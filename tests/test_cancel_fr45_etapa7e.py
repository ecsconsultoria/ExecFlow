"""tests/test_cancel_fr45_etapa7e.py — Cancelamento controlado do FR45 (Etapa 7E).

Cobre: só o status muda (pendente → cancelado); registro preservado (sem
DELETE físico — valor/descrição/datas/company intactos); guarda bloqueia
status inesperado; AP deixa de contar o valor; SO/PO/pagamentos intactos.

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
from app.utils import now_br
from tools.cancel_fr45_etapa7e import cancel_fr45, CancelBlocked

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


def _seed_fr45(app, cid, *, status="pendente"):
    with app.app_context():
        fr = FinancialRecord(id=45, company_id=cid, type="cost",
                             category="custo_operacional",
                             description="Transfer GRU Airport x Itaim",
                             amount=200.0, status=status, due_date=date(2026, 7, 29))
        db.session.add(fr)
        db.session.commit()
        return fr.id


def test_cancel_fr45_status_only(testing_app):
    cid = _cid(testing_app)
    _seed_fr45(testing_app, cid)

    with testing_app.app_context():
        before = {k: getattr(db.session.get(FinancialRecord, 45), k) for k in
                  ("amount", "description", "due_date", "company_id",
                   "emission_date", "reference", "category")}
        r = cancel_fr45(1)
        assert r["before"] == "pendente" and r["after"] == "cancelado"

        fr = db.session.get(FinancialRecord, 45)
        assert fr is not None and fr.deleted_at is None  # SEM delete físico
        after = {k: getattr(fr, k) for k in
                 ("amount", "description", "due_date", "company_id",
                  "emission_date", "reference", "category")}
        assert after == before  # nada além do status mudou


def test_cancel_fr45_guards(testing_app):
    cid = _cid(testing_app)
    _seed_fr45(testing_app, cid, status="pago")
    with testing_app.app_context():
        with pytest.raises(CancelBlocked):
            cancel_fr45(1)
        db.session.rollback()
        assert db.session.get(FinancialRecord, 45).status == "pago"  # intocado


def test_cancel_fr45_ap_and_protected_data(testing_app):
    cid = _cid(testing_app)
    _seed_fr45(testing_app, cid)
    with testing_app.app_context():
        # um SO/parcela protegidos ao lado
        client = Client(company_id=cid, name=f"C7E {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-7E-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=900.0,
                      payment_method="PIX", emission_date=date.today(),
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        pmt = OrderPayment(order_id=order.id, installment_no=1, amount=900.0,
                           due_date=date.today(), paid_amount=0.0)
        db.session.add(pmt)
        db.session.commit()
        oid, pid = order.id, pmt.id

        cancel_fr45(1)

        # AP pendente deixa de incluir o FR45
        from sqlalchemy import func
        ap = (db.session.query(func.sum(FinancialRecord.amount))
              .filter(FinancialRecord.company_id == cid,
                      FinancialRecord.type.in_(["cost", "expense"]),
                      FinancialRecord.status == "pendente",
                      FinancialRecord.deleted_at.is_(None))
              .scalar() or 0.0)
        assert ap == 0.0  # só o FR45 existia como pendente
        # protegidos intactos
        assert db.session.get(Order, oid).total_amount == 900.0
        assert db.session.get(OrderPayment, pid).paid_amount == 0.0
