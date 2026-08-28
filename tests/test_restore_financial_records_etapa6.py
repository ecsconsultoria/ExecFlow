"""tests/test_restore_financial_records_etapa6.py — Restauração controlada (Etapa 6).

Cobre: restauração segura (pagamento válido/pago, sem duplicata) preservando
ID/valor/datas/status/reference/company; bloqueios (duplicata ativa, parcela
inexistente, não paga, valor divergente, reference fora do padrão); rollback
em falha de auditoria; SO/PO/pagamentos intactos.

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
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.user import User
from app.services.financial_service import (
    restore_financial_record, restore_and_audit, RestorationBlocked,
)
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (FinancialRecord, OrderPayment, Order, POPayment,
                      PurchaseOrder, Client):
            model.query.delete()
        db.session.commit()
    yield


def _cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _seed_order_paid(app, cid, total=500.0):
    with app.app_context():
        client = Client(company_id=cid, name=f"Cliente R6 {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-R6-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=total,
                  payment_method="PIX", emission_date=date.today(),
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        pmt = OrderPayment(order_id=o.id, installment_no=1, amount=total,
                           due_date=date.today(), paid_at=now_br(),
                           paid_amount=total, paid_by=1)
        db.session.add(pmt)
        db.session.flush()
        fr = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                             amount=total, status="pago", paid_date=date.today(),
                             reference=f"order_payment:{pmt.id}")
        db.session.add(fr)
        db.session.commit()
        return o.id, pmt.id, fr.id


# ─────────────────────────────────────────────────────────────────────────────
# Restauração segura — preserva tudo
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_safe_preserves_everything(testing_app):
    cid = _cid(testing_app)
    oid, pid, fid = _seed_order_paid(testing_app, cid, total=500.0)

    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        fr.soft_delete()
        db.session.commit()
        before = {k: getattr(fr, k) for k in ("id", "amount", "status", "paid_date",
                                              "reference", "company_id", "emission_date")}
        assert fr.deleted_at is not None

        restored = restore_financial_record(fid, cid)
        assert restored.id == before["id"]
        assert restored.amount == before["amount"]
        assert restored.status == before["status"]
        assert restored.paid_date == before["paid_date"]
        assert restored.reference == before["reference"]
        assert restored.company_id == before["company_id"]
        assert restored.deleted_at is None

        # SO / parcela / pagamento intactos
        o = db.session.get(Order, oid)
        p = db.session.get(OrderPayment, pid)
        assert o.status == "faturado" and o.total_amount == 500.0
        assert p.paid_amount == 500.0 and p.paid_at is not None
        db.session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Bloqueios
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_blocked_active_duplicate(testing_app):
    cid = _cid(testing_app)
    _, pid, _ = _seed_order_paid(testing_app, cid, total=500.0)
    with testing_app.app_context():
        pmt = db.session.get(OrderPayment, pid)
        old = FinancialRecord.query.filter_by(reference=f"order_payment:{pid}").first()
        old.soft_delete()
        active = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                                 amount=500.0, status="pago", paid_date=date.today(),
                                 reference=f"order_payment:{pid}")
        db.session.add(active)
        db.session.commit()
        with pytest.raises(RestorationBlocked) as e:
            restore_financial_record(old.id, cid)
        assert "Duplicidade" in str(e.value)
        db.session.rollback()


def test_restore_blocked_unpaid(testing_app):
    cid = _cid(testing_app)
    with testing_app.app_context():
        client = Client(company_id=cid, name="Cliente NP")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-NP-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=300.0,
                  payment_method="PIX", emission_date=date.today(),
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        pmt = OrderPayment(order_id=o.id, installment_no=1, amount=300.0,
                           due_date=date.today(), paid_amount=0.0)
        db.session.add(pmt)
        db.session.flush()
        fr = FinancialRecord(company_id=cid, type="revenue", category="receita_servico",
                             amount=300.0, status="pendente",
                             reference=f"order_payment:{pmt.id}")
        db.session.add(fr)
        db.session.flush()
        fr.soft_delete()
        db.session.commit()
        with pytest.raises(RestorationBlocked) as e:
            restore_financial_record(fr.id, cid)
        assert "não paga" in str(e.value)
        assert db.session.get(FinancialRecord, fr.id).deleted_at is not None
        db.session.rollback()


def test_restore_blocked_value_mismatch_and_missing_parcel(testing_app):
    cid = _cid(testing_app)
    _, pid, fid = _seed_order_paid(testing_app, cid, total=500.0)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        fr.soft_delete()
        fr.amount = 999.0  # divergência simulada
        db.session.commit()
        with pytest.raises(RestorationBlocked) as e:
            restore_financial_record(fid, cid)
        assert "Divergência de valor" in str(e.value)
        db.session.rollback()

        ghost = FinancialRecord(company_id=cid, type="revenue", amount=100.0,
                                status="pago", paid_date=date.today(),
                                reference="order_payment:999999")
        db.session.add(ghost)
        db.session.flush()
        ghost.soft_delete()
        db.session.commit()
        with pytest.raises(RestorationBlocked) as e:
            restore_financial_record(ghost.id, cid)
        assert "Parcela inexistente" in str(e.value)
        db.session.rollback()


def test_restore_blocked_wrong_company(testing_app):
    cid = _cid(testing_app)
    _, _, fid = _seed_order_paid(testing_app, cid, total=500.0)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        fr.soft_delete()
        db.session.commit()
        with pytest.raises(RestorationBlocked):
            restore_financial_record(fid, cid + 999)
        db.session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Transação: falha de auditoria → rollback completo
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_rollback_on_audit_failure(testing_app, monkeypatch):
    cid = _cid(testing_app)
    _, _, fid = _seed_order_paid(testing_app, cid, total=500.0)
    with testing_app.app_context():
        fr = db.session.get(FinancialRecord, fid)
        fr.soft_delete()
        db.session.commit()

    import app.utils.audit as audit_mod
    def boom(*a, **k):
        raise RuntimeError("falha simulada na auditoria")
    monkeypatch.setattr(audit_mod, "log_activity", boom)

    with testing_app.app_context():
        with pytest.raises(RuntimeError):
            restore_and_audit(fid, cid, 1)
        # rollback: continua soft-deletado, nada parcial
        fr = db.session.get(FinancialRecord, fid)
        assert fr.deleted_at is not None
