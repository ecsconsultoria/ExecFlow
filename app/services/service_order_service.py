"""ServiceOrderService — lógica de negócio central da OS.

Métodos principais:
- create_from_booking(booking, quote, user_id)
- create_manual(company_id, data, user_id)
- assign_driver(os, driver_id, vehicle_id, user_id)
- assign_supplier(os, supplier_id, data, user_id)
- add_cost(os, cost_type, amount, description, user_id, **kw)
- recalculate_margin(os)
- update_status(os, new_status, user_id, description=None)
- add_event(os, event_type, description, user_id, metadata=None)
- close(os, user_id)
- send_driver_info(os, user_id)
"""
from datetime import datetime

from ..extensions import db
from ..models import (
    ServiceOrder, ServiceOrderAssignment, ServiceOrderEvent,
    OperationCost, RevenueEntry, SupplierPayment,
)
from ..utils import now_br


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _next_os_code(company_id: int) -> str:
    """Gera o próximo código OS-AAMMDD-NNN para a empresa."""
    from . import numbering_service
    return numbering_service.next_os(company_id)


# ─────────────────────────────────────────────────────────────────────────────
# Criação
# ─────────────────────────────────────────────────────────────────────────────

def create_from_booking(booking, quote, user_id: int) -> ServiceOrder:
    """Cria OS automaticamente a partir de um Booking confirmado."""
    os = ServiceOrder(
        code        = _next_os_code(booking.company_id),
        company_id  = booking.company_id,
        booking_id  = booking.id,
        quote_id    = quote.id if quote else None,
        client_id   = booking.client_id,
        created_by  = user_id,

        passenger_name  = (booking.client.name if booking.client else ""),
        passenger_phone = (booking.client.phone if booking.client else ""),
        passenger_email = (booking.client.email if booking.client else ""),
        pax_count       = booking.pax_count or 1,
        language        = (booking.client.language if booking.client else "pt"),

        pickup_datetime  = booking.service_date,
        pickup_location  = booking.pickup_address,
        dropoff_location = booking.dropoff_address,
        flight_number    = booking.flight_number,
        notes            = booking.notes,
        status           = "agendado",

        revenue_amount = quote.total_amount if quote else 0.0,
    )
    db.session.add(os)
    db.session.flush()  # get os.id

    # RevenueEntry inicial
    re = RevenueEntry(
        service_order_id = os.id,
        company_id       = os.company_id,
        client_id        = os.client_id,
        created_by       = user_id,
        amount           = os.revenue_amount,
        billing_type     = quote.billing_type if quote else "recibo",
        description      = f"Receita gerada do orçamento {quote.number}" if quote else "Receita da OS",
        status           = "pendente",
    )
    db.session.add(re)

    add_event(os, "criado", f"OS criada a partir do booking {booking.number}", user_id)
    recalculate_margin(os)
    return os


def create_manual(company_id: int, data: dict, user_id: int) -> ServiceOrder:
    """Cria OS manualmente (sem booking/orçamento)."""
    os = ServiceOrder(
        code       = _next_os_code(company_id),
        company_id = company_id,
        created_by = user_id,
        status     = "criado",
        **{k: v for k, v in data.items() if hasattr(ServiceOrder, k)},
    )
    db.session.add(os)
    db.session.flush()
    add_event(os, "criado", "OS criada manualmente", user_id)
    recalculate_margin(os)
    return os


def create_from_quote(quote, user_id: int, form_data: dict = None) -> ServiceOrder:
    """Cria OS diretamente a partir de um orçamento aprovado (sem Booking intermediário)."""
    fd = form_data or {}
    os_obj = ServiceOrder(
        code             = _next_os_code(quote.company_id),
        company_id       = quote.company_id,
        quote_id         = quote.id,
        client_id        = quote.client_id,
        created_by       = user_id,
        passenger_name   = fd.get("passenger_name")  or (quote.client.name  if quote.client else ""),
        passenger_phone  = fd.get("passenger_phone") or (quote.client.phone if quote.client and hasattr(quote.client, "phone") else ""),
        passenger_email  = (quote.client.email if quote.client else ""),
        pax_count        = int(fd.get("pax_count") or 1),
        language         = (quote.language or "pt"),
        pickup_datetime  = fd.get("pickup_datetime"),
        pickup_location  = fd.get("pickup_location"),
        dropoff_location = fd.get("dropoff_location"),
        flight_number    = fd.get("flight_number"),
        notes            = fd.get("notes"),
        status           = "criado",
        revenue_amount   = quote.total_amount or 0.0,
    )
    db.session.add(os_obj)
    db.session.flush()

    re = RevenueEntry(
        service_order_id = os_obj.id,
        company_id       = os_obj.company_id,
        client_id        = os_obj.client_id,
        created_by       = user_id,
        amount           = os_obj.revenue_amount,
        billing_type     = quote.billing_type or "recibo",
        description      = f"Receita do orçamento {quote.number}",
        status           = "pendente",
    )
    db.session.add(re)

    quote.status = "reserva_confirmada"
    add_event(os_obj, "criado", f"OS criada a partir do orçamento {quote.number}", user_id)
    recalculate_margin(os_obj)
    return os_obj


# ─────────────────────────────────────────────────────────────────────────────
# Atribuição
# ─────────────────────────────────────────────────────────────────────────────

def assign_driver(os: ServiceOrder, driver_id: int, vehicle_id: int, user_id: int,
                  notes: str = "") -> ServiceOrderAssignment:
    """Atribui motorista interno. Desativa atribuição anterior."""
    # Desativa anteriores
    (ServiceOrderAssignment.query
     .filter_by(service_order_id=os.id, is_current=True)
     .update({"is_current": False}))

    asgn = ServiceOrderAssignment(
        service_order_id = os.id,
        assigned_by      = user_id,
        assigned_at      = now_br(),
        assignment_type  = "internal",
        driver_id        = driver_id,
        vehicle_id       = vehicle_id,
        is_current       = True,
        notes            = notes,
    )
    db.session.add(asgn)

    # Atualiza snapshot na OS
    os.assigned_driver_id  = driver_id
    os.assigned_vehicle_id = vehicle_id
    os.supplier_id         = None

    if os.status == "agendado":
        os.status = "atribuido"

    driver_name = asgn.driver.name if asgn.driver else str(driver_id)
    add_event(os, "motorista_atribuido", f"Motorista {driver_name} atribuído", user_id)
    return asgn


def assign_supplier(os: ServiceOrder, supplier_id: int, supplier_driver_name: str,
                    supplier_vehicle: str, supplier_contact: str, supplier_price: float,
                    user_id: int, notes: str = "") -> ServiceOrderAssignment:
    """Atribui fornecedor terceirizado. Desativa atribuição anterior."""
    (ServiceOrderAssignment.query
     .filter_by(service_order_id=os.id, is_current=True)
     .update({"is_current": False}))

    asgn = ServiceOrderAssignment(
        service_order_id     = os.id,
        assigned_by          = user_id,
        assigned_at          = now_br(),
        assignment_type      = "outsourced",
        supplier_id          = supplier_id,
        supplier_driver_name = supplier_driver_name,
        supplier_vehicle     = supplier_vehicle,
        supplier_contact     = supplier_contact,
        supplier_price       = supplier_price,
        is_current           = True,
        notes                = notes,
    )
    db.session.add(asgn)

    # Atualiza snapshot na OS
    os.supplier_id           = supplier_id
    os.supplier_driver_name  = supplier_driver_name
    os.supplier_vehicle_desc = supplier_vehicle
    os.supplier_contact      = supplier_contact
    os.assigned_driver_id    = None
    os.assigned_vehicle_id   = None

    if os.status in ("agendado", "criado"):
        os.status = "atribuido"

    # SupplierPayment automático
    if supplier_price and supplier_price > 0:
        sp = SupplierPayment(
            service_order_id = os.id,
            supplier_id      = supplier_id,
            company_id       = os.company_id,
            created_by       = user_id,
            amount           = supplier_price,
            description      = f"Repasse fornecedor para {os.code}",
        )
        db.session.add(sp)

        # Cria também como OperationCost do tipo supplier
        add_cost(os, "supplier", supplier_price,
                 description=f"Custo fornecedor (auto)", user_id=user_id, _flush=False)
        recalculate_margin(os)

    supplier_name = asgn.supplier.name if asgn.supplier else str(supplier_id)
    add_event(os, "fornecedor_atribuido", f"Fornecedor {supplier_name} atribuído", user_id,
              metadata={"supplier_price": supplier_price})
    return asgn


# ─────────────────────────────────────────────────────────────────────────────
# Custos
# ─────────────────────────────────────────────────────────────────────────────

def add_cost(os: ServiceOrder, cost_type: str, amount: float,
             description: str = "", user_id: int = None,
             reference: str = "", notes: str = "", _flush: bool = True) -> OperationCost:
    """Adiciona um custo operacional e recalcula a margem da OS."""
    cost = OperationCost(
        service_order_id = os.id,
        company_id       = os.company_id,
        created_by       = user_id,
        cost_type        = cost_type,
        amount           = amount,
        description      = description,
        reference        = reference,
        notes            = notes,
    )
    db.session.add(cost)
    if _flush:
        db.session.flush()
        recalculate_margin(os)
        add_event(os, "custo_adicionado",
                  f"Custo {cost.cost_type_label}: R$ {amount:.2f}", user_id)
    return cost


def recalculate_margin(os: ServiceOrder):
    """Recalcula total_cost_amount e margin_amount a partir de todos os OperationCost."""
    db.session.flush()  # garante que custos pendentes estão visíveis
    total = (db.session.query(db.func.sum(OperationCost.amount))
             .filter_by(service_order_id=os.id)
             .scalar()) or 0.0
    os.total_cost_amount = round(total, 2)
    os.margin_amount     = round((os.revenue_amount or 0) - os.total_cost_amount, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Status & Eventos
# ─────────────────────────────────────────────────────────────────────────────

def update_status(os: ServiceOrder, new_status: str, user_id: int,
                  description: str = "") -> ServiceOrder:
    """Altera o status da OS e registra evento na timeline."""
    old_status = os.status
    os.status  = new_status

    if new_status == "em_execucao" and not os.executed_at:
        os.executed_at = now_br()
    elif new_status == "finalizado" and not os.closed_at:
        os.closed_at = now_br()

    desc = description or f"Status alterado de '{old_status}' para '{new_status}'"
    add_event(os, "status_alterado", desc, user_id,
              metadata={"old": old_status, "new": new_status})
    return os


def add_event(os: ServiceOrder, event_type: str, description: str,
              user_id: int = None, metadata: dict = None) -> ServiceOrderEvent:
    """Registra um evento na timeline da OS."""
    ev = ServiceOrderEvent(
        service_order_id = os.id,
        user_id          = user_id,
        event_type       = event_type,
        description      = description,
        metadata         = metadata,
    )
    db.session.add(ev)
    return ev


def close(os: ServiceOrder, user_id: int, notes: str = "") -> ServiceOrder:
    """Finaliza a OS: status=finalizado, registra closed_at e evento."""
    os.status    = "finalizado"
    os.closed_at = now_br()
    recalculate_margin(os)
    add_event(os, "finalizado",
              notes or f"OS {os.code} finalizada",
              user_id,
              metadata={"revenue": os.revenue_amount, "cost": os.total_cost_amount,
                        "margin": os.margin_amount})
    return os


def send_driver_info(os: ServiceOrder, user_id: int) -> ServiceOrder:
    """Marca que as informações de motorista/fornecedor foram enviadas ao cliente."""
    os.driver_info_sent    = True
    os.driver_info_sent_at = now_br()
    add_event(os, "dados_enviados_cliente",
              "Dados do motorista enviados ao passageiro", user_id)
    return os
