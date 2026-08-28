"""tests/test_restore_etapa6c.py — Restauração controlada Etapa 6C (allowlist).

Cobre: somente IDs autorizados são restaurados; registro bloqueado (sem
pagamento) fica deletado e não interrompe os demais; correção de status
explicitamente autorizada (caso id 5); proibidos permanecem soft-deletados;
SO/PO/pagamentos intactos.

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
from tools.restore_etapa6c import restore_records

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


def _seed_deleted_frs(app, cid):
    """Cria FRs soft-deletados: 1 pago válido, 1 pendente-com-paid (id5-like),
    1 não pago (proibido) e 1 órfão (proibido)."""
    with app.app_context():
        client = Client(company_id=cid, name=f"C6 {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        order = Order(company_id=cid, client_id=client.id,
                      number=f"SO-6C-{uuid.uuid4().hex[:8]}", status="faturado",
                      client_name=client.name, contact_name="", email="", celular="",
                      language="pt", billing_type="recibo", total_amount=1000.0,
                      payment_method="PIX", emission_date=date.today(),
                      invoiced_at=now_br(), created_by=1)
        db.session.add(order)
        db.session.flush()
        pmt = OrderPayment(order_id=order.id, installment_no=1, amount=1000.0,
                           due_date=date.today(), paid_at=now_br(),
                           paid_amount=1000.0, paid_by=1)
        db.session.add(pmt)
        db.session.flush()
        paid = FinancialRecord(company_id=cid, type="revenue", amount=1000.0,
                               status="pago", paid_date=date.today(),
                               reference=f"order_payment:{pmt.id}")
        id5like = FinancialRecord(company_id=cid, type="revenue", amount=1000.0,
                                  status="pendente", paid_date=date.today(),
                                  reference=f"order_payment:{pmt.id + 1}")
        # parcela paga para o id5like (outra parcela do mesmo SO)
        pmt2 = OrderPayment(order_id=order.id, installment_no=2, amount=1000.0,
                            due_date=date.today(), paid_at=now_br(),
                            paid_amount=1000.0, paid_by=1)
        db.session.add(pmt2)
        db.session.flush()
        id5like.reference = f"order_payment:{pmt2.id}"
        unpaid = FinancialRecord(company_id=cid, type="revenue", amount=500.0,
                                 status="pendente", reference="order_payment:888777")
        orphan = FinancialRecord(company_id=cid, type="revenue", amount=300.0,
                                 status="pendente", reference="order_payment:999999")
        db.session.add_all([paid, id5like, unpaid, orphan])
        db.session.flush()
        for fr in (paid, id5like, unpaid, orphan):
            fr.soft_delete()
        db.session.commit()
        return {"paid": paid.id, "id5like": id5like.id,
                "unpaid": unpaid.id, "orphan": orphan.id}


def test_restore_etapa6c_allowlist_only(testing_app):
    cid = _cid(testing_app)
    ids = _seed_deleted_frs(testing_app, cid)

    with testing_app.app_context():
        # allowlist = pago + id5like (com correção de status); proibidos fora da lista
        results = restore_records([ids["paid"], ids["id5like"]], {ids["id5like"]}, 1)
        assert [r["id"] for r in results if r["ok"]] == [ids["paid"], ids["id5like"]]

        paid = db.session.get(FinancialRecord, ids["paid"])
        assert paid.deleted_at is None and paid.status == "pago"
        assert paid.amount == 1000.0 and paid.reference.startswith("order_payment:")

        id5like = db.session.get(FinancialRecord, ids["id5like"])
        assert id5like.deleted_at is None
        assert id5like.status == "pago"  # correção autorizada (caso id 5)

        # proibidos permanecem soft-deletados
        assert db.session.get(FinancialRecord, ids["unpaid"]).deleted_at is not None
        assert db.session.get(FinancialRecord, ids["orphan"]).deleted_at is not None


def test_restore_etapa6c_blocked_does_not_stop_others(testing_app):
    cid = _cid(testing_app)
    ids = _seed_deleted_frs(testing_app, cid)

    with testing_app.app_context():
        results = restore_records([ids["paid"], ids["unpaid"], ids["orphan"]], set(), 1)
        ok_ids = [r["id"] for r in results if r["ok"]]
        blocked = [r["id"] for r in results if not r["ok"]]
        assert ok_ids == [ids["paid"]]                 # só o válido restaurado
        assert sorted(blocked) == sorted([ids["unpaid"], ids["orphan"]])
        for fid in (ids["unpaid"], ids["orphan"]):
            assert db.session.get(FinancialRecord, fid).deleted_at is not None


def test_restore_etapa6c_does_not_touch_so_payment(testing_app):
    cid = _cid(testing_app)
    ids = _seed_deleted_frs(testing_app, cid)
    with testing_app.app_context():
        restore_records([ids["paid"]], set(), 1)
        # SO e parcela intactos
        fr = db.session.get(FinancialRecord, ids["paid"])
        pid = int(fr.reference.split(":")[1])
        pmt = db.session.get(OrderPayment, pid)
        order = pmt.order
        assert order.total_amount == 1000.0 and order.status == "faturado"
        assert pmt.paid_amount == 1000.0 and pmt.paid_at is not None
