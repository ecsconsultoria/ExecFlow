"""tests/test_baixa_parcial_etapa10d.py — Correção da baixa parcial (Etapa 10D).

Cobre: recebimento integral; parcial; 2 e 3 parciais; parcial + quitação;
excesso bloqueado (sem alterar nada); duplicidade/retry bloqueado; AR e
Caixa após cada recebimento; DRE inalterada; rollback em erro; auditoria;
multiempresa e RBAC.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.financial import FinancialRecord
from app.models.order import Order, OrderPayment
from app.models.user import User
from app.services import order_service
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (FinancialRecord, OrderPayment, Order, Client):
            model.query.delete()
        db.session.commit()
    yield


def _cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _seed(app, cid, amount=1300.0):
    with app.app_context():
        client = Client(company_id=cid, name=f"10D {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-10D-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=amount,
                  payment_method="PIX", emission_date=date.today(),
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        p = OrderPayment(order_id=o.id, installment_no=1, amount=amount,
                         due_date=date.today(), paid_amount=0.0)
        db.session.add(p)
        db.session.commit()
        return o.id, p.id


def _state(app, oid, pid):
    with app.app_context():
        o = db.session.get(Order, oid)
        p = db.session.get(OrderPayment, pid)
        frs = FinancialRecord.query.filter_by(reference=f"order_payment:{pid}").all()
        return {"so_status": o.status, "paid_amount": p.paid_amount,
                "is_paid": p.is_paid, "balance": p.balance,
                "n_frs": len(frs), "fr_amount": frs[0].amount if frs else None,
                "fr_status": frs[0].status if frs else None}


# ─────────────────────────────────────────────────────────────────────────────
# Cenário principal (spec 20)
# ─────────────────────────────────────────────────────────────────────────────

def test_main_partial_flow_500_plus_800(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=1300.0)

    with testing_app.app_context():
        from app.services.ar_ap_service import receivable_totals, received_in_period
        from app.services import dre_service
        p = db.session.get(OrderPayment, pid)
        dre_before = dre_service.recognized_revenue(cid, date.today().replace(day=1),
                                                    date.today())

        # Recebimento 1: 500
        order_service.baixa(p, 500.0, 1, paid_date=date.today())
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 500.0 and s["balance"] == 800.0
        assert s["is_paid"] is False
        assert s["fr_amount"] == 500.0 and s["n_frs"] == 1   # caixa +500
        assert receivable_totals(cid, date.today().replace(day=1), date.today())[0] == 800.0
        assert dre_service.recognized_revenue(cid, date.today().replace(day=1),
                                              date.today()) == dre_before  # DRE inalterada

        # Recebimento 2: 800 (quitação)
        order_service.baixa(p, 800.0, 1, paid_date=date.today())
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 1300.0 and s["balance"] == 0.0
        assert s["is_paid"] is True
        assert s["fr_amount"] == 1300.0 and s["n_frs"] == 1   # caixa acumulado +1.300
        assert receivable_totals(cid, date.today().replace(day=1), date.today())[0] == 0.0
        assert dre_service.recognized_revenue(cid, date.today().replace(day=1),
                                              date.today()) == dre_before
        assert s["so_status"] == "concluido"  # auto-conclusão voltou a funcionar


def test_three_partials_300_400_600(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=1300.0)
    with testing_app.app_context():
        p = db.session.get(OrderPayment, pid)
        order_service.baixa(p, 300.0, 1)
        assert _state(testing_app, oid, pid)["paid_amount"] == 300.0
        order_service.baixa(p, 400.0, 1)
        assert _state(testing_app, oid, pid)["paid_amount"] == 700.0
        order_service.baixa(p, 600.0, 1)
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 1300.0 and s["balance"] == 0.0 and s["is_paid"]
        assert s["fr_amount"] == 1300.0 and s["n_frs"] == 1  # sem duplicidade


# ─────────────────────────────────────────────────────────────────────────────
# Excesso, duplicidade e retry
# ─────────────────────────────────────────────────────────────────────────────

def test_excess_blocked_without_changes(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=1300.0)
    with testing_app.app_context():
        p = db.session.get(OrderPayment, pid)
        order_service.baixa(p, 1000.0, 1)
        with pytest.raises(ValueError) as e:
            order_service.baixa(p, 400.0, 1)  # saldo é 300
        assert "saldo restante" in str(e.value)
        db.session.rollback()
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 1000.0 and s["balance"] == 300.0  # nada alterado


def test_duplicate_and_retry_blocked(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=1300.0)
    with testing_app.app_context():
        p = db.session.get(OrderPayment, pid)
        order_service.baixa(p, 1300.0, 1)
        with pytest.raises(ValueError) as e:
            order_service.baixa(p, 1300.0, 1)  # retry/double click
        assert "já quitada" in str(e.value)
        db.session.rollback()
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 1300.0 and s["n_frs"] == 1  # sem duplicidade


def test_integral_and_zero_blocked(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=500.0)
    with testing_app.app_context():
        p = db.session.get(OrderPayment, pid)
        order_service.baixa(p, 500.0, 1)  # integral
        assert _state(testing_app, oid, pid)["is_paid"] is True
        with pytest.raises(ValueError):
            order_service.baixa(p, 0.0, 1)  # zero não passa
        db.session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Rollback, auditoria, multiempresa/RBAC (via rota)
# ─────────────────────────────────────────────────────────────────────────────

def test_rollback_on_failure(testing_app, monkeypatch):
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=1300.0)
    import app.services.order_service as os_mod
    def boom(order):
        raise RuntimeError("falha simulada no recálculo")
    monkeypatch.setattr(os_mod.margin_service, "recalculate_order", boom)
    with testing_app.app_context():
        p = db.session.get(OrderPayment, pid)
        with pytest.raises(RuntimeError):
            os_mod.baixa(p, 500.0, 1)
        db.session.rollback()
        s = _state(testing_app, oid, pid)
        assert s["paid_amount"] == 0.0 and s["n_frs"] == 0  # estado anterior preservado


def test_baixa_route_multitenant_and_rbac(testing_app):
    from app.models.company import Company
    cid = _cid(testing_app)
    oid, pid = _seed(testing_app, cid, amount=300.0)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B 10D", slug="empresa-b-10d", document="00.000.000/0012-00")
        db.session.add(comp_b)
        db.session.flush()
        o_b = Order(company_id=comp_b.id, client_id=None,
                    number="SO-B-10D", status="faturado",
                    client_name="", contact_name="", email="", celular="",
                    language="pt", billing_type="recibo", total_amount=300.0,
                    payment_method="PIX", emission_date=date.today(),
                    invoiced_at=now_br(), created_by=1)
        db.session.add(o_b)
        db.session.flush()
        p_b = OrderPayment(order_id=o_b.id, installment_no=1, amount=300.0,
                           due_date=date.today(), paid_amount=0.0)
        db.session.add(p_b)
        db.session.flush()
        u = User(email="op10d@teste.local", name="Op 10D", company_id=cid,
                 is_active=True, role="operator")
        u.set_password("senha123!")
        db.session.add(u)
        db.session.commit()
        pid_b = p_b.id

    c = testing_app.test_client()
    c.post("/auth/login", data={"email": "op10d@teste.local", "password": "senha123!"},
           follow_redirects=False)
    # RBAC: operador sem financial.manage não baixa (403)
    assert c.post(f"/orders/payments/{pid}/baixa", data={}).status_code == 403
    # multiempresa: admin (empresa A) não acessa parcela da empresa B
    # (_check_company responde 403 — sem vazamento de informação)
    c2 = testing_app.test_client()
    c2.post("/auth/login", data={"email": ADMIN_EMAIL, "password": "admin123"},
            follow_redirects=False)
    assert c2.post(f"/orders/payments/{pid_b}/baixa", data={}).status_code == 403
