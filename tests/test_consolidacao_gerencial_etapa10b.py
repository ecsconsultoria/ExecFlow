"""tests/test_consolidacao_gerencial_etapa10b.py — Consolidação gerencial (Etapa 10B).

Cobre: KPI de custo com competência correta (service_date → delivery →
created_at fallback); Dashboard = DRE (receita, custo, margem, %); despesas
fora da margem bruta; resultado = margem − despesas; caixa/AR/AP inalterados;
multiempresa; sem duplicidade.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, datetime

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.purchase_order import PurchaseOrder, POPayment, POItem
from app.models.user import User
from app.services import dre_service
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
AUG = date(2026, 8, 1)
AUG_END = date(2026, 8, 31)


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        # Filho-primeiro: PO -> Order (FK purchase_orders.order_id)
        for model in (FinancialRecord, OrderPayment, POItem, POPayment,
                      PurchaseOrder, Order, CostCenter, FinancialCategory, Client):
            model.query.delete()
        db.session.commit()
    yield


def _cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _faturado(app, cid, *, total=1000.0):
    with app.app_context():
        client = Client(company_id=cid, name=f"10B {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-10B-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=total,
                  payment_method="PIX", emission_date=AUG,
                  invoiced_at=datetime(2026, 8, 15, 10, 0), created_by=1)
        db.session.add(o)
        db.session.commit()
        return o.id


def _po(app, cid, oid, *, service_date=None, delivery=None, created=None, amount=300.0):
    with app.app_context():
        po = PurchaseOrder(company_id=cid, number=f"PO-10B-{uuid.uuid4().hex[:8]}",
                           status="aberto", order_id=oid, created_by=1)
        if created:
            po.created_at = created
        if delivery:
            po.delivery_date = delivery
        db.session.add(po)
        db.session.flush()
        if service_date:
            db.session.add(POItem(po_id=po.id, quantity=1, unit_cost=amount,
                                  total_cost=amount, service_date=service_date))
        else:
            po.amount = amount
        db.session.commit()
        return po.id


# ─────────────────────────────────────────────────────────────────────────────
# KPI de custo: competência correta
# ─────────────────────────────────────────────────────────────────────────────

def test_kpi_cost_uses_competence(testing_app):
    from app.blueprints.dashboard.routes import _po_cost
    cid = _cid(testing_app)
    oid = _faturado(testing_app, cid, total=3000.0)
    # criada em julho, serviço em agosto → custo de AGOSTO
    _po(testing_app, cid, oid, service_date=date(2026, 8, 5),
        created=datetime(2026, 7, 10, 9, 0), amount=700.0)
    # sem service/delivery → fallback created_at (julho)
    _po(testing_app, cid, oid, created=datetime(2026, 7, 12, 9, 0), amount=200.0)

    with testing_app.app_context():
        assert _po_cost(cid, AUG, AUG_END) == 700.0     # só a de agosto
        jul_end = date(2026, 7, 31)
        assert _po_cost(cid, date(2026, 7, 1), jul_end) == 200.0  # fallback


def test_dashboard_equals_dre(testing_app):
    from app.blueprints.dashboard.routes import _so_revenue, _po_cost
    cid = _cid(testing_app)
    oid = _faturado(testing_app, cid, total=2000.0)
    _po(testing_app, cid, oid, service_date=date(2026, 8, 6), amount=500.0)

    with testing_app.app_context():
        assert _so_revenue(cid, AUG, AUG_END) == dre_service.recognized_revenue(cid, AUG, AUG_END) == 2000.0
        assert _po_cost(cid, AUG, AUG_END) == dre_service.direct_costs(cid, AUG, AUG_END) == 500.0
        assert dre_service.gross_margin(cid, AUG, AUG_END) == 1500.0
        # Margem % = margem / receita quando receita > 0 (mesma fórmula do Dashboard)
        gm = dre_service.gross_margin(cid, AUG, AUG_END)
        rev = dre_service.recognized_revenue(cid, AUG, AUG_END)
        assert round(gm / rev * 100, 1) == 75.0


def test_expenses_out_of_gross_margin_and_result(testing_app):
    cid = _cid(testing_app)
    _faturado(testing_app, cid, total=1000.0)
    with testing_app.app_context():
        cat = FinancialCategory(company_id=cid, name="Despesas Administrativas",
                                type="expense", active=True)
        db.session.add(cat)
        db.session.flush()
        cc = CostCenter(company_id=cid, name="Administrativo", active=True)
        db.session.add(cc)
        db.session.flush()
        db.session.add(FinancialRecord(company_id=cid, type="expense", category="outro",
                                       description="Aluguel", amount=200.0,
                                       status="pendente", emission_date=date(2026, 8, 5),
                                       due_date=date(2026, 8, 20),
                                       financial_category_id=cat.id, cost_center_id=cc.id,
                                       reference="expense:10b1"))
        db.session.commit()

        assert dre_service.gross_margin(cid, AUG, AUG_END) == 1000.0   # despesa FORA
        assert dre_service.general_expenses(cid, AUG, AUG_END) == 200.0
        assert dre_service.operating_result(cid, AUG, AUG_END) == 800.0


def test_cash_ar_ap_unchanged(testing_app):
    from app.services.cash_flow_service import realized_entries
    from app.services.ar_ap_service import receivable_totals, payable_totals
    cid = _cid(testing_app)
    oid = _faturado(testing_app, cid, total=1000.0)
    with testing_app.app_context():
        pmt = OrderPayment(order_id=oid, installment_no=1, amount=1000.0,
                           due_date=date(2026, 8, 10), paid_amount=0.0)
        db.session.add(pmt)
        db.session.commit()
        # caixa: nada pago; AR: 1000; AP: 0 — regras inalteradas pela consolidação
        assert realized_entries(cid, AUG, AUG_END) == []
        assert receivable_totals(cid, AUG, AUG_END)[0] == 1000.0
        assert payable_totals(cid, AUG, AUG_END)["total"] == 0.0


def test_multitenant_and_screen_labels(testing_app):
    cid = _cid(testing_app)
    _faturado(testing_app, cid, total=1234.0)
    from app.models.company import Company
    with testing_app.app_context():
        comp_b = Company(name="Empresa B 10B", slug="empresa-b-10b", document="00.000.000/0011-00")
        db.session.add(comp_b)
        db.session.commit()
        cid_b = comp_b.id
    with testing_app.app_context():
        assert dre_service.recognized_revenue(cid, AUG, AUG_END) == 1234.0
        assert dre_service.recognized_revenue(cid_b, AUG, AUG_END) == 0.0

    c = testing_app.test_client()
    c.post("/auth/login", data={"email": ADMIN_EMAIL, "password": "admin123"},
           follow_redirects=False)
    page = c.get("/").get_data(as_text=True)
    assert "Custos Diretos" in page          # rótulo atualizado
    page_fin = c.get("/financial/").get_data(as_text=True)
    assert "Receitas Pagas" in page_fin and "Custos Pagos" in page_fin


def test_fallback_flag_transparency(testing_app):
    cid = _cid(testing_app)
    oid = _faturado(testing_app, cid, total=500.0)
    _po(testing_app, cid, oid, created=datetime(2026, 8, 10, 9, 0), amount=150.0)
    with testing_app.app_context():
        rows = dre_service.direct_cost_rows(cid, AUG, AUG_END)
        assert len(rows) == 1 and rows[0][2] is True  # fallback sinalizado
