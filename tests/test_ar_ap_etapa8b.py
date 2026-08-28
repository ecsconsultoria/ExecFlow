"""tests/test_ar_ap_etapa8b.py — AR/AP unificados (Etapa 8B).

Cobre: AR por due_date; AP por due_date (custos de PO + despesas gerais);
vencido; recebido/pago por paid_date (caixa); despesa cancelada fora;
duplicidade zero; consistência Dashboard = Painel (mesma função central);
multiempresa; Caixa e DRE inalterados.

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
from app.services.ar_ap_service import (
    receivable_rows, receivable_totals, received_in_period,
    payable_rows, payable_totals, paid_in_period,
)
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
TODAY = now_br().date()
AUG1 = TODAY.replace(day=1)
AUG31 = date(TODAY.year, TODAY.month + 1, 1) - timedelta(days=1) if TODAY.month < 12 else date(TODAY.year, 12, 31)


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


def _cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _so_with_parcel(app, cid, *, due, paid=False, status="faturado", amount=500.0):
    with app.app_context():
        client = Client(company_id=cid, name=f"8B {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-8B-{uuid.uuid4().hex[:8]}", status=status,
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=amount,
                  payment_method="PIX", emission_date=TODAY,
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        p = OrderPayment(order_id=o.id, installment_no=1, amount=amount,
                         due_date=due,
                         paid_at=now_br() if paid else None,
                         paid_amount=amount if paid else 0.0, paid_by=1 if paid else None)
        db.session.add(p)
        db.session.commit()
        return o.id, p.id


def _po_with_parcel(app, cid, *, due, paid=False, amount=300.0):
    with app.app_context():
        po = PurchaseOrder(company_id=cid, number=f"PO-8B-{uuid.uuid4().hex[:8]}",
                           status="faturado", amount=amount, created_by=1)
        db.session.add(po)
        db.session.flush()
        p = POPayment(po_id=po.id, installment_no=1, amount=amount, due_date=due,
                      paid_at=now_br() if paid else None,
                      paid_amount=amount if paid else 0.0, paid_by=1 if paid else None)
        db.session.add(p)
        db.session.commit()
        return po.id, p.id


def _expense(app, cid, *, due, status="pendente", amount=150.0):
    with app.app_context():
        cat = FinancialCategory.query.filter_by(company_id=cid, type="expense").first()
        cc = CostCenter.query.filter_by(company_id=cid).first()
        fr = FinancialRecord(company_id=cid, type="expense", category="outro",
                             description=f"Despesa 8B {uuid.uuid4().hex[:6]}",
                             amount=amount, status=status,
                             emission_date=TODAY, due_date=due,
                             paid_date=date(2026, 8, 5) if status == "pago" else None,
                             financial_category_id=cat.id if cat else None,
                             cost_center_id=cc.id if cc else None,
                             reference=f"expense:{uuid.uuid4().hex[:8]}")
        db.session.add(fr)
        db.session.commit()
        return fr.id


# ─────────────────────────────────────────────────────────────────────────────
# AR — regra única por due_date
# ─────────────────────────────────────────────────────────────────────────────

def test_ar_due_date_rules(testing_app):
    cid = _cid(testing_app)
    in_aug = date(AUG1.year, AUG1.month, 15)
    other_month = date(AUG1.year, (AUG1.month - 2) % 12 + 1, 15)
    _so_with_parcel(testing_app, cid, due=in_aug, amount=500.0)          # a receber em agosto
    _so_with_parcel(testing_app, cid, due=other_month, amount=700.0)     # fora do período
    _so_with_parcel(testing_app, cid, due=in_aug, paid=True, amount=999.0)  # recebida

    with testing_app.app_context():
        rows = receivable_rows(cid, AUG1, AUG31)
        assert len(rows) == 1 and rows[0].amount == 500.0
        total, overdue = receivable_totals(cid, AUG1, AUG31)
        assert total == 500.0
        # vencido: parcela com due < hoje (se 15/08 < hoje)
        assert overdue == (500.0 if in_aug < TODAY else 0.0)
        # recebido no período = caixa (paid_date)
        assert received_in_period(cid, AUG1, AUG31) == 0.0  # baixa não gera FR aqui


# ─────────────────────────────────────────────────────────────────────────────
# AP — custos de PO + despesas gerais, sem duplicidade
# ─────────────────────────────────────────────────────────────────────────────

def test_ap_consolidated_po_plus_expense(testing_app):
    cid = _cid(testing_app)
    due_aug = date(AUG1.year, AUG1.month, 20)
    _po_with_parcel(testing_app, cid, due=due_aug, amount=300.0)      # custo de serviço
    _po_with_parcel(testing_app, cid, due=due_aug, paid=True, amount=999.0)  # paga — fora do saldo
    _expense(testing_app, cid, due=due_aug, amount=150.0)             # despesa geral
    _expense(testing_app, cid, due=due_aug, status="cancelado", amount=777.0)  # cancelada fora

    with testing_app.app_context():
        rows = payable_rows(cid, AUG1, AUG31)
        origens = sorted(r.origem for r in rows)
        assert origens == ["DESPESA", "PO"]           # uma de cada — sem duplicidade
        t = payable_totals(cid, AUG1, AUG31)
        assert t["total"] == 450.0
        assert t["custos"] == 300.0 and t["despesas"] == 150.0
        assert t["vencido"] == (450.0 if due_aug < TODAY else 0.0)
        assert paid_in_period(cid, AUG1, AUG31) == 0.0  # caixa: sem FR pago


# ─────────────────────────────────────────────────────────────────────────────
# Consistência: Dashboard e Painel consomem a MESMA função central
# ─────────────────────────────────────────────────────────────────────────────

def test_dashboard_and_panel_same_source(testing_app):
    from app.blueprints.dashboard.routes import index as dash_index  # noqa: F401
    # a rota do Dashboard e o painel usam ar_ap_service — verificamos que a
    # tela do Dashboard renderiza os mesmos números da função central.
    cid = _cid(testing_app)
    due_aug = date(AUG1.year, AUG1.month, 25)
    _so_with_parcel(testing_app, cid, due=due_aug, amount=3640.0)
    _po_with_parcel(testing_app, cid, due=due_aug, amount=6600.0)

    c = testing_app.test_client()
    c.post("/auth/login", data={"email": ADMIN_EMAIL, "password": "admin123"},
           follow_redirects=False)
    page = c.get("/?period=this_month").get_data(as_text=True)
    with testing_app.app_context():
        ar_total, _ = receivable_totals(cid, AUG1, AUG31)
        ap_total = payable_totals(cid, AUG1, AUG31)["total"]
    # os valores do service aparecem na tela do dashboard (mesma fonte)
    assert "3.640,00" in page and "6.600,00" in page
    assert ar_total == 3640.0 and ap_total == 6600.0


# ─────────────────────────────────────────────────────────────────────────────
# Multiempresa
# ─────────────────────────────────────────────────────────────────────────────

def test_ar_ap_multitenant(testing_app):
    cid = _cid(testing_app)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B 8B", slug="empresa-b-8b", document="00.000.000/0009-00")
        db.session.add(comp_b)
        db.session.commit()
        cid_b = comp_b.id
    due_aug = date(AUG1.year, AUG1.month, 18)
    _so_with_parcel(testing_app, cid_b, due=due_aug, amount=5000.0)
    _po_with_parcel(testing_app, cid_b, due=due_aug, amount=4000.0)

    with testing_app.app_context():
        assert receivable_rows(cid, AUG1, AUG31) == []       # sem vazamento
        assert payable_rows(cid, AUG1, AUG31) == []
        assert receivable_totals(cid_b, AUG1, AUG31)[0] == 5000.0
        assert payable_totals(cid_b, AUG1, AUG31)["total"] == 4000.0


# ─────────────────────────────────────────────────────────────────────────────
# Caixa e DRE inalterados
# ─────────────────────────────────────────────────────────────────────────────

def test_cash_and_dre_unchanged(testing_app):
    from app.services.cash_flow_service import realized_entries
    from app.services import dre_service
    cid = _cid(testing_app)
    due_aug = date(AUG1.year, AUG1.month, 22)
    oid, pid = _so_with_parcel(testing_app, cid, due=due_aug, amount=1000.0)
    with testing_app.app_context():
        from app.services.order_service import baixa
        pmt = db.session.get(OrderPayment, pid)
        baixa(pmt, 1000.0, 1, paid_date=due_aug)

        # Caixa: 1 movimento (FR pago)
        entries = realized_entries(cid, AUG1, AUG31)
        assert len(entries) == 1 and entries[0].amount == 1000.0
        # AR: a parcela paga saiu da obrigação
        assert receivable_rows(cid, AUG1, AUG31) == []
        # DRE: receita por faturamento, independente do pagamento
        rev = dre_service.recognized_revenue(cid, AUG1, AUG31)
        assert rev == 1000.0
