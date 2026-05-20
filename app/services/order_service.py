"""order_service.py — Lógica de negócio para Pedidos (Orders).

Fluxo de status:
  novo → aberto → faturado → fechado
                ↘ cancelado
"""
from datetime import date, datetime, timedelta

from ..extensions import db
from ..models.order import Order, OrderItem, OrderPayment, ORDER_STATUSES  # noqa: F401
from ..utils import now_br


# ─────────────────────────────────────────────────────────────────────────────
# Criação
# ─────────────────────────────────────────────────────────────────────────────

def create_from_quote(quote, user_id: int) -> Order:
    """Cria um Pedido (BR-AAMMDD-NNN) a partir de um Orçamento aprovado."""
    from . import numbering_service

    order = Order(
        company_id     = quote.company_id,
        client_id      = quote.client_id,
        quote_id       = quote.id,
        number         = numbering_service.next_order(quote.company_id),
        status         = "novo",
        client_name    = quote.client_name  or "",
        contact_name   = quote.contact_name or "",
        email          = quote.email        or "",
        phone          = quote.phone        or "",
        celular        = (quote.client.whatsapp if quote.client else "") or "",
        language       = quote.language     or "pt",
        billing_type   = quote.billing_type or "recibo",
        payment_method = quote.payment_method or "",
        payment_terms  = quote.payment_terms  or "",
        obs            = quote.obs            or "",
        total_amount   = quote.total_amount   or 0,
        emission_date  = now_br().date(),
        created_by     = user_id,
    )
    db.session.add(order)
    db.session.flush()

    for qi in quote.items:
        item = OrderItem(
            order_id            = order.id,
            service_id          = qi.service_id,
            category_id         = qi.category_id,
            description         = qi.description         or "",
            vehicle_description = qi.vehicle_description or "",
            quantity            = qi.quantity            or 1,
            unit_price          = qi.unit_price          or 0,
            total_price         = qi.total_price         or 0,
            sort_order          = qi.sort_order          or 0,
            driver_name         = qi.driver_name         or "",
            state_code          = qi.state_code          or "",
            ref_note            = qi.ref_note            or "",
        )
        db.session.add(item)

    quote.status = "reserva_confirmada"
    db.session.commit()
    return order


# ─────────────────────────────────────────────────────────────────────────────
# Atualização de campos
# ─────────────────────────────────────────────────────────────────────────────

def update_header(order: Order, data: dict) -> None:
    """Atualiza campos do cabeçalho: emissão, entrega, forma, prazo."""
    if data.get("emission_date"):
        try:
            order.emission_date = date.fromisoformat(str(data["emission_date"]))
        except (ValueError, TypeError):
            pass
    if data.get("delivery_datetime"):
        try:
            order.delivery_datetime = datetime.fromisoformat(str(data["delivery_datetime"]))
        except (ValueError, TypeError):
            pass
    else:
        order.delivery_datetime = None
    for field in ("payment_method", "payment_terms", "obs", "celular"):
        if field in data:
            setattr(order, field, data[field] or "")
    db.session.commit()


def update_adjustments(order: Order, data: dict) -> None:
    """Atualiza desconto, frete e outros custos."""
    order.discount_type      = data.get("discount_type", "R$") or "R$"
    order.discount_value     = _parse_float(data.get("discount_value", 0))
    order.freight_amount     = _parse_float(data.get("freight_amount", 0))
    order.other_costs_amount = _parse_float(data.get("other_costs_amount", 0))
    db.session.commit()


def update_payment_inline(payment: OrderPayment, data: dict) -> None:
    """Atualiza parcela inline (data vencimento, notas, valor)."""
    if data.get("due_date"):
        try:
            payment.due_date = date.fromisoformat(str(data["due_date"]))
        except (ValueError, TypeError):
            pass
    if "notes" in data:
        payment.notes = data["notes"] or ""
    if data.get("amount"):
        payment.amount = _parse_float(data["amount"])
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Transições de status
# ─────────────────────────────────────────────────────────────────────────────

def open_order(order: Order, user_id: int) -> None:
    if order.status != "novo":
        raise ValueError(f"Não é possível abrir pedido com status '{order.status}'")
    order.status    = "aberto"
    order.opened_at = now_br()
    db.session.commit()


def faturar(order: Order, data: dict, user_id: int) -> None:
    if order.status != "aberto":
        raise ValueError(f"Não é possível faturar pedido com status '{order.status}'")
    order.status          = "faturado"
    order.invoice_number  = data.get("invoice_number", "") or ""
    order.invoiced_at     = now_br()
    if data.get("invoice_due_date"):
        try:
            order.invoice_due_date = date.fromisoformat(str(data["invoice_due_date"]))
        except (ValueError, TypeError):
            pass
    db.session.commit()


def fechar(order: Order, user_id: int) -> None:
    if order.status not in ("faturado", "aberto"):
        raise ValueError(f"Não é possível fechar pedido com status '{order.status}'")
    order.status    = "fechado"
    order.closed_at = now_br()
    db.session.commit()


def cancel(order: Order, reason: str, user_id: int) -> None:
    if order.status == "fechado":
        raise ValueError("Não é possível cancelar pedido já fechado")
    order.status        = "cancelado"
    order.cancelled_at  = now_br()
    order.cancel_reason = reason or ""
    db.session.commit()


def reabrir(order: Order, user_id: int) -> None:
    if order.status != "faturado":
        raise ValueError(f"Somente pedidos faturados podem ser reabertos (status atual: '{order.status}')")
    order.status         = "aberto"
    order.reopened_at    = now_br()
    order.invoiced_at    = None
    order.invoice_number = ""
    order.invoice_due_date = None
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Pagamentos / Parcelas
# ─────────────────────────────────────────────────────────────────────────────

def generate_payments(order: Order, custom_total: float = None) -> list:
    """Gera parcelas baseado em payment_terms.

    Modo ADD (custom_total fornecido): acrescenta UMA parcela do valor informado
    sem apagar as parcelas não-pagas existentes.  O saldo restante fica em
    aberto para o usuário agendar manualmente quando quiser.

    Modo REGENERAR (sem custom_total): apaga todas as não-pagas e recria com
    base no prazo de pagamento aplicado sobre o saldo (total − já pago).
    """
    today = now_br().date()

    # ── ADD MODE ────────────────────────────────────────────────────────────
    if custom_total is not None:
        existing      = list(order.payments)
        already_alloc = sum(p.amount or 0 for p in existing)
        unscheduled   = round(order.computed_total - already_alloc, 2)
        first_amt     = min(round(custom_total, 2), max(unscheduled, 0))
        if first_amt < 0.01:
            return []
        next_no = max((p.installment_no for p in existing), default=0) + 1
        pmt = OrderPayment(
            order_id       = order.id,
            installment_no = next_no,
            due_date       = today,
            amount         = first_amt,
            paid_amount    = 0,
        )
        db.session.add(pmt)
        db.session.commit()
        return [pmt]

    # ── REGENERATE MODE ──────────────────────────────────────────────────────
    paid_pmts = [p for p in order.payments if p.is_paid]
    unpaid    = [p for p in order.payments if not p.is_paid]
    for p in unpaid:
        db.session.delete(p)
    db.session.flush()

    already_paid = sum(p.paid_amount or 0 for p in paid_pmts)
    remaining    = round(order.computed_total - already_paid, 2)
    terms_upper  = (order.payment_terms or "").upper().strip()
    next_no      = max((p.installment_no for p in paid_pmts), default=0) + 1

    if "DIAS" in terms_upper:
        try:
            defer_days = int(terms_upper.replace("DIAS", "").strip())
        except ValueError:
            defer_days = 30
    else:
        defer_days = 30

    installments: list[tuple] = []
    if terms_upper == "À VISTA + 1 PARCELA":
        half = round(remaining / 2, 2)
        installments = [
            (next_no,     today,                             half),
            (next_no + 1, today + timedelta(days=30),        remaining - half),
        ]
    elif "DIAS" in terms_upper:
        installments = [(next_no, today + timedelta(days=defer_days), remaining)]
    else:
        installments = [(next_no, today, remaining)]

    created = []
    for no, due, amount in installments:
        pmt = OrderPayment(
            order_id       = order.id,
            installment_no = no,
            due_date       = due,
            amount         = amount,
            paid_amount    = 0,
        )
        db.session.add(pmt)
        created.append(pmt)

    db.session.commit()
    return created


def add_payment(order: Order, data: dict) -> OrderPayment:
    next_no = max((p.installment_no for p in order.payments), default=0) + 1
    due = None
    if data.get("due_date"):
        try:
            due = date.fromisoformat(str(data["due_date"]))
        except (ValueError, TypeError):
            pass
    pmt = OrderPayment(
        order_id       = order.id,
        installment_no = next_no,
        due_date       = due,
        amount         = _parse_float(data.get("amount", 0)),
        notes          = data.get("notes", "") or "",
        paid_amount    = 0,
    )
    db.session.add(pmt)
    db.session.commit()
    return pmt


def delete_payment(payment: OrderPayment) -> None:
    if payment.is_paid:
        raise ValueError("Não é possível excluir parcela já paga")
    db.session.delete(payment)
    db.session.commit()


def baixa(payment: OrderPayment, paid_amount: float, user_id: int) -> None:
    payment.paid_amount = paid_amount
    payment.paid_at     = now_br()
    payment.paid_by     = user_id

    order = payment.order
    if all(p.is_paid for p in order.payments) and order.status not in ("fechado", "cancelado"):
        order.status    = "fechado"
        order.closed_at = now_br()

    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _parse_float(value) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Itens do pedido
# ─────────────────────────────────────────────────────────────────────────────

def add_item(order: Order, data: dict) -> OrderItem:
    qty    = max(1, int(data.get("quantity") or 1))
    price  = _parse_float(data.get("unit_price", 0))
    svc_id = int(data["service_id"]) if data.get("service_id") else None
    cat_id = int(data["category_id"]) if data.get("category_id") else None
    desc   = data.get("description", "") or ""
    if svc_id and not desc:
        from ..models.service import Service
        svc = db.session.get(Service, svc_id)
        if svc:
            desc = svc.name
    item = OrderItem(
        order_id            = order.id,
        service_id          = svc_id,
        category_id         = cat_id,
        description         = desc,
        ref_note            = data.get("ref_note", "") or "",
        vehicle_description = data.get("vehicle_description", "") or "",
        quantity            = qty,
        unit_price          = price,
        total_price         = round(price * qty, 2),
        sort_order          = max((i.sort_order or 0 for i in order.items), default=0) + 1,
    )
    db.session.add(item)
    db.session.flush()
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    db.session.commit()
    return item


def update_item(item: OrderItem, data: dict) -> None:
    """Atualiza quantidade e valor unitário de um item do pedido."""
    raw_qty   = data.get("quantity", "")
    raw_price = data.get("unit_price", "")
    if raw_qty:
        item.quantity = max(1, int(raw_qty))
    if raw_price:
        item.unit_price = _parse_float(raw_price)
    item.total_price = round((item.unit_price or 0) * (item.quantity or 1), 2)
    order = item.order
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    db.session.commit()


def delete_item(item: OrderItem) -> None:
    order = item.order
    db.session.delete(item)
    db.session.flush()
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    db.session.commit()
