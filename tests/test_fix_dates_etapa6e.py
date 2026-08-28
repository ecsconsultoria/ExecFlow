"""tests/test_fix_dates_etapa6e.py — Correção de datas dos FRs 8/12 (Etapa 6E).

Cobre: a função corrige paid_date apenas dos IDs autorizados (com guarda da
data anterior); transação única (falha em um registro → nada persiste);
nenhum outro campo/registro é alterado; parcela e SO intactos.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, datetime

import pytest

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.models.financial import FinancialRecord
from app.models.order import Order, OrderPayment
from app.models.user import User
from app.utils import now_br
from tools.fix_dates_etapa6e import fix_paid_dates, DateFixBlocked, FIX_IDS, OLD_DATE, NEW_DATE

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


def _seed_etapa6e_data(app, cid, *, fr8_date=OLD_DATE, fr12_date=OLD_DATE):
    """FRs com os MESMOS ids 8 e 12 e parcelas pagas em 02/06."""
    with app.app_context():
        client = Client(company_id=cid, name=f"6E {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-6E-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=27000.0,
                      payment_method="PIX", emission_date=date.today(),
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        frs = []
        for fid, amount in ((8, 13500.0), (12, 13500.0)):
            pmt = OrderPayment(order_id=order.id, installment_no=fid,
                               amount=amount, due_date=date.today(),
                               paid_at=datetime(2026, 6, 2, 20, 8),
                               paid_amount=amount, paid_by=1)
            db.session.add(pmt)
            db.session.flush()
            fr = FinancialRecord(id=fid, company_id=cid, type="revenue",
                                 amount=amount, status="pago",
                                 paid_date=fr8_date if fid == 8 else fr12_date,
                                 reference=f"order_payment:{pmt.id}")
            db.session.add(fr)
            frs.append(fr)
        db.session.commit()
        return frs[0].id, frs[1].id


def test_fix_dates_corrects_only_authorized(testing_app):
    cid = _cid(testing_app)
    _seed_etapa6e_data(testing_app, cid)

    with testing_app.app_context():
        # um FR extra com paid_date diferente não deve ser tocado
        extra = FinancialRecord(company_id=cid, type="revenue", amount=1.0,
                                status="pago", paid_date=OLD_DATE,
                                reference="order_payment:777111")
        db.session.add(extra)
        db.session.commit()

        results = fix_paid_dates(1)
        assert [r["id"] for r in results] == FIX_IDS
        assert db.session.get(FinancialRecord, 8).paid_date == NEW_DATE
        assert db.session.get(FinancialRecord, 12).paid_date == NEW_DATE
        assert db.session.get(FinancialRecord, extra.id).paid_date == OLD_DATE  # intocado


def test_fix_dates_guards_and_rollback(testing_app):
    cid = _cid(testing_app)
    _seed_etapa6e_data(testing_app, cid, fr12_date=date(2026, 5, 30))  # id12 com data inesperada

    with testing_app.app_context():
        with pytest.raises(DateFixBlocked):
            fix_paid_dates(1)
        db.session.rollback()
        # transação única: NENHUM dos dois foi alterado
        assert db.session.get(FinancialRecord, 8).paid_date == OLD_DATE
        assert db.session.get(FinancialRecord, 12).paid_date == date(2026, 5, 30)


def test_fix_dates_preserves_everything_else(testing_app):
    cid = _cid(testing_app)
    _seed_etapa6e_data(testing_app, cid)

    with testing_app.app_context():
        fr8 = db.session.get(FinancialRecord, 8)
        before = {k: getattr(fr8, k) for k in
                  ("amount", "status", "reference", "company_id", "emission_date", "due_date")}
        pid8 = int(fr8.reference.split(":")[1])
        pmt_before = (db.session.get(OrderPayment, pid8).paid_at,
                      db.session.get(OrderPayment, pid8).paid_amount)

        fix_paid_dates(1)

        fr8 = db.session.get(FinancialRecord, 8)
        after = {k: getattr(fr8, k) for k in
                 ("amount", "status", "reference", "company_id", "emission_date", "due_date")}
        assert after == before                      # nada além de paid_date mudou
        pmt_after = (db.session.get(OrderPayment, pid8).paid_at,
                     db.session.get(OrderPayment, pid8).paid_amount)
        assert pmt_after == pmt_before              # parcela intocada
        order = db.session.get(OrderPayment, pid8).order
        assert order.total_amount == 27000.0 and order.status == "faturado"  # SO intocado
