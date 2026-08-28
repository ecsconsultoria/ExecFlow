"""tests/test_financial_catalog_etapa3a.py — Categorias financeiras e centros de custo.

Cobre:
  * CRUD de categorias (criar/editar/ativar/desativar) e hierarquia (parent);
  * CRUD de centros de custo;
  * Isolamento por company_id (empresa A não acessa estruturas da empresa B);
  * Colunas FK novas em financial_records (nullable, sem efeito em históricos);
  * Seed idempotente;
  * Regressão: SO/PO/parcelas/FR não são tocados pelas rotas do catálogo.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.user import User
from app.utils import now_br
from tools.seed_financial_catalog import seed_company

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        # Company NÃO é deletada (referenciada por users e cadastros do seed)
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


def _admin_cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


# ─────────────────────────────────────────────────────────────────────────────
# Categorias — CRUD + hierarquia
# ─────────────────────────────────────────────────────────────────────────────

def test_category_create_edit_toggle(testing_app):
    c = _login(testing_app)
    r = c.post("/financial/categories/new", data={
        "name": "Manutenção Teste", "type": "expense", "description": "d",
    }, follow_redirects=True)
    assert r.status_code == 200 and "Manutenção Teste" in r.get_data(as_text=True)

    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        cat = FinancialCategory.query.filter_by(company_id=cid, name="Manutenção Teste").first()
        assert cat is not None and cat.active is True and cat.type == "expense"
        cat_id = cat.id

    r = c.post(f"/financial/categories/{cat_id}/edit", data={
        "name": "Manutenção Renomeada", "type": "expense", "description": "novo",
    }, follow_redirects=True)
    assert r.status_code == 200 and "Manutenção Renomeada" in r.get_data(as_text=True)

    r = c.post(f"/financial/categories/{cat_id}/toggle", follow_redirects=True)
    with testing_app.app_context():
        cat = db.session.get(FinancialCategory, cat_id)
        assert cat.active is False

    r = c.post(f"/financial/categories/{cat_id}/toggle", follow_redirects=True)
    with testing_app.app_context():
        assert db.session.get(FinancialCategory, cat_id).active is True


def test_category_hierarchy(testing_app):
    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        root = FinancialCategory(company_id=cid, name="Despesas Teste", type="expense", active=True)
        db.session.add(root)
        db.session.flush()
        child = FinancialCategory(company_id=cid, name="Aluguel Teste", type="expense",
                                  parent_id=root.id, active=True)
        db.session.add(child)
        db.session.commit()
        assert child.parent_id == root.id
        assert child in root.children

    # rota também aceita parent
    c = _login(testing_app)
    r = c.post("/financial/categories/new", data={
        "name": "Filha via rota", "type": "expense", "parent_id": str(root.id),
    }, follow_redirects=True)
    assert r.status_code == 200
    with testing_app.app_context():
        f = FinancialCategory.query.filter_by(company_id=cid, name="Filha via rota").first()
        assert f is not None and f.parent_id == root.id


# ─────────────────────────────────────────────────────────────────────────────
# Centros de custo — CRUD
# ─────────────────────────────────────────────────────────────────────────────

def test_cost_center_create_edit_toggle(testing_app):
    c = _login(testing_app)
    r = c.post("/financial/cost-centers/new", data={"name": "Centro Teste"},
               follow_redirects=True)
    assert r.status_code == 200 and "Centro Teste" in r.get_data(as_text=True)

    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        cc = CostCenter.query.filter_by(company_id=cid, name="Centro Teste").first()
        assert cc is not None and cc.active is True
        cc_id = cc.id

    r = c.post(f"/financial/cost-centers/{cc_id}/edit", data={"name": "Centro Renomeado"},
               follow_redirects=True)
    assert r.status_code == 200 and "Centro Renomeado" in r.get_data(as_text=True)

    c.post(f"/financial/cost-centers/{cc_id}/toggle", follow_redirects=True)
    with testing_app.app_context():
        assert db.session.get(CostCenter, cc_id).active is False


# ─────────────────────────────────────────────────────────────────────────────
# Isolamento por company_id
# ─────────────────────────────────────────────────────────────────────────────

def test_company_isolation_categories(testing_app):
    cid_a = _admin_cid(testing_app)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B Teste", slug="empresa-b-teste", document="00.000.000/0002-00")
        db.session.add(comp_b)
        db.session.flush()
        cat_b = FinancialCategory(company_id=comp_b.id, name="Categoria da B",
                                  type="expense", active=True)
        db.session.add(cat_b)
        db.session.commit()
        cat_b_id = cat_b.id

    c = _login(testing_app)  # admin pertence à empresa A
    r = c.get(f"/financial/categories/{cat_b_id}/edit")
    assert r.status_code == 404
    r = c.post(f"/financial/categories/{cat_b_id}/toggle")
    assert r.status_code == 404
    with testing_app.app_context():
        assert db.session.get(FinancialCategory, cat_b_id).active is True  # intocado


def test_company_isolation_cost_centers(testing_app):
    with testing_app.app_context():
        comp_b = Company(name="Empresa B2 Teste", slug="empresa-b2-teste", document="00.000.000/0003-00")
        db.session.add(comp_b)
        db.session.flush()
        cc_b = CostCenter(company_id=comp_b.id, name="Centro da B", active=True)
        db.session.add(cc_b)
        db.session.commit()
        cc_b_id = cc_b.id

    c = _login(testing_app)
    assert c.get(f"/financial/cost-centers/{cc_b_id}/edit").status_code == 404
    assert c.post(f"/financial/cost-centers/{cc_b_id}/toggle").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# FK novas em FinancialRecord + regressão de históricos
# ─────────────────────────────────────────────────────────────────────────────

def test_financial_record_new_fk_columns(testing_app):
    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        cols = {c.name: c for c in FinancialRecord.__table__.columns}
        assert "financial_category_id" in cols and cols["financial_category_id"].nullable
        assert "cost_center_id" in cols and cols["cost_center_id"].nullable
        fr = FinancialRecord(company_id=cid, type="cost", amount=1.0)
        db.session.add(fr)
        db.session.commit()
        assert fr.financial_category_id is None and fr.cost_center_id is None


def test_catalog_routes_do_not_touch_transactional_data(testing_app):
    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        client = Client(company_id=cid, name="Cliente Regressão")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-REG-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=1000.0,
                      payment_method="PIX", emission_date=date.today(),
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        pmt = OrderPayment(order_id=order.id, installment_no=1, amount=1000.0,
                           due_date=date.today(), paid_amount=0.0)
        db.session.add(pmt)
        db.session.flush()
        fr = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                             amount=1000.0, status="pendente",
                             reference=f"order_payment:{pmt.id}")
        db.session.add(fr)
        db.session.commit()
        oid, pid, fid = order.id, pmt.id, fr.id

    c = _login(testing_app)
    c.get("/financial/categories")
    c.get("/financial/cost-centers")

    with testing_app.app_context():
        o = db.session.get(Order, oid)
        p = db.session.get(OrderPayment, pid)
        f = db.session.get(FinancialRecord, fid)
        assert o.status == "faturado" and o.total_amount == 1000.0
        assert p.paid_amount == 0.0 and p.amount == 1000.0
        assert f.amount == 1000.0 and f.status == "pendente" and f.deleted_at is None


# ─────────────────────────────────────────────────────────────────────────────
# Seed idempotente
# ─────────────────────────────────────────────────────────────────────────────

def test_seed_financial_catalog_idempotent(testing_app):
    cid = _admin_cid(testing_app)
    with testing_app.app_context():
        first = seed_company(cid)
        assert first["skipped"] is False
        assert first["categories"] == 48
        assert first["cost_centers"] == 7
        db.session.commit()

        second = seed_company(cid)
        assert second["skipped"] is True  # segunda execução não duplica

        total_cats = FinancialCategory.query.filter_by(company_id=cid).count()
        total_ccs = CostCenter.query.filter_by(company_id=cid).count()
        assert total_cats == 48 and total_ccs == 7
