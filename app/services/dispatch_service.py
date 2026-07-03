"""DispatchService — Centro de Operações baseado em Sales Orders.

Consulta OrderItems com dados operacionais preenchidos (op_pickup_datetime)
e os apresenta como agenda operacional. NÃO cria registros — apenas lê e
atualiza campos operacionais existentes.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Order, OrderItem, Client


# ── Status derivation ────────────────────────────────────────────────────────
def derive_dispatch_status(item, order):
    """Deriva status operacional do OrderItem com base na Order e dados presentes."""
    if order.status == 'cancelado':
        return 'cancelado'
    if order.status == 'concluido':
        return 'concluido'
    if order.status == 'faturado':
        return 'em_execucao'
    if not item.op_driver_name:
        return 'pendente_escala'
    if item.op_driver_name and not item.op_vehicle_model:
        return 'motorista_atribuido'
    return 'confirmado'


STATUS_LABELS = {
    'pendente_escala':    'Pend. Escala',
    'motorista_atribuido': 'Motorista Atrib.',
    'confirmado':         'Confirmado',
    'em_execucao':        'Em Execução',
    'concluido':          'Concluído',
    'cancelado':          'Cancelado',
}

STATUS_COLORS = {
    'pendente_escala':    'slate',
    'motorista_atribuido': 'blue',
    'confirmado':         'emerald',
    'em_execucao':        'amber',
    'concluido':          'slate',
    'cancelado':          'red',
}


# ── Base query ───────────────────────────────────────────────────────────────
def _base_items_query(company_id: int):
    """OrderItems com op_pickup_datetime, join Order + Client."""
    return (OrderItem.query
            .join(Order, OrderItem.order_id == Order.id)
            .outerjoin(Client, Order.client_id == Client.id)
            .options(
                joinedload(OrderItem.order).joinedload(Order.client),
                joinedload(OrderItem.category),
            )
            .filter(Order.company_id == company_id)
            .filter(OrderItem.op_pickup_datetime.isnot(None))
            .filter(Order.deleted_at.is_(None)))


# ── Calendar queries ─────────────────────────────────────────────────────────
def get_calendar_items(company_id: int, start_date, end_date, filters=None):
    """Itens com pickup dentro do range. Aceita filtros opcionais."""
    q = _base_items_query(company_id).filter(
        func.date(OrderItem.op_pickup_datetime).between(
            start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
            end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date,
        )
    )

    if filters:
        if filters.get('search'):
            term = f"%{filters['search']}%"
            q = q.filter(or_(
                Order.number.ilike(term),
                Client.name.ilike(term),
                OrderItem.op_driver_name.ilike(term),
                OrderItem.op_passenger_name.ilike(term),
            ))
        if filters.get('driver'):
            q = q.filter(OrderItem.op_driver_name.ilike(f"%{filters['driver']}%"))
        if filters.get('vehicle'):
            term = f"%{filters['vehicle']}%"
            q = q.filter(or_(
                OrderItem.op_vehicle_model.ilike(term),
                OrderItem.op_vehicle_plate.ilike(term),
            ))
        if filters.get('client'):
            q = q.filter(Client.name.ilike(f"%{filters['client']}%"))
        if filters.get('origin'):
            q = q.filter(OrderItem.op_pickup_location.ilike(f"%{filters['origin']}%"))
        if filters.get('destination'):
            q = q.filter(OrderItem.op_dropoff_location.ilike(f"%{filters['destination']}%"))
        if filters.get('category'):
            q = q.filter(OrderItem.category_id == int(filters['category']))
        if filters.get('status'):
            # status is derived, so we filter in Python after fetch
            pass

    items = q.order_by(OrderItem.op_pickup_datetime.asc()).all()

    # Apply derived status filter if requested (post-query)
    if filters and filters.get('status'):
        items = [it for it in items
                 if derive_dispatch_status(it, it.order) == filters['status']]

    return items


def get_items_for_date(company_id: int, ref_date):
    """Todos os itens com pickup em uma data específica."""
    return get_calendar_items(company_id, ref_date, ref_date)


# ── KPI summary ──────────────────────────────────────────────────────────────
def get_kpi_summary(company_id: int, ref_date=None):
    """Retorna os 6 KPIs. Se ref_date=None, conta todos (sem filtro de data)."""
    base = _base_items_query(company_id)

    if ref_date:
        base = base.filter(func.date(OrderItem.op_pickup_datetime) == ref_date.isoformat())

    all_items = base.all()

    counts = {k: 0 for k in STATUS_LABELS}
    for item in all_items:
        s = derive_dispatch_status(item, item.order)
        counts[s] = counts.get(s, 0) + 1

    return {
        'total':             len(all_items),
        'agendados_hoje':    counts.get('confirmado', 0) + counts.get('motorista_atribuido', 0) + counts.get('pendente_escala', 0) + counts.get('em_execucao', 0),
        'pendente_escala':   counts.get('pendente_escala', 0),
        'confirmados':       counts.get('confirmado', 0) + counts.get('motorista_atribuido', 0),
        'em_execucao':       counts.get('em_execucao', 0),
        'concluidos':        counts.get('concluido', 0),
        'cancelados':        counts.get('cancelado', 0),
    }


# ── Item detail ──────────────────────────────────────────────────────────────
def get_item_detail(item_id: int):
    """Detalhes completos de um OrderItem para o drawer."""
    item = (OrderItem.query
            .options(
                joinedload(OrderItem.order).joinedload(Order.client),
                joinedload(OrderItem.category),
            )
            .get(item_id))
    if not item:
        return None

    order = item.order
    return {
        'id':                   item.id,
        'order_id':             order.id,
        'order_number':         order.number,
        'order_status':         order.status,
        'dispatch_status':      derive_dispatch_status(item, order),
        'dispatch_status_label': STATUS_LABELS.get(derive_dispatch_status(item, order)),
        'client_name':          order.client.name if order.client else (order.client_name or '–'),
        'pickup_datetime':      item.op_pickup_datetime.isoformat() if item.op_pickup_datetime else None,
        'pickup_location':      item.op_pickup_location or '',
        'dropoff_location':     item.op_dropoff_location or '',
        'driver_name':          item.op_driver_name or '',
        'driver_phone':         item.op_driver_phone or '',
        'vehicle_model':        item.op_vehicle_model or '',
        'vehicle_plate':        item.op_vehicle_plate or '',
        'passenger_name':       item.op_passenger_name or '',
        'passenger_phone':      item.op_passenger_phone or '',
        'flight_number':        item.op_flight_number or '',
        'pax_count':            '',
        'notes':                item.op_notes or '',
        'service_name':         item.description or '–',
        'category_name':        item.category.name if item.category else '–',
    }


# ── Actions ──────────────────────────────────────────────────────────────────
def update_item_driver(item_id: int, driver_name: str, driver_phone: str = ''):
    """Atualiza dados do motorista no OrderItem."""
    item = OrderItem.query.get(item_id)
    if not item:
        return False
    item.op_driver_name = driver_name
    if driver_phone:
        item.op_driver_phone = driver_phone
    db.session.commit()
    return True


def update_item_vehicle(item_id: int, vehicle_model: str, vehicle_plate: str = ''):
    """Atualiza dados do veículo no OrderItem."""
    item = OrderItem.query.get(item_id)
    if not item:
        return False
    item.op_vehicle_model = vehicle_model
    if vehicle_plate:
        item.op_vehicle_plate = vehicle_plate
    db.session.commit()
    return True


def start_item_service(item_id: int):
    """Inicia serviço: se SO='aberto', muda para 'faturado'."""
    item = OrderItem.query.options(joinedload(OrderItem.order)).get(item_id)
    if not item or not item.order:
        return False
    if item.order.status == 'aberto':
        item.order.status = 'faturado'
        db.session.commit()
        return True
    return False


def complete_item_service(item_id: int):
    """Conclui serviço: se SO='faturado', muda para 'concluido'."""
    item = OrderItem.query.options(joinedload(OrderItem.order)).get(item_id)
    if not item or not item.order:
        return False
    if item.order.status == 'faturado':
        item.order.status = 'concluido'
        db.session.commit()
        return True
    return False


def cancel_item_service(item_id: int):
    """Cancela agendamento do item: limpa dados operacionais."""
    item = OrderItem.query.get(item_id)
    if not item:
        return False
    item.op_driver_name = None
    item.op_driver_phone = None
    item.op_vehicle_model = None
    item.op_vehicle_plate = None
    item.op_pickup_datetime = None
    db.session.commit()
    return True
