"""tests/test_order_save.py — Regressão do fluxo Salvar do SO (save-all).

Bug reportado: após abrir o pedido, alterar o campo Faturamento (billing_type)
e clicar em Salvar não atualizava o campo. Cobre billing_type + demais campos
do cabeçalho. App próprio com TestingConfig (sqlite :memory:).
"""
import uuid
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.company import Company
from app.models.order import Order, OrderItem, OrderPayment
from app.models.payment_receipt import PaymentReceipt
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.financial import FinancialRecord
from app.models.user import User

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (PaymentReceipt, OrderPayment, OrderItem, Order,
                      POPayment, PurchaseOrder, FinancialRecord, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302)
    return c


def _seed_order(app, status="aberto"):
    with app.app_context():
        company = Company.query.first()
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        client = Client(company_id=company.id, name="Cliente Save")
        db.session.add(client)
        db.session.flush()
        order = Order(
            company_id=company.id, client_id=client.id,
            number=f"SO-TEST-{uuid.uuid4().hex[:8]}",
            status=status,
            client_name=client.name,
            language="pt", billing_type="recibo",
            total_amount=1000.0,
            payment_method="PIX", payment_terms="À vista",
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
        db.session.commit()
        return order.id


def test_save_all_updates_billing_type(testing_app):
    oid = _seed_order(testing_app, status="aberto")
    c = _login(testing_app)
    r = c.post(f"/orders/{oid}/save-all", data={
        "action": "save",
        "billing_type": "nf",
        "emission_date": date.today().isoformat(),
        "payment_method": "TRANSFERÊNCIA",
        "payment_terms": "15 dias",
    }, follow_redirects=False)
    assert r.status_code == 302
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        assert order.billing_type == "nf"
        assert order.payment_method == "TRANSFERÊNCIA"
        assert order.payment_terms == "15 dias"


def test_save_all_keeps_billing_when_invalid(testing_app):
    oid = _seed_order(testing_app, status="aberto")
    c = _login(testing_app)
    r = c.post(f"/orders/{oid}/save-all", data={
        "action": "save",
        "billing_type": "valor_invalido",
    }, follow_redirects=False)
    assert r.status_code == 302
    with testing_app.app_context():
        # Valor inválido é ignorado — o cadastro anterior permanece
        assert db.session.get(Order, oid).billing_type == "recibo"


def test_inline_client_creation_saves_celular_to_whatsapp(testing_app):
    # O campo "Celular" do modal de novo cliente grava em Client.whatsapp
    c = _login(testing_app)
    r = c.post("/clients/api/new", json={
        "name": "Cliente Inline", "contact": "Fulana",
        "whatsapp": "+55 11 99999-0000", "email": "fulana@example.com",
    })
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["whatsapp"] == "+55 11 99999-0000"
    assert d["contact"] == "Fulana"
    assert d["email"] == "fulana@example.com"
    with testing_app.app_context():
        cli = Client.query.filter_by(name="Cliente Inline").first()
        assert cli is not None
        assert cli.whatsapp == "+55 11 99999-0000"  # celular no campo móvel
        assert cli.phone is None


def test_inline_client_creation_legacy_phone_field(testing_app):
    # Compatibilidade: "phone" antigo ainda cai no whatsapp
    c = _login(testing_app)
    r = c.post("/clients/api/new", json={
        "name": "Cliente Legacy", "phone": "+55 11 98888-1111",
    })
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and d["whatsapp"] == "+55 11 98888-1111"
    with testing_app.app_context():
        cli = Client.query.filter_by(name="Cliente Legacy").first()
        assert cli.whatsapp == "+55 11 98888-1111"
