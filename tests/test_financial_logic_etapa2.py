"""tests/test_financial_logic_etapa2.py — Regras financeiras unificadas (Etapa 2).

Cobre:
  * Reconhecimento de receita (somente SO efetivamente faturado);
  * Custo direto válido (PO rascunho/cancelado/excluído fora; PO sem SO fora);
  * Margem única (margin_service = property do model = dashboard);
  * Proteção de FinancialRecords pagos no void;
  * Baixa atômica (rollback em falha);
  * Não-duplicação de FinancialRecord por reference.

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
from app.models.order import Order, OrderPayment
from app.models.purchase_order import PurchaseOrder, POPayment
from app.models.user import User
from app.services import margin_service
from app.services import financial_service
from app.services import order_service
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        # Ordem filho-primeiro respeitando as FKs (PO -> Order, POPayment -> PO)
        for model in (FinancialRecord, OrderPayment, POPayment,
                      PurchaseOrder, Order, Client):
            model.query.delete()
        db.session.commit()
    yield


def _seed_base(app):
    """Cria company/admin/client base e retorna (company, admin)."""
    with app.app_context():
        company = Company.query.first()
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        assert company and admin, "seeder do app testing não populou base"
        return company.id, admin.id


def _seed_order(app, company_id, admin_id, *, number, status, total=1000.0,
                invoiced_at=None):
    with app.app_context():
        client = Client(company_id=company_id, name=f"Cliente {number}")
        db.session.add(client)
        db.session.flush()
        order = Order(
            company_id=company_id, client_id=client.id,
            number=number, status=status,
            client_name=client.name, contact_name="", email="", celular="",
            language="pt", billing_type="recibo",
            total_amount=total, payment_method="PIX",
            emission_date=date.today(), invoiced_at=invoiced_at,
            created_by=admin_id,
        )
        db.session.add(order)
        db.session.flush()
        oid = order.id
        db.session.commit()
        return oid


def _seed_po(app, company_id, admin_id, *, number, status, amount=400.0,
             order_id=None):
    with app.app_context():
        po = PurchaseOrder(
            company_id=company_id, number=number, status=status,
            amount=amount, order_id=order_id, created_by=admin_id,
        )
        db.session.add(po)
        db.session.flush()
        pid = po.id
        db.session.commit()
        return pid


def _add_payment(app, oid, *, installment_no=1, amount=500.0, due=None):
    with app.app_context():
        pmt = OrderPayment(
            order_id=oid, installment_no=installment_no, amount=amount,
            due_date=due or date.today(), paid_amount=0.0,
        )
        db.session.add(pmt)
        db.session.flush()
        pid = pmt.id
        db.session.commit()
        return pid


# ─────────────────────────────────────────────────────────────────────────────
# Receita reconhecida (regra única)
# ─────────────────────────────────────────────────────────────────────────────

def test_revenue_recognition_rules(testing_app):
    cid, admin = _seed_base(testing_app)
    today_dt = now_br()

    def recognized(oid):
        with testing_app.app_context():
            o = db.session.get(Order, oid)
            return margin_service.recognized_service_revenue(o)

    novo = _seed_order(testing_app, cid, admin, number="SO-NOVO", status="novo")
    aberto = _seed_order(testing_app, cid, admin, number="SO-AB", status="aberto")
    concl_sem_fat = _seed_order(testing_app, cid, admin, number="SO-CSF", status="concluido")
    faturado = _seed_order(testing_app, cid, admin, number="SO-FAT", status="faturado",
                           invoiced_at=today_dt)
    concl_com_fat = _seed_order(testing_app, cid, admin, number="SO-CCF", status="concluido",
                                invoiced_at=today_dt)
    cancelado = _seed_order(testing_app, cid, admin, number="SO-CAN", status="cancelado",
                            invoiced_at=today_dt)

    assert recognized(novo) == 0.0          # SO criado não é receita
    assert recognized(aberto) == 0.0        # SO aberto não é receita
    assert recognized(concl_sem_fat) == 0.0  # concluído sem faturamento não é receita
    assert recognized(cancelado) == 0.0      # cancelado não é receita
    assert recognized(faturado) == 1000.0    # faturado é receita
    assert recognized(concl_com_fat) == 1000.0  # concluído COM fatura é receita


# ─────────────────────────────────────────────────────────────────────────────
# Custo direto válido (regra única)
# ─────────────────────────────────────────────────────────────────────────────

def test_cost_rule_excludes_invalid_and_unlinked(testing_app):
    cid, admin = _seed_base(testing_app)
    today_dt = now_br()
    oid = _seed_order(testing_app, cid, admin, number="SO-CUSTO", status="faturado",
                      invoiced_at=today_dt)
    _seed_po(testing_app, cid, admin, number="PO-RAS", status="rascunho", amount=900.0, order_id=oid)
    _seed_po(testing_app, cid, admin, number="PO-CAN", status="cancelado", amount=300.0, order_id=oid)
    _seed_po(testing_app, cid, admin, number="PO-EXC", status="excluido", amount=200.0, order_id=oid)
    _seed_po(testing_app, cid, admin, number="PO-AB", status="aberto", amount=400.0, order_id=oid)
    _seed_po(testing_app, cid, admin, number="PO-SOLTA", status="pago", amount=13500.0, order_id=None)

    with testing_app.app_context():
        o = db.session.get(Order, oid)
        cost = margin_service.direct_cost_total(o)
        assert cost == 400.0  # somente a PO aberta vinculada; sem-SO não entra
        assert all(po.order_id == oid for po in margin_service.direct_costs_for_order(o))


# ─────────────────────────────────────────────────────────────────────────────
# Margem única (mesma fonte em serviço, model e dashboard)
# ─────────────────────────────────────────────────────────────────────────────

def test_gross_margin_single_source(testing_app):
    cid, admin = _seed_base(testing_app)
    today_dt = now_br()
    oid = _seed_order(testing_app, cid, admin, number="SO-MARG", status="faturado",
                      invoiced_at=today_dt)
    _seed_po(testing_app, cid, admin, number="PO-M1", status="aberto", amount=400.0, order_id=oid)
    _seed_po(testing_app, cid, admin, number="PO-M2", status="rascunho", amount=900.0, order_id=oid)

    with testing_app.app_context():
        o = db.session.get(Order, oid)
        # denormalizado "sujo" de propósito — o cálculo deve ignorá-lo
        o.total_po_cost = 1300.0
        rev, cost, margin = margin_service.gross_margin(o)
        assert (rev, cost, margin) == (1000.0, 400.0, 600.0)
        assert margin_service.gross_margin_pct(o) == 60.0
        assert o.margin_pct == 60.0  # property do model usa a mesma regra


def test_dashboard_period_functions(testing_app):
    from app.blueprints.dashboard.routes import _so_revenue, _po_cost
    cid, admin = _seed_base(testing_app)
    today = now_br().date()
    m_start = today.replace(day=1)
    fat_oid = _seed_order(testing_app, cid, admin, number="SO-DASH-FAT",
                          status="faturado", invoiced_at=now_br())
    _seed_order(testing_app, cid, admin, number="SO-DASH-AB", status="aberto")
    _seed_po(testing_app, cid, admin, number="PO-D1", status="aberto", amount=300.0, order_id=fat_oid)
    _seed_po(testing_app, cid, admin, number="PO-D2", status="rascunho", amount=999.0, order_id=fat_oid)
    _seed_po(testing_app, cid, admin, number="PO-D3", status="pago", amount=5000.0, order_id=None)

    with testing_app.app_context():
        assert _so_revenue(cid, m_start, today) == 1000.0   # só faturado
        assert _po_cost(cid, m_start, today) == 300.0        # rascunho e sem-SO fora


# ─────────────────────────────────────────────────────────────────────────────
# Proteção de FinancialRecords pagos no void
# ─────────────────────────────────────────────────────────────────────────────

def test_void_preserves_paid_financial_records(testing_app):
    cid, admin = _seed_base(testing_app)
    oid = _seed_order(testing_app, cid, admin, number="SO-VOID", status="faturado",
                      total=1000.0, invoiced_at=now_br())
    p1 = _add_payment(testing_app, oid, installment_no=1, amount=500.0)
    p2 = _add_payment(testing_app, oid, installment_no=2, amount=500.0)

    with testing_app.app_context():
        order = db.session.get(Order, oid)
        order_service._sync_order_pending_financials(order)   # 2 FRs pendentes
        db.session.commit()
        pmt1 = db.session.get(OrderPayment, p1)
        order_service.baixa(pmt1, 500.0, admin)               # FR1 -> pago
        n = financial_service.void_payment_financial_records(order.payments, "order_payment")
        db.session.commit()
        assert n == 1  # só o pendente foi voidado
        fr1 = FinancialRecord.query.filter_by(reference=f"order_payment:{p1}").first()
        fr2 = FinancialRecord.query.filter_by(reference=f"order_payment:{p2}").first()
        assert fr1.status == "pago" and fr1.deleted_at is None    # pago PRESERVADO
        assert fr2.deleted_at is not None                          # pendente voidado


# ─────────────────────────────────────────────────────────────────────────────
# Não-duplicação de FinancialRecord por reference
# ─────────────────────────────────────────────────────────────────────────────

def test_no_duplicate_financial_record_on_rebaixa(testing_app):
    cid, admin = _seed_base(testing_app)
    oid = _seed_order(testing_app, cid, admin, number="SO-DUP", status="faturado",
                      total=500.0, invoiced_at=now_br())
    pid = _add_payment(testing_app, oid, installment_no=1, amount=500.0)

    with testing_app.app_context():
        pmt = db.session.get(OrderPayment, pid)
        order_service.baixa(pmt, 500.0, admin)
        # Etapa 10D: re-baixa de parcela quitada é BLOQUEADA (não duplica)
        with pytest.raises(ValueError):
            order_service.baixa(pmt, 500.0, admin)
        db.session.rollback()
        frs = FinancialRecord.query.filter_by(reference=f"order_payment:{pid}").all()
        assert len(frs) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Baixa atômica (rollback em falha)
# ─────────────────────────────────────────────────────────────────────────────

def test_baixa_rolls_back_on_failure(testing_app, monkeypatch):
    cid, admin = _seed_base(testing_app)
    oid = _seed_order(testing_app, cid, admin, number="SO-ATOM", status="faturado",
                      total=500.0, invoiced_at=now_br())
    pid = _add_payment(testing_app, oid, installment_no=1, amount=500.0)

    def boom(order):
        raise RuntimeError("falha simulada no recálculo de margem")

    monkeypatch.setattr(margin_service, "recalculate_order", boom)

    with testing_app.app_context():
        pmt = db.session.get(OrderPayment, pid)
        with pytest.raises(RuntimeError):
            order_service.baixa(pmt, 500.0, admin)
        db.session.rollback()   # nada deve ter sido commitado
        pmt = db.session.get(OrderPayment, pid)
        assert pmt.paid_at is None and (pmt.paid_amount or 0) == 0
        frs = FinancialRecord.query.filter_by(reference=f"order_payment:{pid}").all()
        assert frs == []  # nenhum lançamento criado
