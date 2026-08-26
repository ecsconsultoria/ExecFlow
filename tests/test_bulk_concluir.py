"""tests/test_bulk_concluir.py — Bulk Concluir em SO (faturado → concluído) e PO (faturado → pago).

A ação dá baixa nas parcelas pendentes assumindo a data do dia e conclui
vários pedidos simultaneamente. App próprio com TestingConfig (sqlite :memory:).
"""
import uuid
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.financial import FinancialRecord
from app.models.order import Order, OrderItem, OrderPayment
from app.models.payment_receipt import PaymentReceipt
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.rbac import Role
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
        # Ordem filho-primeiro respeitando as FKs
        for model in (PaymentReceipt, OrderPayment, OrderItem, Order,
                      POPayment, PurchaseOrder, FinancialRecord, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302), f"login {email} falhou ({r.status_code})"
    return c


def _seed_order(app, *, status="faturado", installments=2, paid=0,
                with_payments=True):
    """Cria SO com parcelas; `paid` = quantas já estão quitadas."""
    with app.app_context():
        company = Company.query.first()
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        client = Client(company_id=company.id, name="Cliente Bulk")
        db.session.add(client)
        db.session.flush()
        order = Order(
            company_id=company.id, client_id=client.id,
            number=f"SO-TEST-{uuid.uuid4().hex[:8]}",
            status=status,
            client_name=client.name, contact_name="", email="", celular="",
            language="pt", billing_type="recibo",
            total_amount=1000.0,
            payment_method="PIX",
            emission_date=date.today(),
            created_by=admin.id,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            order_id=order.id, description="Executive Transportation",
            quantity=1, unit_price=1000.0, total_price=1000.0,
            service_date=date.today(),
        ))
        pids = []
        if with_payments:
            inst_amount = round(1000.0 / installments, 2)
            for i in range(1, installments + 1):
                is_paid = i <= paid
                pmt = OrderPayment(
                    order_id=order.id, installment_no=i, amount=inst_amount,
                    due_date=date.today(),
                    paid_at=now_br() if is_paid else None,
                    paid_amount=inst_amount if is_paid else 0.0,
                    paid_by=admin.id if is_paid else None,
                )
                db.session.add(pmt)
                db.session.flush()
                pids.append(pmt.id)
                if is_paid:
                    db.session.add(FinancialRecord(
                        company_id=company.id, type="revenue",
                        category="receita_servico",
                        description=f"{order.number} — parcela {i}/{installments}",
                        amount=inst_amount, status="pago", paid_date=date.today(),
                        payment_method="PIX", reference=f"order_payment:{pmt.id}",
                    ))
        db.session.commit()
        return order.id


def _seed_po(app, *, status="faturado", installments=2, paid=0,
             with_payments=True):
    """Cria PO com parcelas; `paid` = quantas já estão quitadas."""
    with app.app_context():
        company = Company.query.first()
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        po = PurchaseOrder(
            company_id=company.id,
            number=f"PO-TEST-{uuid.uuid4().hex[:8]}",
            status=status,
            created_by=admin.id,
            amount=1000.0,
        )
        db.session.add(po)
        db.session.flush()
        pids = []
        if with_payments:
            inst_amount = round(1000.0 / installments, 2)
            for i in range(1, installments + 1):
                is_paid = i <= paid
                pmt = POPayment(
                    po_id=po.id, installment_no=i, amount=inst_amount,
                    due_date=date.today(),
                    paid_at=now_br() if is_paid else None,
                    paid_amount=inst_amount if is_paid else 0.0,
                    paid_by=admin.id if is_paid else None,
                )
                db.session.add(pmt)
                db.session.flush()
                pids.append(pmt.id)
                if is_paid:
                    db.session.add(FinancialRecord(
                        company_id=company.id, type="cost",
                        category="custo_fornecedor",
                        description=f"{po.number} — parcela {i}/{installments}",
                        amount=inst_amount, status="pago", paid_date=date.today(),
                        payment_method="PIX", reference=f"po_payment:{pmt.id}",
                    ))
        db.session.commit()
        return po.id


# ─────────────────────────────────────────────────────────────────────────────
# Sales Order
# ─────────────────────────────────────────────────────────────────────────────

def test_so_bulk_concluir_settles_and_completes(testing_app):
    oid1 = _seed_order(testing_app, status="faturado", installments=2, paid=0)
    oid2 = _seed_order(testing_app, status="faturado", installments=2, paid=0)
    c = _login(testing_app)
    r = c.post("/orders/bulk-concluir", json={"ids": [oid1, oid2]})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and d["concluidos"] == 2 and d["falhas"] == 0

    today = now_br().date()
    with testing_app.app_context():
        for oid in (oid1, oid2):
            order = db.session.get(Order, oid)
            assert order.status == "concluido"
            for pmt in order.payments:
                assert pmt.is_paid
                assert pmt.paid_at.date() == today  # baixa com a data do dia
            frs = FinancialRecord.query.filter(
                FinancialRecord.reference.like(f"order_payment:%"),
                FinancialRecord.description.like(f"{order.number}%"),
            ).all()
            assert frs and all(fr.status == "pago" and fr.paid_date == today for fr in frs)


def test_so_bulk_concluir_skips_non_faturado(testing_app):
    oid_aberto = _seed_order(testing_app, status="aberto", installments=2, paid=0)
    oid_fat = _seed_order(testing_app, status="faturado", installments=2, paid=0)
    c = _login(testing_app)
    r = c.post("/orders/bulk-concluir", json={"ids": [oid_aberto, oid_fat]})
    d = r.get_json()
    assert d["concluidos"] == 1 and d["falhas"] == 1
    with testing_app.app_context():
        assert db.session.get(Order, oid_aberto).status == "aberto"
        assert db.session.get(Order, oid_fat).status == "concluido"


def test_so_bulk_concluir_requires_parcels(testing_app):
    oid = _seed_order(testing_app, status="faturado", with_payments=False)
    c = _login(testing_app)
    r = c.post("/orders/bulk-concluir", json={"ids": [oid]})
    d = r.get_json()
    assert d["concluidos"] == 0 and d["falhas"] == 1
    assert any("sem parcelas" in e for e in d["erros"])


def test_so_bulk_concluir_permission_denied(testing_app):
    oid = _seed_order(testing_app, status="faturado", installments=2, paid=0)
    with testing_app.app_context():
        company = Company.query.first()
        viewer = User.query.filter_by(email="bulk_viewer@test.local").first()
        if not viewer:
            viewer = User(company_id=company.id, name="Bulk Viewer",
                          email="bulk_viewer@test.local")
            viewer.set_password("TestRBAC123!")
            db.session.add(viewer)
            db.session.flush()
            role = Role.query.filter_by(code="VIEWER").first()
            if role:
                viewer.roles.append(role)
            db.session.commit()
    c = _login(testing_app, email="bulk_viewer@test.local", password="TestRBAC123!")
    r = c.post("/orders/bulk-concluir", json={"ids": [oid]})
    assert r.status_code == 403
    with testing_app.app_context():
        assert db.session.get(Order, oid).status == "faturado"


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Order
# ─────────────────────────────────────────────────────────────────────────────

def test_po_bulk_concluir_settles_and_completes(testing_app):
    pid = _seed_po(testing_app, status="faturado", installments=2, paid=0)
    c = _login(testing_app)
    r = c.post("/po/bulk-concluir", json={"ids": [pid]})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and d["concluidos"] == 1 and d["falhas"] == 0

    today = now_br().date()
    with testing_app.app_context():
        po = db.session.get(PurchaseOrder, pid)
        assert po.status == "pago"  # rótulo "Concluído"
        for pmt in po.payments:
            assert pmt.is_paid
            assert pmt.paid_at.date() == today


def test_po_bulk_concluir_skips_non_faturado(testing_app):
    pid_fat = _seed_po(testing_app, status="faturado", installments=2, paid=0)
    pid_aberto = _seed_po(testing_app, status="aberto", installments=2, paid=0)
    c = _login(testing_app)
    r = c.post("/po/bulk-concluir", json={"ids": [pid_fat, pid_aberto]})
    d = r.get_json()
    assert d["concluidos"] == 1 and d["falhas"] == 1
    with testing_app.app_context():
        assert db.session.get(PurchaseOrder, pid_fat).status == "pago"
        assert db.session.get(PurchaseOrder, pid_aberto).status == "aberto"
