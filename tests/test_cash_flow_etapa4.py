"""tests/test_cash_flow_etapa4.py — Fluxo de Caixa Realizado (Etapa 4).

Fonte oficial: FinancialRecord (status='pago', paid_date). Regras cobertas:
receita só entra com RECEBIMENTO; PO só entra PAGA; despesa só entra PAGA;
período pela data do movimento (paid_date); uma única aparição por movimento;
categoria/centro de custo corretos; previsto separado do realizado;
multiempresa; tela somente leitura.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.user import User
from app.services.cash_flow_service import (
    realized_entries, split_movements, movement_info, pending_forecast,
)
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (FinancialRecord, OrderPayment, Order, POPayment,
                      PurchaseOrder, CostCenter, FinancialCategory, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302)
    return c


def _cid_of(app, email=ADMIN_EMAIL):
    with app.app_context():
        return User.query.filter_by(email=email).first().company_id


def _cat(app, cid, ctype="expense", name=None):
    with app.app_context():
        cat = FinancialCategory.query.filter_by(company_id=cid, type=ctype,
                                                name=name).first()
        if cat is None:
            cat = FinancialCategory(company_id=cid, name=name or f"Cat {ctype}",
                                    type=ctype, active=True)
            db.session.add(cat)
            db.session.commit()
        return cat.id


def _cc(app, cid, name="CC Caixa"):
    with app.app_context():
        cc = CostCenter.query.filter_by(company_id=cid, name=name).first()
        if cc is None:
            cc = CostCenter(company_id=cid, name=name, active=True)
            db.session.add(cc)
            db.session.commit()
        return cc.id


_TODAY = now_br().date()


def _range_this_month():
    return _TODAY.replace(day=1), _TODAY


# ─────────────────────────────────────────────────────────────────────────────
# Receita: somente recebimento entra no caixa
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_revenue_only_on_receipt(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        client = Client(company_id=cid, name="Cliente Caixa")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-CX-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=1000.0,
                      payment_method="PIX", emission_date=_TODAY,
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        pmt = OrderPayment(order_id=order.id, installment_no=1, amount=1000.0,
                           due_date=_TODAY, paid_amount=0.0)
        db.session.add(pmt)
        db.session.flush()
        # SO faturado com FR PENDENTE (ainda não recebido)
        fr = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                             amount=1000.0, status="pendente", emission_date=_TODAY,
                             due_date=_TODAY, reference=f"order_payment:{pmt.id}")
        db.session.add(fr)
        db.session.commit()
        oid, pid = order.id, pmt.id

    first, last = _range_this_month()
    with testing_app.app_context():
        # faturado + não recebido → caixa 0
        assert realized_entries(cid, first, last) == []
        # recebimento (baixa) → caixa = valor recebido, UMA única vez
        from app.services.order_service import baixa
        pmt = db.session.get(OrderPayment, pid)
        baixa(pmt, 600.0, 1, paid_date=_TODAY)  # recebeu parcial: 600 de 1000
        entries = realized_entries(cid, first, last)
        assert len(entries) == 1
        assert entries[0].amount == 600.0
        inflows, outflows = split_movements(entries)
        assert len(inflows) == 1 and outflows == []


# ─────────────────────────────────────────────────────────────────────────────
# PO: somente pago entra no caixa
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_po_only_when_paid(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        po_unpaid = PurchaseOrder(company_id=cid,
                                  number=f"PO-CX-{uuid.uuid4().hex[:8]}",
                                  status="aberto", amount=500.0, created_by=1)
        db.session.add(po_unpaid)
        db.session.flush()
        pp1 = POPayment(po_id=po_unpaid.id, installment_no=1, amount=500.0,
                        due_date=_TODAY, paid_amount=0.0)
        db.session.add(pp1)
        db.session.flush()
        fr_unpaid = FinancialRecord(company_id=cid, type="cost", category="custo_fornecedor",
                                    amount=500.0, status="pendente",
                                    due_date=_TODAY, reference=f"po_payment:{pp1.id}")
        # PO pago
        po_paid = PurchaseOrder(company_id=cid,
                                number=f"PO-CXP-{uuid.uuid4().hex[:8]}",
                                status="pago", amount=300.0, created_by=1)
        db.session.add(po_paid)
        db.session.flush()
        pp2 = POPayment(po_id=po_paid.id, installment_no=1, amount=300.0,
                        due_date=_TODAY, paid_at=now_br(), paid_amount=300.0, paid_by=1)
        db.session.add(pp2)
        db.session.flush()
        fr_paid = FinancialRecord(company_id=cid, type="cost", category="custo_fornecedor",
                                  amount=300.0, status="pago", paid_date=_TODAY,
                                  reference=f"po_payment:{pp2.id}")
        # PO rascunho — sem FR (não é custo realizado)
        db.session.add(PurchaseOrder(company_id=cid,
                                     number=f"PO-CXR-{uuid.uuid4().hex[:8]}",
                                     status="rascunho", amount=999.0, created_by=1))
        db.session.add(fr_unpaid)
        db.session.add(fr_paid)
        db.session.commit()

    first, last = _range_this_month()
    with testing_app.app_context():
        entries = realized_entries(cid, first, last)
        outflows = split_movements(entries)[1]
        assert len(outflows) == 1          # só o PO pago
        assert outflows[0].amount == 300.0


# ─────────────────────────────────────────────────────────────────────────────
# Despesa: somente paga entra no caixa
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_expense_only_when_paid(testing_app):
    cid = _cid_of(testing_app)
    cat = _cat(testing_app, cid, name="Aluguel Caixa")
    cc = _cc(testing_app, cid)
    with testing_app.app_context():
        pend = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Aluguel pendente", amount=2000.0,
                               status="pendente", emission_date=_TODAY,
                               due_date=_TODAY, financial_category_id=cat,
                               cost_center_id=cc, reference="expense:888001")
        venc = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Aluguel vencido", amount=1500.0,
                               status="pendente", emission_date=_TODAY,
                               due_date=_TODAY - timedelta(days=10),
                               financial_category_id=cat, cost_center_id=cc,
                               reference="expense:888002")
        canc = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Aluguel cancelado", amount=700.0,
                               status="cancelado", emission_date=_TODAY,
                               due_date=_TODAY, financial_category_id=cat,
                               cost_center_id=cc, reference="expense:888003")
        paga = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Aluguel pago", amount=1000.0,
                               status="pago", emission_date=_TODAY, paid_date=_TODAY,
                               due_date=_TODAY, financial_category_id=cat,
                               cost_center_id=cc, reference="expense:888004")
        db.session.add_all([pend, venc, canc, paga])
        db.session.commit()

    first, last = _range_this_month()
    with testing_app.app_context():
        entries = realized_entries(cid, first, last)
        outflows = split_movements(entries)[1]
        assert len(outflows) == 1
        assert outflows[0].description == "Aluguel pago" and outflows[0].amount == 1000.0
        info = movement_info(outflows[0])
        assert info["origem"] == "DESPESA"
        assert info["category_label"] == "Aluguel Caixa"
        assert info["cost_center"] == "CC Caixa"


# ─────────────────────────────────────────────────────────────────────────────
# Período pela data do movimento (paid_date), nunca created_at
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_period_uses_paid_date(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        db.session.add(FinancialRecord(
            company_id=cid, type="revenue", category="receita_servico",
            description="Recebimento de outro mês", amount=900.0, status="pago",
            paid_date=_TODAY - timedelta(days=400), reference="order_payment:777001"))
        db.session.add(FinancialRecord(
            company_id=cid, type="cost", category="custo_fornecedor",
            description="Pagamento deste mês", amount=100.0, status="pago",
            paid_date=_TODAY, reference="po_payment:777002"))
        db.session.commit()

    first, last = _range_this_month()
    with testing_app.app_context():
        entries = realized_entries(cid, first, last)
        assert len(entries) == 1 and entries[0].description == "Pagamento deste mês"
        assert realized_entries(cid, _TODAY - timedelta(days=400),
                                _TODAY - timedelta(days=400))[0].amount == 900.0


# ─────────────────────────────────────────────────────────────────────────────
# Previsto separado do realizado
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_forecast_separate_from_realized(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        db.session.add(FinancialRecord(company_id=cid, type="revenue",
                                       description="A receber", amount=400.0,
                                       status="pendente", reference="order_payment:777003"))
        db.session.add(FinancialRecord(company_id=cid, type="expense",
                                       description="A pagar", amount=200.0,
                                       status="pendente", reference="expense:777004"))
        db.session.commit()
    first, last = _range_this_month()
    with testing_app.app_context():
        assert realized_entries(cid, first, last) == []  # previsto NÃO é realizado
        to_receive, to_pay = pending_forecast(cid)
        assert to_receive == 400.0 and to_pay == 200.0


# ─────────────────────────────────────────────────────────────────────────────
# Multiempresa + tela somente leitura
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_flow_multitenant_and_screen(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B CX", slug="empresa-b-cx", document="00.000.000/0007-00")
        db.session.add(comp_b)
        db.session.flush()
        fr_b = FinancialRecord(company_id=comp_b.id, type="revenue",
                               description="Recebimento da Empresa B", amount=5000.0,
                               status="pago", paid_date=_TODAY, reference="order_payment:777005")
        fr_a = FinancialRecord(company_id=cid, type="revenue",
                               description="Recebimento da Empresa A", amount=300.0,
                               status="pago", paid_date=_TODAY, reference="order_payment:777006")
        db.session.add_all([fr_b, fr_a])
        db.session.commit()

    first, last = _range_this_month()
    with testing_app.app_context():
        entries = realized_entries(cid, first, last)
        assert len(entries) == 1 and entries[0].description == "Recebimento da Empresa A"

    c = _login(testing_app)
    page = c.get("/financial/cash-flow").get_data(as_text=True)
    assert "Recebimento da Empresa A" in page
    assert "Recebimento da Empresa B" not in page      # sem vazamento
    assert "Saldo inicial não configurado" in page      # não inventa saldo inicial
    # tela somente leitura: sem formulários de mutação
    assert "form method=\"post\"" not in page
    r = c.post("/financial/cash-flow")
    assert r.status_code == 405  # sem rota de mutação


# ─────────────────────────────────────────────────────────────────────────────
# RBAC: usuário sem permissão também só vê (não modifica nada nesta tela)
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_flow_view_for_viewer_user(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        u = User(email="caixa_viewer@teste.local", name="Viewer Caixa",
                 company_id=cid, is_active=True, role="operator")
        u.set_password("senha123!")
        db.session.add(u)
        db.session.commit()
    c = _login(testing_app, email="caixa_viewer@teste.local", password="senha123!")
    assert c.get("/financial/cash-flow").status_code == 200
    assert c.post("/financial/cash-flow").status_code == 405
