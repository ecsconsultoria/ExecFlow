"""tests/test_payment_receipt.py — Payment Receipt (Recibo de Pagamento).

Cobre: regras do botão/rota (concluido + parcela paga), recibo parcial vs final,
reutilização do número, PDF em 1 página, valores vindos dos records reais,
USD via usd_rate e geração read-only em relação às finanças.

App próprio com TestingConfig (sqlite :memory:) — não usa o DB dev do conftest.
"""
import re
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
from app.models.user import User
from app.services.receipt_pdf import (
    build_receipt_context,
    generate_receipt_pdf,
    _amount_cell,
)
from app.services.quote_pdf import BRAND_DARK
from app.utils import now_br

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"
REC_RE = re.compile(r"REC-\d{6}-\d{3}")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures (isoladas do app/DB dev do conftest)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean_tables(testing_app):
    with testing_app.app_context():
        # Ordem filho-primeiro respeitando as FKs
        for model in (PaymentReceipt, OrderPayment, OrderItem, Order,
                      FinancialRecord, Client):
            model.query.delete()
        db.session.commit()
    yield


def _login(app, email=ADMIN_EMAIL, password=ADMIN_PWD):
    c = app.test_client()
    r = c.post("/auth/login", data={"email": email, "password": password},
               follow_redirects=False)
    assert r.status_code in (200, 302), f"login {email} falhou ({r.status_code})"
    return c


def _seed_order(app, *, status="concluido", installments=2, paid=2,
                usd_rate=None, payment_method="TRANSFERÊNCIA",
                category_name=None, vehicle_description="Luxury Van Jet",
                driver_name="Bilingual Driver"):
    """Cria Company-agnostic: client + order + itens + parcelas + espelho financeiro."""
    with app.app_context():
        company = Company.query.first()
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        client = Client(company_id=company.id, name="Philippine Embassy",
                        contact="Bien Janine", email="bienjanine.alfaro@dfa.gov.ph",
                        whatsapp="+63 966 957 0116")
        db.session.add(client)
        db.session.flush()

        order = Order(
            company_id=company.id, client_id=client.id,
            number=f"SO-TEST-{uuid.uuid4().hex[:8]}",
            status=status,
            client_name=client.name, contact_name=client.contact,
            email=client.email, celular=client.whatsapp,
            language="pt", billing_type="recibo",
            total_amount=17500.0, usd_rate=usd_rate,
            payment_method=payment_method,
            emission_date=date.today(),
            created_by=admin.id,
        )
        db.session.add(order)
        db.session.flush()

        category_id = None
        if category_name:
            from app.models.vehicle import VehicleCategory
            cat = (VehicleCategory.query
                   .filter(db.func.lower(VehicleCategory.name) == category_name.lower())
                   .first())
            category_id = cat.id if cat else None

        db.session.add(OrderItem(
            order_id=order.id, description="Executive Transportation",
            vehicle_description=vehicle_description, driver_name=driver_name,
            category_id=category_id,
            quantity=1, unit_price=17500.0, total_price=17500.0,
            service_date=date.today(),
        ))

        inst_amount = round(17500.0 / installments, 2)
        pids = []
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
                    company_id=company.id, type="revenue", category="receita_servico",
                    description=f"{order.number} — parcela {i}/{installments}",
                    amount=inst_amount, status="pago", paid_date=date.today(),
                    payment_method=payment_method,
                    reference=f"order_payment:{pmt.id}",
                ))
        db.session.commit()
        return order.id, pids


def _receipt_numbers_from_response(resp):
    disp = resp.headers.get("Content-Disposition", "")
    return REC_RE.findall(disp)


def _snapshot_financials(app):
    """Snapshot das tabelas financeiras — a geração do recibo não pode alterá-las."""
    with app.app_context():
        def rows(model):
            cols = model.__table__.columns.keys()
            return [tuple(getattr(r, c) for c in cols)
                    for r in model.query.order_by(model.id).all()]
        return {
            "orders": rows(Order),
            "order_payments": rows(OrderPayment),
            "financial_records": rows(FinancialRecord),
        }


class _CountingCanvas:
    """canvasmaker do SimpleDocTemplate — conta páginas renderizadas."""

    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas as _canvas
        self._inner = _canvas.Canvas(*args, **kwargs)
        self.pages = 0

    def showPage(self):
        self.pages += 1
        self._inner.showPage()

    def save(self):
        self._inner.save()

    def __getattr__(self, name):
        return getattr(self._inner, name)


# ─────────────────────────────────────────────────────────────────────────────
# Regras de geração
# ─────────────────────────────────────────────────────────────────────────────

def test_route_returns_pdf_when_concluido_and_paid(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    c = _login(testing_app)
    r = c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False)
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data[:5] == b"%PDF-"


def test_route_403_when_order_not_concluido(testing_app):
    oid, pids = _seed_order(testing_app, status="faturado", installments=2, paid=2)
    c = _login(testing_app)
    r = c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False)
    assert r.status_code == 403


def test_route_404_when_payment_not_of_order(testing_app):
    oid1, pids1 = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    oid2, _ = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    c = _login(testing_app)
    r = c.get(f"/orders/{oid1}/receipt/{pids1[0]}/pt", follow_redirects=False)
    assert r.status_code == 200
    # Parcela de outro SO
    r = c.get(f"/orders/{oid1}/receipt/99999/pt", follow_redirects=False)
    assert r.status_code == 404
    # O SO2 não tem parcelas com os ids do SO1
    with testing_app.app_context():
        other_pmt = OrderPayment.query.filter_by(order_id=oid2).first()
    r = c.get(f"/orders/{oid1}/receipt/{other_pmt.id}/pt", follow_redirects=False)
    assert r.status_code == 404


def test_route_400_when_payment_unpaid(testing_app):
    # SO concluído manualmente (fechar) com parcela em aberto — recibo bloqueado
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=1)
    c = _login(testing_app)
    r = c.get(f"/orders/{oid}/receipt/{pids[1]}/pt", follow_redirects=False)
    assert r.status_code == 400


def test_anon_redirected_to_login(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    c = testing_app.test_client()
    r = c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False)
    assert r.status_code == 302
    assert "/auth/login" in (r.headers.get("Location") or "")


# ─────────────────────────────────────────────────────────────────────────────
# Conteúdo do recibo (context puro)
# ─────────────────────────────────────────────────────────────────────────────

def test_context_partial_payment(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=1)
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["summary"]["received"] == 8750.0
    assert ctx["summary"]["previously"] == 0.0
    assert ctx["summary"]["outstanding"] == 8750.0
    assert ctx["summary"]["is_final"] is False
    assert ctx["status"]["key"] == "paid"
    assert ctx["status"]["label"] == "PAID"
    assert "1 of 2" in ctx["payment"]["reference"]
    assert ctx["payment"]["method"] == "TRANSFERÊNCIA"
    assert ctx["payment"]["amount"] == 8750.0
    assert ctx["customer"]["name"] == "Philippine Embassy"
    assert ctx["customer"]["email"] == "bienjanine.alfaro@dfa.gov.ph"
    assert ctx["service"]["summary"] == "Executive Transportation"


def test_context_final_payment(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[1])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["summary"]["received"] == 8750.0
    assert ctx["summary"]["previously"] == 8750.0
    assert ctx["summary"]["outstanding"] == 0.0
    assert ctx["summary"]["is_final"] is True
    assert ctx["status"]["key"] == "paid_in_full"
    assert ctx["status"]["label"] == "PAID IN FULL"
    assert "2 of 2" in ctx["payment"]["reference"]
    assert ctx["payment"]["payment_type"] == "Final Payment"


def test_context_first_of_fully_paid_order_still_partial(testing_app):
    # SO 100% quitado, mas o recibo da 1ª parcela é um documento parcial:
    # mostra o saldo restante NAQUELA posição do contrato, não o saldo atual.
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["summary"]["received"] == 8750.0
    assert ctx["summary"]["previously"] == 0.0
    assert ctx["summary"]["outstanding"] == 8750.0
    assert ctx["summary"]["is_final"] is False
    assert ctx["status"]["key"] == "paid"
    assert ctx["status"]["label"] == "PAID"
    assert ctx["payment"]["payment_type"] == "Installment 1 of 2"


def test_context_single_payment_full(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=1, paid=1)
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["summary"]["outstanding"] == 0.0
    assert ctx["summary"]["is_final"] is True
    assert ctx["payment"]["payment_type"] == "Full Payment"
    assert "1 of 1" in ctx["payment"]["reference"]


def test_context_vehicle_from_category(testing_app):
    # Item sem vehicle_description: veículo deriva da categoria (regra do SO)
    oid, pids = _seed_order(testing_app, status="concluido", installments=1, paid=1,
                            category_name="Van Blindada", vehicle_description="",
                            driver_name="Bilíngue")
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["service"]["vehicle"] == "Mercedes Sprinter or Similar"
    assert ctx["service"]["driver"] == "Bilingual Driver"


def test_values_come_from_real_payment_records(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    with testing_app.app_context():
        pmt = db.session.get(OrderPayment, pids[0])
        pmt.paid_amount = 9000.25
        fr = FinancialRecord.query.filter_by(reference=f"order_payment:{pmt.id}").first()
        fr.payment_method = "PIX"
        db.session.commit()
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        ctx = build_receipt_context(order, pmt, lang="en")
    assert ctx["payment"]["amount"] == 9000.25
    assert ctx["summary"]["received"] == 9000.25
    assert ctx["summary"]["previously"] == 0.0
    # Saldo = posição do contrato APÓS este pagamento (parcelas anteriores + esta)
    assert ctx["summary"]["outstanding"] == 8499.75
    assert ctx["summary"]["is_final"] is False
    assert ctx["payment"]["method"] == "PIX"
    # O PDF reflete o novo valor (build com sucesso)
    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[0])
        buf = generate_receipt_pdf(order, pmt, "REC-260813-001", lang="en")
    assert buf.read(5) == b"%PDF-"


def test_usd_only_when_usd_rate_set():
    cell_off = _amount_cell(17500.0, None, BRAND_DARK)
    assert "USD" not in cell_off.getPlainText()
    cell_on = _amount_cell(17500.0, 5.25, BRAND_DARK)
    assert "USD 3,333.33" in cell_on.getPlainText()


# ─────────────────────────────────────────────────────────────────────────────
# Numeração e deduplicação
# ─────────────────────────────────────────────────────────────────────────────

def test_regeneration_reuses_receipt_number(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    c = _login(testing_app)

    r1 = c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False)
    r2 = c.get(f"/orders/{oid}/receipt/{pids[0]}/en", follow_redirects=False)
    assert r1.status_code == r2.status_code == 200
    n1, n2 = _receipt_numbers_from_response(r1), _receipt_numbers_from_response(r2)
    assert n1 and n1 == n2  # mesmo recibo, mesmo número

    with testing_app.app_context():
        assert PaymentReceipt.query.count() == 1
        rec = PaymentReceipt.query.first()
        assert rec.receipt_number == n1[0]
        assert rec.payment_id == pids[0]

    # Outra parcela → outro número (sequência do dia)
    r3 = c.get(f"/orders/{oid}/receipt/{pids[1]}/pt", follow_redirects=False)
    n3 = _receipt_numbers_from_response(r3)
    assert r3.status_code == 200 and n3
    assert n3[0] != n1[0]
    with testing_app.app_context():
        assert PaymentReceipt.query.count() == 2
        seq_a = int(n1[0].split("-")[-1])
        seq_b = int(n3[0].split("-")[-1])
        assert seq_b == seq_a + 1


# ─────────────────────────────────────────────────────────────────────────────
# PDF em 1 página
# ─────────────────────────────────────────────────────────────────────────────

def test_pdf_is_one_page(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    holder = {}

    def _factory(*args, **kwargs):
        holder["canvas"] = _CountingCanvas(*args, **kwargs)
        return holder["canvas"]

    with testing_app.app_context():
        order = db.session.get(Order, oid)
        pmt = db.session.get(OrderPayment, pids[1])
        buf = generate_receipt_pdf(order, pmt, "REC-260813-001", lang="en",
                                   canvasmaker=_factory)
        data = buf.getvalue()
    assert data[:5] == b"%PDF-"
    # 1) contagem autoritativa via canvasmaker
    assert holder["canvas"].pages == 1
    # 2) smoke no bytes brutos — ReportLab grava dicionários de página sem compressão
    assert len(re.findall(rb"/Type\s*/Page(?!s)", data)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Read-only financeiro
# ─────────────────────────────────────────────────────────────────────────────

def test_generation_does_not_mutate_financials(testing_app):
    oid, pids = _seed_order(testing_app, status="concluido", installments=2, paid=2)
    c = _login(testing_app)
    before = _snapshot_financials(testing_app)

    assert c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False).status_code == 200
    assert c.get(f"/orders/{oid}/receipt/{pids[1]}/en", follow_redirects=False).status_code == 200
    # Regeneração também não pode alterar nada
    assert c.get(f"/orders/{oid}/receipt/{pids[0]}/pt", follow_redirects=False).status_code == 200

    after = _snapshot_financials(testing_app)
    assert after == before

    with testing_app.app_context():
        order = db.session.get(Order, oid)
        assert order.status == "concluido"
        assert order.total_paid() == 17500.0
        assert order.total_pending() == 0.0
