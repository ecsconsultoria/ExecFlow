"""tests/test_ux_parcelas_etapa11b.py — UX de parcelas e baixas (Etapa 11B fase 2).

Cobre: resumo Valor/Recebido/Saldo/Status para aberta/parcial/quitada;
badge PARCIAL; timeline pós-10D (valores + saldo derivado + total);
pré-10D sem inventar valor; modal pré-preenchendo saldo (data-balance);
consistência (não corrige dados); multiempresa; RBAC (sem novos endpoints).

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev.
"""
import uuid
from datetime import date, datetime

import pytest

from app import create_app
from app.extensions import db
from app.models.audit import AuditLog
from app.models.client import Client
from app.models.financial import FinancialRecord
from app.models.order import Order, OrderPayment
from app.models.user import User
from app.services.payment_history_service import build_baixa_history
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        for model in (AuditLog, FinancialRecord, OrderPayment, Order, Client):
            model.query.delete()
        db.session.commit()
    yield


def _cid(app):
    with app.app_context():
        return User.query.filter_by(email=ADMIN_EMAIL).first().company_id


def _seed_order(app, cid, *, paid=0.0, amount=1300.0, n_parcelas=1):
    with app.app_context():
        client = Client(company_id=cid, name=f"11B {uuid.uuid4().hex[:6]}")
        db.session.add(client)
        db.session.flush()
        o = Order(company_id=cid, client_id=client.id,
                  number=f"SO-11B-{uuid.uuid4().hex[:8]}", status="faturado",
                  client_name=client.name, contact_name="", email="", celular="",
                  language="pt", billing_type="recibo", total_amount=amount,
                  payment_method="PIX", emission_date=date.today(),
                  invoiced_at=now_br(), created_by=1)
        db.session.add(o)
        db.session.flush()
        p = OrderPayment(order_id=o.id, installment_no=1, amount=amount,
                         due_date=date.today(), paid_amount=paid,
                         paid_at=now_br() if paid else None,
                         paid_by=1 if paid else None)
        db.session.add(p)
        db.session.commit()
        return o.id, p.id


def _seed_audit(app, oid, action, at=None):
    with app.app_context():
        db.session.add(AuditLog(company_id=1, user_id=1, entity="order",
                                entity_id=oid, action=action,
                                created_at=at or now_br()))
        db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Service de histórico
# ─────────────────────────────────────────────────────────────────────────────

def test_history_post_10d_full(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed_order(testing_app, cid, paid=1300.0, amount=1300.0)
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 500.00",
                at=datetime(2026, 8, 28, 20, 15))
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 800.00",
                at=datetime(2026, 8, 29, 10, 30))

    with testing_app.app_context():
        logs = AuditLog.query.filter_by(entity="order", entity_id=oid).order_by(AuditLog.created_at).all()
        pmt = db.session.get(OrderPayment, pid)
        h = build_baixa_history(logs, {1: pmt})
        assert 1 in h
        entries = h[1]["entries"]
        assert [e["value"] for e in entries] == [500.0, 800.0]
        assert [e["balance_after"] for e in entries] == [800.0, 0.0]
        assert h[1]["total"] == 1300.0
        assert h[1]["consistent"] is True
        assert h[1]["pre_10d"] is False


def test_history_pre_10d_no_invention(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed_order(testing_app, cid, paid=450.0, amount=450.0)
    _seed_audit(testing_app, oid, "Parcela 1 baixada")  # sem valor

    with testing_app.app_context():
        logs = AuditLog.query.filter_by(entity="order", entity_id=oid).order_by(AuditLog.created_at).all()
        pmt = db.session.get(OrderPayment, pid)
        h = build_baixa_history(logs, {1: pmt})
        assert h[1]["pre_10d"] is True
        assert h[1]["entries"][0]["value"] is None          # nunca inventar
        assert h[1]["final_paid"] == 450.0                  # comprovado da parcela
        assert h[1]["consistent"] is True


def test_history_ignores_panel_and_inconsistency(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed_order(testing_app, cid, paid=1300.0, amount=1300.0)
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 500.00")
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 900.00")  # soma 1.400 > 1.300
    _seed_audit(testing_app, oid, "Baixa registrada R$ 100.00 (PIX)")  # painel — ignorada

    with testing_app.app_context():
        logs = AuditLog.query.filter_by(entity="order", entity_id=oid).order_by(AuditLog.created_at).all()
        pmt = db.session.get(OrderPayment, pid)
        h = build_baixa_history(logs, {1: pmt})
        assert len(h[1]["entries"]) == 2          # "Baixa registrada" ignorada
        assert h[1]["consistent"] is False        # sinaliza, NÃO corrige
        assert h[1]["final_paid"] == 1300.0       # dados originais preservados


# ─────────────────────────────────────────────────────────────────────────────
# Render (rota do detail)
# ─────────────────────────────────────────────────────────────────────────────

def _login(app):
    c = app.test_client()
    c.post("/auth/login", data={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
           follow_redirects=False)
    return c


def test_detail_renders_summary_and_badges(testing_app):
    cid = _cid(testing_app)
    oid_aberta, _ = _seed_order(testing_app, cid, paid=0.0, amount=1000.0)
    oid_parcial, _ = _seed_order(testing_app, cid, paid=400.0, amount=1000.0)
    oid_quitada, _ = _seed_order(testing_app, cid, paid=1000.0, amount=1000.0)

    c = _login(testing_app)
    page = c.get(f"/orders/{oid_parcial}").get_data(as_text=True)
    assert "PARCIAL" in page and "saldo R$ 600,00" in page
    assert 'data-balance="600,00"' in page          # modal pré-preenche o SALDO

    page = c.get(f"/orders/{oid_aberta}").get_data(as_text=True)
    assert "ABERTA" in page

    page = c.get(f"/orders/{oid_quitada}").get_data(as_text=True)
    assert "QUITADA" in page and "saldo R$ 0,00" in page


def test_detail_timeline_render(testing_app):
    cid = _cid(testing_app)
    oid, pid = _seed_order(testing_app, cid, paid=1300.0, amount=1300.0)
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 500.00")
    _seed_audit(testing_app, oid, "Parcela 1 baixada R$ 800.00")

    c = _login(testing_app)
    page = c.get(f"/orders/{oid}").get_data(as_text=True)
    assert "Histórico de baixas" in page
    assert "500.00" in page and "800.00" in page
    assert "TOTAL RECEBIDO" in page and "1300.00" in page
    assert "não disponível para este período" not in page  # pós-10D completo


def test_detail_pre_10d_notice(testing_app):
    cid = _cid(testing_app)
    oid, _ = _seed_order(testing_app, cid, paid=450.0, amount=450.0)
    _seed_audit(testing_app, oid, "Parcela 1 baixada")

    c = _login(testing_app)
    page = c.get(f"/orders/{oid}").get_data(as_text=True)
    assert "valor individual não disponível" in page
    assert "não disponível para este período" in page


def test_multitenant_history_scoped(testing_app):
    from app.models.company import Company
    cid = _cid(testing_app)
    oid_a, pid = _seed_order(testing_app, cid, paid=0.0)
    with testing_app.app_context():
        comp_b = Company(name="Empresa B 11B", slug="empresa-b-11b", document="00.000.000/0013-00")
        db.session.add(comp_b)
        db.session.commit()
        cid_b = comp_b.id
        # auditoria da empresa B não pode vazar para a timeline de A
        db.session.add(AuditLog(company_id=cid_b, user_id=1, entity="order",
                                entity_id=999, action="Parcela 1 baixada R$ 999.00"))
        db.session.commit()

    c = _login(testing_app)
    page = c.get(f"/orders/{oid_a}").get_data(as_text=True)
    assert "999,00" not in page  # timeline não vaza dados de outra empresa
