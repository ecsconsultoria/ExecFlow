"""tests/test_cash_flow_completo_etapa9b.py — Caixa completo (Etapa 9B).

Cobre: saldo inicial configurável por empresa (companies.settings, sem
migration); RBAC financial.manage na configuração; multiempresa; realizado
(FR pago por paid_date); previsto (due_date via ar_ap_service); saldo
realizado/projetado; mês seguinte; transição previsto→realizado sem
duplicidade; FR cancelado fora; pago não permanece no previsto; DRE e
AR/AP inalterados.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.user import User
from app.services.cash_flow_service import (
    realized_entries, split_movements, initial_balance,
    set_initial_balance, forecast_entries,
)
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"
TODAY = now_br().date()
NEXT_M = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)


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


def _cid(app, email=ADMIN_EMAIL):
    with app.app_context():
        return User.query.filter_by(email=email).first().company_id


def _so_parcel(app, cid, *, due, amount=500.0, paid=False):
    with app.app_context():
        client = Client(company_id=cid, name=f"9B {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-9B-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=amount,
                  payment_method="PIX", emission_date=TODAY,
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        p = OrderPayment(order_id=o.id, installment_no=1, amount=amount,
                         due_date=due,
                         paid_at=now_br() if paid else None,
                         paid_amount=amount if paid else 0.0,
                         paid_by=1 if paid else None)
        db.session.add(p)
        db.session.commit()
        return o.id, p.id


# ─────────────────────────────────────────────────────────────────────────────
# Saldo inicial
# ─────────────────────────────────────────────────────────────────────────────

def test_initial_balance_configurable_and_audited(testing_app):
    cid = _cid(testing_app)
    with testing_app.app_context():
        from app.models.company import Company
        company = db.session.get(Company, cid)
        assert initial_balance(company) == (0.0, None)  # nunca inferido
        set_initial_balance(company, 1500.50, date(2026, 8, 1), 1)
        db.session.commit()
        company = db.session.get(Company, cid)
        assert initial_balance(company) == (1500.50, date(2026, 8, 1))

    c = _login(testing_app)
    r = c.post("/financial/cash-flow/settings",
               data={"cash_initial_balance": "2000,00",
                     "cash_initial_balance_date": "2026-08-15"},
               follow_redirects=True)
    assert r.status_code == 200 and "Saldo inicial salvo" in r.get_data(as_text=True)
    with testing_app.app_context():
        from app.models.company import Company
        company = db.session.get(Company, cid)
        assert initial_balance(company) == (2000.00, date(2026, 8, 15))
        from app.models.audit import AuditLog
        assert AuditLog.query.filter(AuditLog.action.like("%Saldo inicial ALTERADO%")).count() == 1


def test_initial_balance_multitenant_and_rbac(testing_app):
    cid = _cid(testing_app)
    with testing_app.app_context():
        from app.models.company import Company
        comp_b = Company(name="Empresa B 9B", slug="empresa-b-9b", document="00.000.000/0010-00")
        db.session.add(comp_b)
        db.session.commit()
        set_initial_balance(db.session.get(Company, cid), 1000.0, date(2026, 8, 1), 1)
        set_initial_balance(comp_b, 9999.0, date(2026, 8, 1), 1)
        db.session.commit()
        assert initial_balance(db.session.get(Company, cid))[0] == 1000.0  # sem vazamento

        u = User(email="op9b@teste.local", name="Op 9B", company_id=cid,
                 is_active=True, role="operator")
        u.set_password("senha123!")
        db.session.add(u)
        db.session.commit()

    c = _login(testing_app, email="op9b@teste.local", password="senha123!")
    r = c.post("/financial/cash-flow/settings",
               data={"cash_initial_balance": "1,00",
                     "cash_initial_balance_date": "2026-08-15"},
               follow_redirects=False)
    assert r.status_code == 403  # sem financial.manage


# ─────────────────────────────────────────────────────────────────────────────
# Realizado + Previsto + Saldos
# ─────────────────────────────────────────────────────────────────────────────

def test_realized_forecast_balances(testing_app):
    cid = _cid(testing_app)
    due_next = NEXT_M + timedelta(days=5)
    _so_parcel(testing_app, cid, due=due_next, amount=10000.0)      # previsto
    _so_parcel(testing_app, cid, due=due_next, amount=500.0, paid=True)  # será realizado

    with testing_app.app_context():
        from app.models.company import Company
        company = db.session.get(Company, cid)
        set_initial_balance(company, 2000.0, date(2026, 8, 1), 1)
        db.session.commit()

        # baixa cria o FR pago (realizado)
        from app.services.order_service import baixa
        paid_pmt = (OrderPayment.query.filter(OrderPayment.paid_at.isnot(None)).first())
        baixa(paid_pmt, 500.0, 1, paid_date=NEXT_M + timedelta(days=1))

        m_start, m_end = NEXT_M.replace(day=1), (NEXT_M + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        entries = realized_entries(cid, m_start, m_end)
        inflows, outflows = split_movements(entries)
        assert len(inflows) == 1 and inflows[0].amount == 500.0

        fin, fout = forecast_entries(cid, m_start, m_end)
        assert sum(r.amount for r in fin) == 10000.0      # só a pendente
        assert fout == []                                  # nenhuma saída prevista

        init_val, _ = initial_balance(company)
        realized_balance = init_val + 500.0
        projected = realized_balance + 10000.0
        assert realized_balance == 2500.0 and projected == 12500.0


def test_transition_no_duplication(testing_app):
    cid = _cid(testing_app)
    due = NEXT_M + timedelta(days=10)
    oid, pid = _so_parcel(testing_app, cid, due=due, amount=10000.0)

    m_start, m_end = NEXT_M.replace(day=1), (NEXT_M + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    with testing_app.app_context():
        fin, _ = forecast_entries(cid, m_start, m_end)
        assert sum(r.amount for r in fin) == 10000.0          # ANTES: previsto
        assert realized_entries(cid, m_start, m_end) == []    # realizado 0

        from app.services.order_service import baixa
        pmt = db.session.get(OrderPayment, pid)
        baixa(pmt, 10000.0, 1, paid_date=due)

        fin, _ = forecast_entries(cid, m_start, m_end)
        assert sum(r.amount for r in fin) == 0.0              # DEPOIS: previsto 0
        entries = realized_entries(cid, m_start, m_end)
        assert len(entries) == 1 and entries[0].amount == 10000.0  # realizado 10.000
        # nunca previsto + realizado simultaneamente


def test_cancelled_out_and_forecast_filtering(testing_app):
    cid = _cid(testing_app)
    due = NEXT_M + timedelta(days=7)
    with testing_app.app_context():
        db.session.add(FinancialRecord(company_id=cid, type="expense", category="outro",
                                       description="Cancelada", amount=99.0,
                                       status="cancelado", emission_date=TODAY,
                                       due_date=due, reference="expense:9b1"))
        db.session.add(FinancialRecord(company_id=cid, type="expense", category="outro",
                                       description="Paga", amount=77.0,
                                       status="pago", emission_date=TODAY,
                                       due_date=due, paid_date=TODAY,
                                       reference="expense:9b2"))
        db.session.commit()
        m_start, m_end = NEXT_M.replace(day=1), (NEXT_M + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        fin, fout = forecast_entries(cid, m_start, m_end)
        assert sum(r.amount for r in fout) == 0.0  # cancelada fora; paga não permanece no previsto
        # paga aparece no realizado (caixa), cancelada nunca
        entries = realized_entries(cid, TODAY.replace(day=1), TODAY)
        assert any(e.amount == 77.0 for e in entries)
        assert not any(e.amount == 99.0 for e in entries)


def test_next_month_filter_and_screen(testing_app):
    cid = _cid(testing_app)
    due_next = NEXT_M + timedelta(days=3)
    _so_parcel(testing_app, cid, due=due_next, amount=1234.0)
    c = _login(testing_app)
    page = c.get("/financial/cash-flow?period=next_month").get_data(as_text=True)
    assert "1.234,00" in page and "PREVISTO" in page
    assert "SALDO PROJETADO" in page and "SALDO INICIAL" in page


def test_cash_does_not_change_dre_ar_ap(testing_app):
    from app.services import dre_service
    cid = _cid(testing_app)
    due = NEXT_M + timedelta(days=2)
    oid, pid = _so_parcel(testing_app, cid, due=due, amount=1000.0)
    with testing_app.app_context():
        m_start, m_end = NEXT_M.replace(day=1), (NEXT_M + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        before_ar = sum(r.amount for r in forecast_entries(cid, m_start, m_end)[0])
        before_dre = dre_service.recognized_revenue(cid, m_start, m_end)
        assert before_ar == 1000.0 and before_dre == 0.0  # faturamento foi hoje (fora do mês seguinte)
        # caixa não altera AR nem DRE por si
        from app.services.order_service import baixa
        pmt = db.session.get(OrderPayment, pid)
        baixa(pmt, 1000.0, 1, paid_date=due)
        assert dre_service.recognized_revenue(cid, m_start, m_end) == before_dre
        assert sum(r.amount for r in forecast_entries(cid, m_start, m_end)[0]) == 0.0  # AR caiu só pela baixa
