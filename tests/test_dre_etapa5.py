"""tests/test_dre_etapa5.py — DRE Gerencial por competência (Etapa 5).

Cobre: receita só com faturamento (recebimento não altera); custo direto válido
+ vinculado (rascunho/cancelado/sem-SO fora); competência com prioridade
(service_date → delivery_date → created_at); despesa por emissão (cancelada
fora); margem e resultado; período; multiempresa; tela somente leitura.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, datetime

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.order import Order, OrderPayment
from app.models.purchase_order import PurchaseOrder, POPayment, POItem
from app.models.user import User
from app.services import dre_service
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"

AUG = date(2026, 8, 1)
AUG_END = date(2026, 8, 31)
JUL = date(2026, 7, 1)
JUL_END = date(2026, 7, 31)


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        # Ordem filho-primeiro respeitando as FKs (PO -> Order, POPayment/POItem -> PO)
        for model in (FinancialRecord, OrderPayment, POItem, POPayment,
                      PurchaseOrder, Order, CostCenter, FinancialCategory, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302)
    return c


def _cid_of(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _seed_order(app, cid, *, status, invoiced_at=None, total=1000.0, with_payment=False):
    with app.app_context():
        client = Client(company_id=cid, name=f"Cliente {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-DRE-{uuid.uuid4().hex[:8]}", status=status,
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=total,
                  payment_method="PIX", emission_date=date.today(),
                  invoiced_at=invoiced_at, created_by=1)
        db.session.add(o)
        db.session.flush()
        pid = None
        if with_payment:
            pmt = OrderPayment(order_id=o.id, installment_no=1, amount=total,
                               due_date=date.today(), paid_amount=0.0)
            db.session.add(pmt)
            db.session.flush()
            pid = pmt.id
        db.session.commit()
        return o.id, pid


def _seed_po(app, cid, *, status="aberto", order_id=None, created=None,
             service_date=None, delivery_date=None, amount=500.0):
    with app.app_context():
        po = PurchaseOrder(company_id=cid,
                           number=f"PO-DRE-{uuid.uuid4().hex[:8]}",
                           status=status, order_id=order_id, created_by=1)
        if created:
            po.created_at = created
        if delivery_date:
            po.delivery_date = delivery_date
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
# Receita
# ─────────────────────────────────────────────────────────────────────────────

def test_dre_revenue_rules(testing_app):
    cid = _cid_of(testing_app)
    _seed_order(testing_app, cid, status="faturado",
                invoiced_at=datetime(2026, 8, 15, 10, 0), total=1000.0)
    _seed_order(testing_app, cid, status="aberto", total=999.0)
    _seed_order(testing_app, cid, status="concluido", total=777.0)  # sem fatura
    oid, pid = _seed_order(testing_app, cid, status="faturado",
                           invoiced_at=datetime(2026, 8, 20, 10, 0),
                           total=500.0, with_payment=True)

    with testing_app.app_context():
        assert dre_service.recognized_revenue(cid, AUG, AUG_END) == 1500.0

        # recebimento NÃO altera a receita reconhecida
        from app.services.order_service import baixa
        pmt = db.session.get(OrderPayment, pid)
        baixa(pmt, 500.0, 1, paid_date=date(2026, 8, 21))
        assert dre_service.recognized_revenue(cid, AUG, AUG_END) == 1500.0


# ─────────────────────────────────────────────────────────────────────────────
# Custos diretos e competência
# ─────────────────────────────────────────────────────────────────────────────

def test_dre_cost_rules_and_competence(testing_app):
    cid = _cid_of(testing_app)
    oid, _ = _seed_order(testing_app, cid, status="faturado",
                         invoiced_at=datetime(2026, 8, 15, 10, 0), total=3000.0)

    # competência: PO criada em julho, serviço executado em agosto
    _seed_po(testing_app, cid, order_id=oid, created=datetime(2026, 7, 10, 9, 0),
             service_date=date(2026, 8, 5), amount=700.0)
    # fallback: sem service_date/delivery → competência = created_at (julho)
    _seed_po(testing_app, cid, order_id=oid, created=datetime(2026, 7, 12, 9, 0),
             amount=300.0)
    # inválidas: rascunho / cancelada / sem SO
    _seed_po(testing_app, cid, status="rascunho", order_id=oid, amount=900.0)
    _seed_po(testing_app, cid, status="cancelado", order_id=oid, amount=800.0)
    _seed_po(testing_app, cid, status="pago", order_id=None, amount=13500.0)

    with testing_app.app_context():
        aug_rows = dre_service.direct_cost_rows(cid, AUG, AUG_END)
        assert len(aug_rows) == 1 and aug_rows[0][1] == date(2026, 8, 5)
        assert dre_service.direct_costs(cid, AUG, AUG_END) == 700.0

        jul_rows = dre_service.direct_cost_rows(cid, JUL, JUL_END)
        assert len(jul_rows) == 1 and jul_rows[0][2] is True  # usou fallback
        assert dre_service.direct_costs(cid, JUL, JUL_END) == 300.0

        uncl = dre_service.unclassified_cost_rows(cid)
        assert len(uncl) == 1 and uncl[0].amount == 13500.0  # CUSTO NÃO CLASSIFICADO


# ─────────────────────────────────────────────────────────────────────────────
# Despesas, margem e resultado
# ─────────────────────────────────────────────────────────────────────────────

def test_dre_expenses_margin_result(testing_app):
    cid = _cid_of(testing_app)
    with testing_app.app_context():
        cat = FinancialCategory(company_id=cid, name="Despesas Administrativas",
                                type="expense", active=True)
        db.session.add(cat)
        db.session.flush()
        cc = CostCenter(company_id=cid, name="Administrativo", active=True)
        db.session.add(cc)
        db.session.flush()
        paga = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Aluguel competência", amount=200.0,
                               status="pago", emission_date=date(2026, 8, 5),
                               paid_date=date(2026, 9, 10), due_date=date(2026, 9, 10),
                               financial_category_id=cat.id, cost_center_id=cc.id,
                               reference="expense:555001")
        pend = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Contabilidade pendente", amount=100.0,
                               status="pendente", emission_date=date(2026, 8, 6),
                               due_date=date(2026, 9, 6),
                               financial_category_id=cat.id, cost_center_id=cc.id,
                               reference="expense:555002")
        canc = FinancialRecord(company_id=cid, type="expense", category="outro",
                               description="Cancelada", amount=50.0,
                               status="cancelado", emission_date=date(2026, 8, 7),
                               financial_category_id=cat.id, cost_center_id=cc.id,
                               reference="expense:555003")
        db.session.add_all([paga, pend, canc])
        db.session.commit()

    _seed_order(testing_app, cid, status="faturado",
                invoiced_at=datetime(2026, 8, 15, 10, 0), total=1000.0)
    _seed_po(testing_app, cid, order_id=None, status="pago", amount=0.0)  # sem-SO não afeta aqui
    oid, _ = _seed_order(testing_app, cid, status="faturado",
                         invoiced_at=datetime(2026, 8, 16, 10, 0), total=0.0)
    with testing_app.app_context():
        o = db.session.get(Order, oid)
        o.total_amount = 0.0
        db.session.commit()

    with testing_app.app_context():
        rev = dre_service.recognized_revenue(cid, AUG, AUG_END)
        assert rev == 1000.0
        # despesa entra por competência (emissão), inclusive PENDENTE; cancelada fora
        groups = dre_service.general_expenses_by_group(cid, AUG, AUG_END)
        assert groups["Despesas Administrativas"] == 300.0
        assert dre_service.general_expenses(cid, AUG, AUG_END) == 300.0
        # margem e resultado (sem custos diretos neste período)
        assert dre_service.gross_margin(cid, AUG, AUG_END) == 1000.0
        assert dre_service.operating_result(cid, AUG, AUG_END) == 700.0


# ─────────────────────────────────────────────────────────────────────────────
# Multiempresa + tela somente leitura
# ─────────────────────────────────────────────────────────────────────────────

def test_dre_multitenant_and_screen(testing_app):
    cid = _cid_of(testing_app)
    _seed_order(testing_app, cid, status="faturado",
                invoiced_at=datetime(2026, 8, 15, 10, 0), total=1000.0)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B DRE", slug="empresa-b-dre", document="00.000.000/0008-00")
        db.session.add(comp_b)
        db.session.flush()
        client = Client(company_id=comp_b.id, name="Cliente B")
        db.session.add(client)
        db.session.flush()
        o_b = Order(company_id=comp_b.id, client_id=client.id,
                    number="SO-B-DRE-1", status="faturado",
                    client_name=client.name, contact_name="", email="", celular="",
                    language="pt", billing_type="recibo", total_amount=9999.0,
                    payment_method="PIX", emission_date=date.today(),
                    invoiced_at=datetime(2026, 8, 15, 10, 0), created_by=1)
        db.session.add(o_b)
        db.session.commit()

    with testing_app.app_context():
        assert dre_service.recognized_revenue(cid, AUG, AUG_END) == 1000.0  # só empresa A

    c = _login(testing_app)
    page = c.get("/financial/dre").get_data(as_text=True)
    assert "RECEITA DE SERVIÇOS" in page and "MARGEM BRUTA" in page
    assert "SO-B-DRE-1" not in page          # sem vazamento
    assert "form method=\"post\"" not in page  # somente leitura
    assert c.post("/financial/dre").status_code == 405
