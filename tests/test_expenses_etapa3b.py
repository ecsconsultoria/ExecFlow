"""tests/test_expenses_etapa3b.py — Módulo de Despesas Gerais (Etapa 3B).

Cobre: criação; categoria expense obrigatória (revenue/direct_cost rejeitadas);
centro de custo obrigatório e da própria empresa; fornecedor/SO/PO opcionais;
pagamento único e transacional; cancelamento (pendente ok, paga bloqueada,
histórico preservado); duplicidade de FinancialRecord; multiempresa; RBAC;
regressão de dados transacionais.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.user import User
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (FinancialRecord, OrderPayment, Order,
                      CostCenter, FinancialCategory, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302)
    return c


def _cid_of(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).first().company_id


def _cat(app, cid, ctype="expense", name=None):
    with app.app_context():
        q = FinancialCategory.query.filter_by(company_id=cid, type=ctype)
        if name:
            q = q.filter_by(name=name)
        cat = q.first()
        if cat is None:
            cat = FinancialCategory(company_id=cid, name=name or f"Cat {ctype}",
                                    type=ctype, active=True)
            db.session.add(cat)
            db.session.commit()
        return cat.id


def _cc(app, cid, name="Admin Teste"):
    with app.app_context():
        cc = CostCenter.query.filter_by(company_id=cid, name=name).first()
        if cc is None:
            cc = CostCenter(company_id=cid, name=name, active=True)
            db.session.add(cc)
            db.session.commit()
        return cc.id


def _expense_payload(cat_id, cc_id, **overrides):
    p = {
        "description": "Honorários contábeis",
        "amount": "1000,00",
        "financial_category_id": str(cat_id),
        "cost_center_id": str(cc_id),
        "emission_date": "2026-08-28",
        "due_date": "2026-09-10",
    }
    p.update(overrides)
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Criação e validações
# ─────────────────────────────────────────────────────────────────────────────

def test_expense_create_valid(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    c = _login(testing_app)
    r = c.post("/financial/expenses/new", data=_expense_payload(cat, cc),
               follow_redirects=True)
    assert r.status_code == 200 and "Honorários contábeis" in r.get_data(as_text=True)
    with testing_app.app_context():
        fr = FinancialRecord.query.filter_by(company_id=cid, type="expense").first()
        assert fr is not None
        assert fr.status == "pendente"
        assert fr.reference == f"expense:{fr.id}"
        assert fr.financial_category_id == cat and fr.cost_center_id == cc
        assert fr.order_id is None and fr.purchase_order_id is None  # SO/PO opcionais


def test_expense_category_must_be_expense(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    rev_cat = _cat(testing_app, cid, ctype="revenue", name="Cat Revenue")
    dc_cat = _cat(testing_app, cid, ctype="direct_cost", name="Cat DirectCost")
    cc = _cc(testing_app, cid)
    c = _login(testing_app)

    r = c.post("/financial/expenses/new", data=_expense_payload(rev_cat, cc),
               follow_redirects=True)
    assert "tipo Despesa" in r.get_data(as_text=True)  # flash de erro
    r = c.post("/financial/expenses/new", data=_expense_payload(dc_cat, cc),
               follow_redirects=True)
    assert "tipo Despesa" in r.get_data(as_text=True)
    with testing_app.app_context():
        assert FinancialRecord.query.filter_by(type="expense").count() == 0


def test_expense_cost_center_required_and_company_scoped(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B 3B", slug="empresa-b-3b", document="00.000.000/0004-00")
        db.session.add(comp_b)
        db.session.flush()
        cc_b = CostCenter(company_id=comp_b.id, name="CC da B", active=True)
        db.session.add(cc_b)
        db.session.commit()
        cc_b_id = cc_b.id
    c = _login(testing_app)

    r = c.post("/financial/expenses/new",
               data=_expense_payload(cat, None), follow_redirects=True)
    assert "Centro de custo é obrigatório" in r.get_data(as_text=True)

    r = c.post("/financial/expenses/new",
               data=_expense_payload(cat, cc_b_id), follow_redirects=True)
    assert "outra empresa" in r.get_data(as_text=True)
    with testing_app.app_context():
        assert FinancialRecord.query.filter_by(type="expense").count() == 0


def test_expense_supplier_optional_and_scoped(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    with testing_app.app_context():
        from app.models.supplier import Supplier
        comp_b = Company(name="Empresa C 3B", slug="empresa-c-3b", document="00.000.000/0005-00")
        db.session.add(comp_b)
        db.session.flush()
        sup_b = Supplier(company_id=comp_b.id, name="Fornecedor da B")
        db.session.add(sup_b)
        db.session.commit()
        sup_b_id = sup_b.id
    c = _login(testing_app)

    # fornecedor opcional — criação sem fornecedor
    r = c.post("/financial/expenses/new", data=_expense_payload(cat, cc),
               follow_redirects=True)
    assert "Despesa criada" in r.get_data(as_text=True)
    with testing_app.app_context():
        fr = FinancialRecord.query.filter_by(type="expense").first()
        assert fr.supplier_id is None

    # fornecedor de outra empresa rejeitado
    r = c.post("/financial/expenses/new",
               data=_expense_payload(cat, cc, description="Desp 2",
                                     supplier_id=str(sup_b_id)),
               follow_redirects=True)
    assert "outra empresa" in r.get_data(as_text=True)


# ─────────────────────────────────────────────────────────────────────────────
# Pagamento / duplicidade / cancelamento
# ─────────────────────────────────────────────────────────────────────────────

def test_expense_payment_creates_single_financial_record(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    c = _login(testing_app)
    c.post("/financial/expenses/new", data=_expense_payload(cat, cc), follow_redirects=True)
    with testing_app.app_context():
        fr = FinancialRecord.query.filter_by(type="expense").first()
        fid = fr.id

    r = c.post(f"/financial/record/{fid}/baixa", data={"paid_date": "2026-09-10"},
               follow_redirects=True)
    assert "Baixa registrada com sucesso" in r.get_data(as_text=True)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        assert fr.status == "pago" and fr.paid_date == date(2026, 9, 10)
        n = FinancialRecord.query.filter_by(reference=f"expense:{fid}").count()
        assert n == 1  # pagamento NÃO duplica o lançamento


def test_expense_reference_unique_index(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    with testing_app.app_context():
        # O app de testes usa create_all (sem migrations) — espelha o efeito
        # da migration a3c1f8d2e6b4, que cria este índice parcial no prod/dev.
        db.session.execute(db.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_financial_records_active_reference "
            "ON financial_records (reference) "
            "WHERE deleted_at IS NULL AND reference IS NOT NULL"))
        db.session.commit()
        db.session.add(FinancialRecord(company_id=cid, type="expense",
                                       description="A", amount=1.0, status="pendente",
                                       reference="expense:999999"))
        db.session.commit()
        db.session.add(FinancialRecord(company_id=cid, type="expense",
                                       description="B", amount=2.0, status="pendente",
                                       reference="expense:999999"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_expense_payment_rollback_on_failure(testing_app, monkeypatch):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    c = _login(testing_app)
    c.post("/financial/expenses/new", data=_expense_payload(cat, cc), follow_redirects=True)
    with testing_app.app_context():
        fid = FinancialRecord.query.filter_by(type="expense").first().id

    import app.blueprints.financial.routes as froutes
    def boom(*a, **k):
        raise RuntimeError("falha simulada no log de auditoria")
    monkeypatch.setattr(froutes, "log_activity", boom)

    r = c.post(f"/financial/record/{fid}/baixa", data={"paid_date": "2026-09-10"},
               follow_redirects=True)
    assert "revertida" in r.get_data(as_text=True)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        assert fr.status == "pendente" and fr.paid_date is None  # rollback completo


def test_expense_cancel_rules(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    c = _login(testing_app)
    c.post("/financial/expenses/new", data=_expense_payload(cat, cc), follow_redirects=True)
    with testing_app.app_context():
        fid = FinancialRecord.query.filter_by(type="expense").first().id

    # pendente -> cancela
    r = c.post(f"/financial/expenses/{fid}/cancel", follow_redirects=True)
    assert "Despesa cancelada" in r.get_data(as_text=True)
    with testing_app.app_context():
        assert db.session.get(FinancialRecord, fid).status == "cancelado"
        assert db.session.get(FinancialRecord, fid).deleted_at is None  # sem soft-delete

    # paga -> não cancela (preserva histórico)
    c2 = _login(testing_app)
    c2.post("/financial/expenses/new", data=_expense_payload(cat, cc, description="Desp paga"),
            follow_redirects=True)
    with testing_app.app_context():
        fid2 = FinancialRecord.query.filter_by(type="expense", description="Desp paga").first().id
    c2.post(f"/financial/record/{fid2}/baixa", data={"paid_date": "2026-09-10"},
            follow_redirects=True)
    r = c2.post(f"/financial/expenses/{fid2}/cancel", follow_redirects=True)
    assert "não pode ser cancelada" in r.get_data(as_text=True)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid2)
        assert fr.status == "pago" and fr.deleted_at is None  # histórico preservado


def test_expense_paid_edit_blocked(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    c = _login(testing_app)
    c.post("/financial/expenses/new", data=_expense_payload(cat, cc), follow_redirects=True)
    with testing_app.app_context():
        fid = FinancialRecord.query.filter_by(type="expense").first().id
    c.post(f"/financial/record/{fid}/baixa", data={"paid_date": "2026-09-10"},
           follow_redirects=True)

    r = c.get(f"/financial/expenses/{fid}/edit", follow_redirects=True)
    assert "não pode ser editada" in r.get_data(as_text=True)
    r = c.post(f"/financial/expenses/{fid}/edit",
               data=_expense_payload(cat, cc, description="TENTATIVA",
                                     amount="5,00"), follow_redirects=True)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        assert fr.amount == 1000.0 and fr.description != "TENTATIVA"  # não alterou


# ─────────────────────────────────────────────────────────────────────────────
# Multiempresa + RBAC
# ─────────────────────────────────────────────────────────────────────────────

def test_expense_company_isolation(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    with testing_app.app_context():
        comp_b = Company(name="Empresa D 3B", slug="empresa-d-3b", document="00.000.000/0006-00")
        db.session.add(comp_b)
        db.session.flush()
        cat_b = FinancialCategory(company_id=comp_b.id, name="Cat B", type="expense", active=True)
        cc_b = CostCenter(company_id=comp_b.id, name="CC B", active=True)
        db.session.add_all([cat_b, cc_b])
        db.session.flush()
        fr_b = FinancialRecord(company_id=comp_b.id, type="expense", category="outro",
                               description="Despesa da B", amount=500.0, status="pendente",
                               emission_date=date(2026, 8, 1), due_date=date(2026, 8, 15),
                               financial_category_id=cat_b.id, cost_center_id=cc_b.id,
                               reference=f"expense:{999999}")
        db.session.add(fr_b)
        db.session.commit()
        fid_b = fr_b.id

    c = _login(testing_app)  # admin da empresa A
    assert c.get(f"/financial/expenses/{fid_b}/edit").status_code == 404
    assert c.post(f"/financial/expenses/{fid_b}/cancel").status_code == 404
    assert c.post(f"/financial/record/{fid_b}/baixa",
                  data={"paid_date": "2026-09-10"}).status_code == 404
    page = c.get("/financial/expenses").get_data(as_text=True)
    assert "Despesa da B" not in page  # lista não vaza dados da empresa B


def test_expense_rbac_blocks_unauthorized(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    with testing_app.app_context():
        u = User(email="operador@teste3b.local", name="Operador 3B",
                 company_id=cid, is_active=True, role="operator")
        u.set_password("senha123!")
        db.session.add(u)
        db.session.commit()

    c = _login(testing_app, email="operador@teste3b.local", password="senha123!")
    r = c.post("/financial/expenses/new", data=_expense_payload(cat, cc),
               follow_redirects=False)
    assert r.status_code == 403  # sem financial.manage


# ─────────────────────────────────────────────────────────────────────────────
# Regressão de dados transacionais
# ─────────────────────────────────────────────────────────────────────────────

def test_expense_flows_do_not_touch_transactional_data(testing_app):
    cid = _cid_of(testing_app, ADMIN_EMAIL)
    cat = _cat(testing_app, cid)
    cc = _cc(testing_app, cid)
    with testing_app.app_context():
        client = Client(company_id=cid, name="Cliente Reg 3B")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-REG3B-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=2000.0,
                      payment_method="PIX", emission_date=date.today(),
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        pmt = OrderPayment(order_id=order.id, installment_no=1, amount=2000.0,
                           due_date=date.today(), paid_amount=0.0)
        db.session.add(pmt)
        db.session.flush()
        fr = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                             amount=2000.0, status="pendente",
                             reference=f"order_payment:{pmt.id}")
        db.session.add(fr)
        db.session.commit()
        oid, pid, fid = order.id, pmt.id, fr.id

    c = _login(testing_app)
    c.get("/financial/expenses")
    c.post("/financial/expenses/new", data=_expense_payload(cat, cc), follow_redirects=True)

    with testing_app.app_context():
        o = db.session.get(Order, oid)
        p = db.session.get(OrderPayment, pid)
        f = db.session.get(FinancialRecord, fid)
        assert o.status == "faturado" and o.total_amount == 2000.0
        assert p.paid_amount == 0.0 and p.amount == 2000.0
        assert f.amount == 2000.0 and f.status == "pendente" and f.deleted_at is None
