"""purchase_order_service.py — Lógica de negócio para Purchase Orders (PO).

PO = despesa / contas a pagar (contraparte de custo do Pedido SO).
Fluxo: rascunho → aberto → aprovado → em_execucao → concluido
"""
from datetime import datetime, timedelta, date
from ..extensions import db
from ..models.purchase_order import PurchaseOrder, POPayment, POItem, PO_STATUSES
from ..utils import now_br
from ..utils.helpers import parse_brl
from . import numbering_service
from . import margin_service


# ─────────────────────────────────────────────────────────────────────────────
# Criação
# ─────────────────────────────────────────────────────────────────────────────

def create(company_id: int, data: dict, user_id: int) -> PurchaseOrder:
    """Cria uma PO manualmente a partir de um dict de formulário."""
    po = PurchaseOrder(
        number     = numbering_service.next_po(company_id),
        company_id = company_id,
        created_by = user_id,
        status     = "rascunho",
    )
    _apply_data(po, data)
    db.session.add(po)
    db.session.flush()
    return po


def create_from_order(order, user_id: int) -> PurchaseOrder:
    """Cria PO a partir de uma Order (SO), copiando itens e ajustes financeiros.

    Se já existir uma PO em rascunho para esta Order, retorna a existente
    em vez de criar duplicata. Rascunhos só aparecem na listagem após salvar.
    """
    from ..models.order import Order
    existing = PurchaseOrder.query.filter_by(
        order_id=order.id, status="rascunho",
    ).filter(PurchaseOrder.deleted_at.is_(None)).first()
    if existing:
        return existing
    po = PurchaseOrder(
        number             = numbering_service.next_po(order.company_id),
        company_id         = order.company_id,
        created_by         = user_id,
        order_id           = order.id,
        status             = "rascunho",
        discount_type      = order.discount_type or "R$",
        discount_value     = order.discount_value or 0,
        freight_amount     = order.freight_amount or 0,
        other_costs_amount = order.other_costs_amount or 0,
        other_costs_label  = order.other_costs_label or "",
    )
    db.session.add(po)
    db.session.flush()

    # Resolve preço de custo da tabela ServicePricing
    from ..models.service import ServicePricing
    for idx, item in enumerate(order.items):
        cost_price = item.unit_price or 0
        if item.service_id and item.category_id:
            driver_type = item.driver_name or ""
            pricing = ServicePricing.query.filter_by(
                service_id=item.service_id,
                category_id=item.category_id,
                driver_type=driver_type,
            ).first()
            if pricing and pricing.price_cost:
                cost_price = pricing.price_cost
        qty = item.quantity or 1
        poi = POItem(
            po_id       = po.id,
            service_id  = item.service_id,
            category_id = item.category_id,
            description = item.description or "",
            quantity    = qty,
            unit_cost   = cost_price,
            total_cost  = round(cost_price * qty, 2),
            sort_order  = idx,
        )
        db.session.add(poi)
    return po


def create_from_service_order(service_order, user_id: int) -> PurchaseOrder:
    """Cria PO automaticamente a partir de uma OS do Centro de Despacho."""
    po = PurchaseOrder(
        number           = numbering_service.next_po(service_order.company_id),
        company_id       = service_order.company_id,
        created_by       = user_id,
        service_order_id = service_order.id,
        supplier_id      = service_order.supplier_id,
        service_id       = service_order.service_id,
        passenger_name   = service_order.passenger_name,
        passenger_phone  = service_order.passenger_phone,
        pax_count        = service_order.pax_count or 1,
        pickup_datetime  = service_order.pickup_datetime,
        pickup_location  = service_order.pickup_location,
        dropoff_location = service_order.dropoff_location,
        flight_number    = service_order.flight_number,
        amount           = service_order.supplier_amount or 0.0,
        notes            = service_order.notes,
        status           = "rascunho",
    )
    db.session.add(po)
    db.session.flush()
    return po


# ─────────────────────────────────────────────────────────────────────────────
# Transições de status
# ─────────────────────────────────────────────────────────────────────────────

def open_po(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Abre a PO para processamento."""
    _assert_status(po, ["rascunho"])
    po.status  = "aberto"
    po.sent_at = now_br()
    return po


def send(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Compat backward — mantém chamadas antigas para abrir a PO."""
    return open_po(po, user_id)


def approve(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Fornecedor confirmou a PO."""
    _assert_status(po, ["aberto", "enviado"])
    po.status      = "aprovado"
    po.approved_at = now_br()
    return po


def start_execution(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Inicia execução do serviço."""
    _assert_status(po, ["aprovado"])
    po.status = "em_execucao"
    return po


def conclude(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Conclui a PO — serviço executado."""
    _assert_status(po, ["em_execucao", "aprovado"])
    po.status       = "concluido"
    po.concluded_at = now_br()
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    return po


def reabrir(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Reabre uma PO faturada, voltando para status 'aberto'."""
    if po.status != "faturado":
        raise ValueError(f"Somente POs faturadas podem ser reabertas (status atual: '{po.status}')")
    po.status       = "aberto"
    po.reopened_at  = now_br()
    po.reopened_by  = user_id
    po.invoiced_at  = None
    po.invoiced_by  = None
    db.session.commit()
    return po


def faturar(po: PurchaseOrder, user_id: int) -> PurchaseOrder:
    """Fatura a PO — nota fiscal do fornecedor recebida."""
    if po.status in ("faturado", "cancelado", "excluido"):
        raise ValueError(f"Não é possível faturar PO com status '{po.status}'")
    if not po.supplier_id:
        raise ValueError("Selecione o Fornecedor antes de faturar.")
    if not list(po.payments):
        raise ValueError("Gere as contas a pagar antes de faturar.")
    po.status      = "faturado"
    po.invoiced_at = now_br()
    po.invoiced_by = user_id
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    _sync_po_pending_financials(po)
    return po


def cancel(po: PurchaseOrder, user_id: int, reason: str = "") -> PurchaseOrder:
    """Cancela a PO."""
    if not (reason or "").strip():
        raise ValueError("Informe o motivo do cancelamento")
    _assert_status(po, ["rascunho", "aberto", "enviado", "aprovado"])
    po.status       = "cancelado"
    po.cancelled_at = now_br()
    po.internal_notes = (po.internal_notes or "") + (
        f"\n[Cancelado em {now_br().strftime('%d/%m/%Y %H:%M')} por user_id={user_id}] {reason.strip()}"
    )

    # Cancela FinancialRecords vinculados aos pagamentos desta PO
    from ..models.financial import FinancialRecord
    payment_refs = [f"po_payment:{p.id}" for p in po.payments.all()]
    if payment_refs:
        frs = FinancialRecord.query.filter(
            FinancialRecord.company_id == po.company_id,
            FinancialRecord.deleted_at.is_(None),
            FinancialRecord.status.notin_(("cancelado", "pago")),
            FinancialRecord.reference.in_(payment_refs),
        ).all()
        for fr in frs:
            fr.status = "cancelado"

    # Recalcula margem do SO vinculado, se houver
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)

    return po


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _apply_data(po: PurchaseOrder, data: dict):
    """Aplica dict de formulário ao objeto PO, ignorando campos inexistentes."""
    from datetime import datetime, date as date_type
    safe = {k: v for k, v in data.items() if hasattr(PurchaseOrder, k)}

    def _to_float(v, default=0.0):
        if v in (None, ""):
            return default
        try:
            return parse_brl(v)
        except (ValueError, TypeError):
            return default

    for f in ("amount", "discount_value", "freight_amount", "other_costs_amount"):
        if f in safe:
            safe[f] = _to_float(safe[f], 0.0)

    if "pax_count" in safe:
        try:
            safe["pax_count"] = int(safe["pax_count"]) if safe["pax_count"] not in (None, "") else 1
        except (ValueError, TypeError):
            safe["pax_count"] = 1

    if "discount_type" in safe:
        safe["discount_type"] = safe["discount_type"] or "R$"

    # Parse de tipos especiais
    if "pickup_datetime" in safe and safe["pickup_datetime"]:
        if isinstance(safe["pickup_datetime"], str):
            try:
                safe["pickup_datetime"] = datetime.strptime(safe["pickup_datetime"], "%Y-%m-%dT%H:%M")
            except ValueError:
                safe.pop("pickup_datetime", None)

    if "payment_due_date" in safe:
        val = safe["payment_due_date"]
        if val and isinstance(val, str):
            try:
                safe["payment_due_date"] = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                safe["payment_due_date"] = None
        elif not val:
            safe["payment_due_date"] = None

    # Campos nullable FK: converter string vazia para None
    for fk_field in ("supplier_id", "service_id", "service_order_id", "order_id",
                     "quote_id", "vehicle_category_id"):
        if fk_field in safe and safe[fk_field] in ("", None):
            safe[fk_field] = None
        elif fk_field in safe:
            try:
                safe[fk_field] = int(safe[fk_field])
            except (ValueError, TypeError):
                safe[fk_field] = None

    for k, v in safe.items():
        setattr(po, k, v)


def _assert_status(po: PurchaseOrder, allowed: list):
    if po.status not in allowed:
        raise ValueError(
            f"Operação inválida: PO {po.number} está '{po.status}', "
            f"esperado: {allowed}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pagamentos / Parcelas (Contas a Pagar)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_float(val) -> float:
    try:
        return parse_brl(val)
    except (ValueError, TypeError):
        return 0.0


def generate_payments(po: PurchaseOrder, custom_total: float = None) -> list:
    """Gera parcelas de custo baseado em payment_terms.

    Modo ADD (custom_total fornecido): acrescenta UMA parcela do valor informado.
    Modo REGENERAR (sem custom_total): apaga não-pagas e recria pelo prazo.
    """
    from datetime import date as date_type
    today = now_br().date()

    if custom_total is not None:
        existing      = list(po.payments)
        already_alloc = sum(p.amount or 0 for p in existing)
        unscheduled   = round(po.computed_total - already_alloc, 2)
        first_amt     = min(round(custom_total, 2), max(unscheduled, 0))
        if first_amt < 0.01:
            return []
        next_no = max((p.installment_no for p in existing), default=0) + 1
        pmt = POPayment(
            po_id          = po.id,
            installment_no = next_no,
            due_date       = today,
            amount         = first_amt,
            paid_amount    = 0,
        )
        db.session.add(pmt)
        db.session.commit()
        return [pmt]

    # REGENERATE MODE
    paid_pmts = [p for p in po.payments if p.is_paid]
    unpaid    = [p for p in po.payments if not p.is_paid]
    for p in unpaid:
        db.session.delete(p)
    db.session.flush()

    already_paid = sum(p.paid_amount or 0 for p in paid_pmts)
    remaining    = round(po.computed_total - already_paid, 2)
    terms_upper  = (po.payment_terms or "").upper().strip()
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
            (next_no,     today,                          half),
            (next_no + 1, today + timedelta(days=30),     remaining - half),
        ]
    elif "DIAS" in terms_upper:
        installments = [(next_no, today + timedelta(days=defer_days), remaining)]
    else:
        installments = [(next_no, today, remaining)]

    created = []
    for no, due, amount in installments:
        pmt = POPayment(
            po_id          = po.id,
            installment_no = no,
            due_date       = due,
            amount         = amount,
            paid_amount    = 0,
        )
        db.session.add(pmt)
        created.append(pmt)

    db.session.commit()
    return created


def update_payment_inline(payment: POPayment, data: dict) -> None:
    from datetime import date as date_type
    if data.get("due_date"):
        try:
            payment.due_date = date_type.fromisoformat(str(data["due_date"]))
        except (ValueError, TypeError):
            pass
    if "notes" in data:
        payment.notes = data["notes"] or ""
    if data.get("amount"):
        payment.amount = _parse_float(data["amount"])
    db.session.commit()


def delete_payment(payment: POPayment) -> None:
    if payment.is_paid:
        raise ValueError("Não é possível excluir parcela já paga")
    db.session.delete(payment)
    db.session.commit()


def baixa(payment: POPayment, paid_amount: float, user_id: int, paid_date: date | None = None) -> None:
    """Liquida uma parcela de PurchaseOrder.

    Toda a operação é atômica: o pagamento, o espelho financeiro,
    e o sync de parcelas pendentes são commitados juntos.
    Se qualquer etapa falhar, nada persiste.
    """
    _paid_date = paid_date if paid_date else now_br().date()
    _now = now_br()
    _paid_at = _now.replace(year=_paid_date.year, month=_paid_date.month, day=_paid_date.day)
    payment.paid_amount = paid_amount
    payment.paid_at     = _paid_at
    payment.paid_by     = user_id

    po = payment.purchase_order

    # Auto-avança PO para 'pago' quando todas as parcelas forem quitadas
    if po.status == "faturado":
        all_pmts     = list(po.payments)
        total_amount = sum(p.amount or 0 for p in all_pmts)
        total_paid   = sum(
            paid_amount if p.id == payment.id else (p.paid_amount or 0)
            for p in all_pmts
        )
        if total_amount > 0 and total_paid >= total_amount:
            po.status   = "pago"
            po.paid_at  = now_br()

    # Espelho financeiro — criado ANTES do commit para atomicidade
    _sync_po_payment_financial_record(payment, po, _paid_date, paid_amount)
    _sync_po_pending_financials(po)

    db.session.commit()


def _sync_po_payment_financial_record(payment: POPayment, po, paid_date, paid_amount) -> None:
    """Cria/atualiza o FinancialRecord de uma parcela paga (custo).

    Chamado ANTES do commit principal para garantir atomicidade.
    """
    from ..models.financial import FinancialRecord
    _ref = f"po_payment:{payment.id}"
    fr = FinancialRecord.query.filter_by(
        company_id=po.company_id, reference=_ref
    ).filter(FinancialRecord.deleted_at.is_(None)).first()
    if fr:
        fr.amount        = paid_amount
        fr.paid_date     = paid_date
        fr.emission_date = po.created_at.date() if po.created_at else None
        fr.status        = "pago"
    else:
        total_inst    = len(list(po.payments))
        supplier_name = (po.supplier.name if po.supplier else "") or ""
        desc = f"{po.number}"
        if supplier_name:
            desc += f" — {supplier_name}"
        desc += f" — parcela {payment.installment_no}/{total_inst}"
        db.session.add(FinancialRecord(
            company_id     = po.company_id,
            type           = "cost",
            category       = "custo_fornecedor",
            description    = desc,
            amount         = paid_amount,
            status         = "pago",
            payment_method = getattr(po, "payment_method", "") or "",
            emission_date  = po.created_at.date() if po.created_at else None,
            paid_date      = paid_date,
            reference      = _ref,
        ))


def _sync_po_pending_financials(po: PurchaseOrder) -> None:
    """Cria/atualiza lançamentos pendentes de custo para parcelas em aberto da PO.

    Não faz rollback — o caller gerencia a transação.
    """
    from ..models.financial import FinancialRecord
    total_inst    = len(list(po.payments))
    supplier_name = (po.supplier.name if po.supplier else "") or ""
    for p in po.payments:
        if p.is_paid:
            continue
        _ref = f"po_payment:{p.id}"
        desc = f"{po.number}"
        if supplier_name:
            desc += f" — {supplier_name}"
        desc += f" — parcela {p.installment_no}/{total_inst}"
        fr = FinancialRecord.query.filter_by(
            company_id=po.company_id, reference=_ref
        ).filter(FinancialRecord.deleted_at.is_(None)).first()
        if fr and fr.status != "pago":
            fr.type           = "cost"
            fr.category       = "custo_fornecedor"
            fr.description    = desc
            fr.amount         = p.amount or 0
            fr.status         = "pendente"
            fr.payment_method = getattr(po, "payment_method", "") or ""
            fr.emission_date  = po.created_at.date() if po.created_at else None
            fr.due_date       = p.due_date
            fr.paid_date      = None
        elif not fr:
            db.session.add(FinancialRecord(
                company_id     = po.company_id,
                type           = "cost",
                category       = "custo_fornecedor",
                description    = desc,
                amount         = p.amount or 0,
                status         = "pendente",
                payment_method = getattr(po, "payment_method", "") or "",
                emission_date  = po.created_at.date() if po.created_at else None,
                due_date       = p.due_date,
                reference      = _ref,
            ))


# ─────────────────────────────────────────────────────────────────────────────
# Itens da PO
# ─────────────────────────────────────────────────────────────────────────────

def _parse_cost(val) -> float:
    try:
        return parse_brl(val)
    except (ValueError, TypeError):
        return 0.0


def add_item(po: PurchaseOrder, data: dict) -> POItem:
    """Adiciona um POItem à PO e atualiza o total.

    Se service_id + category_id forem informados, busca o price_cost
    da tabela ServicePricing (respeitando driver_type se informado).
    Caso contrário, usa o unit_cost do formulário.
    """
    service_id  = int(data["service_id"])  if data.get("service_id")  else None
    category_id = int(data["category_id"]) if data.get("category_id") else None
    driver_type = (data.get("driver_type") or "").strip()
    qty         = max(int(data.get("quantity") or 1), 1)
    unit_cost   = _parse_cost(data.get("unit_cost", 0))

    # Se não foi informado custo manual, busca o price_cost da tabela
    if unit_cost == 0 and service_id and category_id:
        from ..models.service import ServicePricing
        q_pricing = ServicePricing.query.filter_by(
            service_id=service_id, category_id=category_id, is_active=True,
        )
        if driver_type:
            pricing = q_pricing.filter_by(driver_type=driver_type).first()
        else:
            pricing = q_pricing.first()
        if pricing and pricing.price_cost:
            unit_cost = pricing.price_cost
    total_cost = round(unit_cost * qty, 2)

    # Default description = nome do serviço se não informado
    description = (data.get("description") or "").strip()
    if not description and service_id:
        from ..models.service import Service
        svc = Service.query.get(service_id)
        if svc:
            description = svc.name

    sort_order = len(po.items)
    item = POItem(
        po_id       = po.id,
        service_id  = service_id,
        category_id = category_id,
        description = description,
        quantity    = qty,
        unit_cost   = unit_cost,
        total_cost  = total_cost,
        sort_order  = sort_order,
    )
    db.session.add(item)
    db.session.flush()
    return item


def update_item(item: POItem, data: dict) -> POItem:
    """Atualiza quantidade e custo unitário de um POItem."""
    if "quantity" in data:
        item.quantity = max(int(data["quantity"] or 1), 1)
    if "unit_cost" in data:
        item.unit_cost = _parse_cost(data["unit_cost"])
    if "description" in data:
        item.description = (data["description"] or "").strip()
    item.total_cost = round((item.unit_cost or 0) * (item.quantity or 1), 2)
    db.session.flush()
    return item


def delete_item(item: POItem) -> None:
    """Remove um POItem."""
    db.session.delete(item)
    db.session.flush()


def _parse_item_pickup_datetime(data: dict):
    date_str = (data.get("op_pickup_date") or "").strip()
    time_str = (data.get("op_pickup_time") or "").strip()
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str or '00:00'}")
    except (TypeError, ValueError):
        return None


def update_item_operational(item: POItem, data: dict, apply_to_all: bool = False) -> None:
    """Atualiza dados operacionais por item de PO; opcionalmente replica para todos os itens."""
    pickup_dt = _parse_item_pickup_datetime(data)

    raw_pax = (data.get("op_pax_count") or "").strip() if isinstance(data.get("op_pax_count"), str) else data.get("op_pax_count")
    try:
        pax_count = int(raw_pax) if raw_pax not in (None, "") else None
    except (TypeError, ValueError):
        pax_count = None

    base_payload = {
        "op_pickup_datetime": pickup_dt,
        "op_pickup_location": data.get("op_pickup_location", "") or "",
        "op_dropoff_location": data.get("op_dropoff_location", "") or "",
        "op_passenger_name": data.get("op_passenger_name", "") or "",
        "op_passenger_phone": data.get("op_passenger_phone", "") or "",
        "op_flight_number": data.get("op_flight_number", "") or "",
        "op_pax_count": pax_count,
        "op_notes": data.get("op_notes", "") or "",
    }

    targets = item.purchase_order.items if apply_to_all else [item]
    for target in targets:
        for field, value in base_payload.items():
            setattr(target, field, value)

    db.session.flush()
