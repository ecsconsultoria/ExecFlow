"""order_service.py — Lógica de negócio para Pedidos (Orders).

Fluxo de status:
  novo → aberto → faturado → concluido
                ↘ cancelado
"""
from datetime import date, datetime, timedelta

from ..extensions import db
from ..models.order import Order, OrderItem, OrderPayment, ORDER_STATUSES  # noqa: F401
from ..utils import now_br
from ..utils.helpers import parse_brl
from . import margin_service


# ─────────────────────────────────────────────────────────────────────────────
# Criação
# ─────────────────────────────────────────────────────────────────────────────

def create_manual(company_id: int, user_id: int) -> Order:
    """Cria um Pedido em branco (sem orçamento vinculado)."""
    from . import numbering_service

    order = Order(
        company_id   = company_id,
        number       = numbering_service.next_order(company_id),
        status       = "novo",
        billing_type = "recibo",
        total_amount = 0,
        emission_date= now_br().date(),
        created_by   = user_id,
    )
    db.session.add(order)
    db.session.flush()
    return order


def create_from_quote(quote, user_id: int) -> Order:
    """Cria um Pedido (SO-AAMMDD-NNN) a partir de um Orçamento aprovado."""
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
            service_date        = qi.service_date,
            service_time        = qi.service_time,
        )
        # Auto-preencher op_pickup_datetime se service_date/service_time vierem da RFQ
        if qi.service_date:
            from datetime import datetime as _dt, time as _tm
            t = qi.service_time if qi.service_time else _tm(0, 0)
            item.op_pickup_datetime = _dt.combine(qi.service_date, t)
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
    # Operational fields
    for field in ("driver_name", "driver_phone", "vehicle_model", "vehicle_plate",
                  "pickup_location", "dropoff_location", "passenger_name", "passenger_phone",
                  "flight_number", "vehicle_description"):
        if field in data:
            setattr(order, field, data[field] or "")
    if "pax_count" in data:
        try:
            order.pax_count = int(data["pax_count"]) if data["pax_count"] else None
        except (ValueError, TypeError):
            pass
    db.session.commit()


def update_adjustments(order: Order, data: dict) -> None:
    """Atualiza desconto, frete e outros custos."""
    order.discount_type      = data.get("discount_type", "R$") or "R$"
    order.discount_value     = _parse_float(data.get("discount_value", 0))
    order.freight_amount     = _parse_float(data.get("freight_amount", 0))
    order.other_costs_amount = _parse_float(data.get("other_costs_amount", 0))
    order.other_costs_label  = data.get("other_costs_label", "") or ""
    if "usd_rate" in data:
        rate = _parse_float(data.get("usd_rate", 0))
        order.usd_rate = rate if rate and rate > 0 else None
    margin_service.recalculate_order(order)
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
    amount_changed = False
    if data.get("amount"):
        new_amount = _parse_float(data["amount"])
        if abs(new_amount - (payment.amount or 0)) > 0.001:
            payment.amount = new_amount
            amount_changed = True
    db.session.commit()
    # Sincroniza o lançamento financeiro pendente quando o valor muda
    if amount_changed and not payment.is_paid:
        try:
            from ..models.financial import FinancialRecord
            _ref = f"order_payment:{payment.id}"
            fr = FinancialRecord.query.filter_by(
                company_id=payment.order.company_id, reference=_ref
            ).first()
            if fr and fr.status != "pago":
                fr.amount = payment.amount or 0
                db.session.commit()
        except Exception:
            db.session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Transições de status
# ─────────────────────────────────────────────────────────────────────────────

def open_order(order: Order, user_id: int) -> None:
    if order.status != "novo":
        raise ValueError(f"Não é possível abrir pedido com status '{order.status}'")
    order.status    = "aberto"
    order.opened_at = now_br()
    order.opened_by = user_id
    db.session.commit()


def faturar(order: Order, data: dict, user_id: int) -> None:
    if order.status != "aberto":
        raise ValueError(f"Não é possível faturar pedido com status '{order.status}'")
    order.status          = "faturado"
    order.invoice_number  = data.get("invoice_number", "") or ""
    order.invoiced_at     = now_br()
    order.invoiced_by     = user_id
    if data.get("invoice_due_date"):
        try:
            order.invoice_due_date = date.fromisoformat(str(data["invoice_due_date"]))
        except (ValueError, TypeError):
            pass
    margin_service.recalculate_order(order)
    _sync_order_pending_financials(order)
    # Se todas as parcelas já estão pagas ao faturar, conclui automaticamente
    if order.payments:
        total_paid = sum(p.paid_amount or 0 for p in order.payments)
        if (all(p.is_paid for p in order.payments)
                and total_paid >= (order.computed_total or 0)):
            order.status    = "concluido"
            order.closed_at = now_br()
    db.session.commit()


def fechar(order: Order, user_id: int) -> None:
    if order.status not in ("faturado", "aberto"):
        raise ValueError(f"Não é possível fechar pedido com status '{order.status}'")
    order.status    = "concluido"
    order.closed_at = now_br()
    order.closed_by = user_id
    margin_service.recalculate_order(order)
    db.session.commit()


def cancel(order: Order, reason: str, user_id: int) -> None:
    if order.status in ("concluido", "cancelado"):
        raise ValueError(f"Não é possível cancelar pedido com status '{order.status}'")
    if order.payments and all(p.is_paid for p in order.payments):
        raise ValueError("Não é possível cancelar pedido com todas as parcelas pagas")
    if not (reason or "").strip():
        raise ValueError("Informe o motivo do cancelamento")

    order.status        = "cancelado"
    order.cancelled_at  = now_br()
    order.cancelled_by  = user_id
    order.cancel_reason = reason.strip()

    # Cancela FinancialRecords vinculados às parcelas do pedido
    from ..models.financial import FinancialRecord
    payment_refs = [f"order_payment:{p.id}" for p in order.payments]
    if payment_refs:
        frs = FinancialRecord.query.filter(
            FinancialRecord.company_id == order.company_id,
            FinancialRecord.deleted_at.is_(None),
            FinancialRecord.status.notin_(("cancelado", "pago")),
            FinancialRecord.reference.in_(payment_refs),
        ).all()
        for fr in frs:
            fr.status = "cancelado"

    # Cancela AccountReceivable vinculados ao orçamento
    if order.quote_id:
        from ..models.financial import AccountReceivable
        ars = AccountReceivable.query.filter_by(
            company_id=order.company_id,
            quote_id=order.quote_id,
            status="pendente",
        ).all()
        for ar in ars:
            ar.status = "cancelado"

    # Cascade para POs — Option A: cancela POs canceláveis, pula os demais (log de auditoria)
    from . import purchase_order_service as _pos
    from ..utils.audit import log_activity as _log
    _CANCELLABLE = ("rascunho", "aberto", "enviado", "aprovado")
    for po in order.purchase_orders:
        if po.status in _CANCELLABLE:
            _pos.cancel(po, user_id, reason=f"Cascade SO {order.number}: {reason.strip()}")
            _log("purchase_order", po.id, po.company_id,
                 f"Cancelada por cascade — SO {order.number}", user_id)
        else:
            _log("purchase_order", po.id, po.company_id,
                 f"PO {po.number} em status '{po.status}' — cancelamento manual necessário "
                 f"(SO {order.number} cancelado)", user_id)

    margin_service.recalculate_order(order)
    # Nota: db.session.commit() é responsabilidade da rota (não do serviço)


def reabrir(order: Order, user_id: int) -> None:
    """Reabre um pedido faturado, desde que sem impacto financeiro.

    Bloqueia a reabertura se houver:
    - Parcelas já pagas (exige estorno primeiro)
    - Lançamentos financeiros vinculados (exige cancelamento primeiro)
    """
    if order.status not in ("faturado", "concluido"):
        raise ValueError(f"Somente pedidos faturados ou concluídos podem ser reabertos (status atual: '{order.status}')")
    # Validação financeira
    if order.payments:
        paid = [p for p in order.payments if p.is_paid]
        if paid:
            raise ValueError(
                f"Existe(m) {len(paid)} parcela(s) já paga(s). "
                "Estorne os recebimentos antes de reabrir o pedido."
            )
    # Verifica lançamentos financeiros vinculados (apenas os pagos bloqueiam)
    from ..models.financial import FinancialRecord
    refs = [f"order_payment:{p.id}" for p in order.payments]
    if refs:
        fr_count = FinancialRecord.query.filter(
            FinancialRecord.reference.in_(refs),
            FinancialRecord.status == "pago",
            FinancialRecord.deleted_at.is_(None),
        ).count()
        if fr_count > 0:
            raise ValueError(
                f"Existe(m) {fr_count} lançamento(s) financeiro(s) pago(s) vinculado(s). "
                "Estorne os recebimentos antes de reabrir o pedido."
            )
    order.status         = "aberto"
    order.reopened_at    = now_br()
    order.reopened_by    = user_id
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


def baixa(payment: OrderPayment, paid_amount: float, user_id: int, paid_date: date | None = None) -> None:
    """Liquida uma parcela de Order.

    Toda a operação é atômica: o pagamento, o espelho financeiro,
    o recálculo de margem e o sync de parcelas pendentes são commitados
    juntos. Se qualquer etapa falhar, nada persiste.
    """
    _paid_date = paid_date if paid_date else now_br().date()
    _now = now_br()
    _paid_at = _now.replace(year=_paid_date.year, month=_paid_date.month, day=_paid_date.day)
    payment.paid_amount = paid_amount
    payment.paid_at     = _paid_at
    payment.paid_by     = user_id

    order = payment.order

    margin_service.recalculate_order(order)

    # Auto-conclui apenas se faturado E todas as parcelas pagas cobrem o total
    if order.status == "faturado":
        total_paid = sum(p.paid_amount or 0 for p in order.payments)
        if (all(p.is_paid for p in order.payments)
                and total_paid >= (order.computed_total or 0)):
            order.status    = "concluido"
            order.closed_at = now_br()

    # Espelho financeiro — criado ANTES do commit para atomicidade
    _sync_payment_financial_record(payment, order, _paid_date, paid_amount)
    _sync_order_pending_financials(order)

    db.session.commit()


def _sync_payment_financial_record(payment: OrderPayment, order, paid_date, paid_amount) -> None:
    """Cria/atualiza o FinancialRecord de uma parcela paga (receita).

    Chamado ANTES do commit principal para garantir atomicidade.
    """
    from ..models.financial import FinancialRecord
    _ref = f"order_payment:{payment.id}"
    fr = FinancialRecord.query.filter_by(
        company_id=order.company_id, reference=_ref
    ).filter(FinancialRecord.deleted_at.is_(None)).first()
    if fr:
        fr.amount        = paid_amount
        fr.paid_date     = paid_date
        fr.emission_date = order.emission_date
        fr.status        = "pago"
    else:
        total_inst = len(order.payments)
        db.session.add(FinancialRecord(
            company_id     = order.company_id,
            type           = "revenue",
            category       = "receita_servico",
            description    = f"{order.number} — parcela {payment.installment_no}/{total_inst}",
            amount         = paid_amount,
            status         = "pago",
            payment_method = order.payment_method or "",
            emission_date  = order.emission_date,
            paid_date      = paid_date,
            reference      = _ref,
        ))


def _sync_order_pending_financials(order: Order) -> None:
    """Cria/atualiza lançamentos pendentes de receita para parcelas em aberto do SO.

    Não faz rollback — o caller gerencia a transação.
    """
    from ..models.financial import FinancialRecord
    total_inst = len(order.payments)
    for p in order.payments:
        if p.is_paid:
            continue
        _ref = f"order_payment:{p.id}"
        fr = FinancialRecord.query.filter_by(
            company_id=order.company_id, reference=_ref
        ).filter(FinancialRecord.deleted_at.is_(None)).first()
        if fr and fr.status != "pago":
            fr.type           = "revenue"
            fr.category       = "receita_servico"
            fr.description    = f"{order.number} — parcela {p.installment_no}/{total_inst}"
            fr.amount         = p.amount or 0
            fr.status         = "pendente"
            fr.payment_method = order.payment_method or ""
            fr.emission_date  = order.emission_date
            fr.due_date       = p.due_date
            fr.paid_date      = None
        elif not fr:
            db.session.add(FinancialRecord(
                company_id     = order.company_id,
                type           = "revenue",
                category       = "receita_servico",
                description    = f"{order.number} — parcela {p.installment_no}/{total_inst}",
                amount         = p.amount or 0,
                status         = "pendente",
                payment_method = order.payment_method or "",
                emission_date  = order.emission_date,
                due_date       = p.due_date,
                reference      = _ref,
            ))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _parse_float(value) -> float:
    try:
        return parse_brl(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_item_pickup_datetime(data: dict):
    date_str = (data.get("op_pickup_date") or "").strip()
    time_str = (data.get("op_pickup_time") or "").strip()
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str or '00:00'}")
    except (TypeError, ValueError):
        return None


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
        driver_name         = data.get("driver_type", "") or "",
        quantity            = qty,
        unit_price          = price,
        total_price         = round(price * qty, 2),
        sort_order          = max((i.sort_order or 0 for i in order.items), default=0) + 1,
    )
    db.session.add(item)
    db.session.flush()
    db.session.expire(order, ['items'])  # força reload para incluir o novo item no total
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    margin_service.recalculate_order(order)
    db.session.commit()
    return item


def update_item(item: OrderItem, data: dict) -> None:
    """Atualiza quantidade, valor unitário, categoria e motorista de um item do pedido."""
    raw_qty   = data.get("quantity", "")
    raw_price = data.get("unit_price", "")
    if raw_qty:
        item.quantity = max(1, int(raw_qty))
    if raw_price:
        item.unit_price = _parse_float(raw_price)
    if "category_id" in data:
        cid = data.get("category_id")
        item.category_id = int(cid) if cid and str(cid).strip() else None
    if "driver_name" in data:
        item.driver_name = (data.get("driver_name") or "").strip() or None
    if "description" in data:
        item.description = (data.get("description") or "").strip()
    item.total_price = round((item.unit_price or 0) * (item.quantity or 1), 2)
    order = item.order
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    margin_service.recalculate_order(order)
    db.session.commit()


def update_item_operational(item: OrderItem, data: dict, apply_to_all: bool = False) -> None:
    """Atualiza dados operacionais por item; opcionalmente replica para todos os itens da SO."""
    pickup_dt = _parse_item_pickup_datetime(data)

    base_payload = {
        "op_driver_name": data.get("op_driver_name", "") or "",
        "op_driver_phone": data.get("op_driver_phone", "") or "",
        "op_vehicle_model": data.get("op_vehicle_model", "") or "",
        "op_vehicle_plate": data.get("op_vehicle_plate", "") or "",
        "op_pickup_datetime": pickup_dt,
        "op_pickup_location": data.get("op_pickup_location", "") or "",
        "op_dropoff_location": data.get("op_dropoff_location", "") or "",
        "op_passenger_name": data.get("op_passenger_name", "") or "",
        "op_passenger_phone": data.get("op_passenger_phone", "") or "",
        "op_flight_number": data.get("op_flight_number", "") or "",
        "op_notes": data.get("op_notes", "") or "",
    }

    targets = item.order.items if apply_to_all else [item]
    for target in targets:
        for field, value in base_payload.items():
            setattr(target, field, value)

    db.session.commit()


def delete_item(item: OrderItem) -> None:
    order = item.order
    db.session.delete(item)
    db.session.flush()
    db.session.expire(order, ['items'])  # força reload para excluir o item deletado do total
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    margin_service.recalculate_order(order)
    db.session.commit()
