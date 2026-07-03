"""DispatchService — Centro de Operações baseado em Sales Orders.

Consulta OrderItems com dados operacionais (op_pickup_datetime) e os
apresenta como agenda. NÃO cria registros — apenas consulta e atualiza
campos existentes.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Order, OrderItem, Client, ServiceOrder


# ── Status labels ────────────────────────────────────────────────────────────
STATUS_LABELS = {
    'pendente_escala':    'Pend. Escala',
    'motorista_atribuido': 'Motorista Atrib.',
    'confirmado':         'Confirmado',
    'em_execucao':        'Em Execução',
    'concluido':          'Concluído',
    'cancelado':          'Cancelado',
}

STATUS_COLORS = {
    'pendente_escala':     'slate',
    'motorista_atribuido': 'blue',
    'confirmado':          'emerald',
    'em_execucao':         'amber',
    'concluido':           'slate',
    'cancelado':           'red',
}


# ── Status derivation ────────────────────────────────────────────────────────
def derive_dispatch_status(item, order):
    """Status operacional derivado de Order.status + dados do item."""
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


# ── Base query ───────────────────────────────────────────────────────────────
def _base_items_query(company_id):
    """OrderItems com op_pickup_datetime + Order + Client."""
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


# ── Calendar items ───────────────────────────────────────────────────────────
def get_calendar_items(company_id, start_date, end_date, filters=None):
    """Itens com pickup no intervalo de datas."""
    day_start = datetime.combine(start_date, datetime.min.time())
    day_end = datetime.combine(end_date, datetime.max.time())

    q = (_base_items_query(company_id)
         .filter(OrderItem.op_pickup_datetime.between(day_start, day_end)))

    if filters:
        if filters.get('search'):
            term = '%' + filters['search'] + '%'
            q = q.filter(or_(
                Order.number.ilike(term),
                Client.name.ilike(term),
                OrderItem.op_driver_name.ilike(term),
                OrderItem.op_passenger_name.ilike(term),
            ))
        if filters.get('driver'):
            q = q.filter(OrderItem.op_driver_name.ilike('%' + filters['driver'] + '%'))
        if filters.get('client'):
            q = q.filter(Client.name.ilike('%' + filters['client'] + '%'))
        if filters.get('status'):
            pass  # derived — filter in Python below

    items = q.order_by(OrderItem.op_pickup_datetime.asc()).all()

    if filters and filters.get('status'):
        items = [it for it in items
                 if derive_dispatch_status(it, it.order) == filters['status']]

    return items


# ── KPI summary ──────────────────────────────────────────────────────────────
def get_kpi_summary(company_id, ref_date=None):
    """Retorna 6 KPIs. Se ref_date, filtra por data."""
    base = _base_items_query(company_id)

    if ref_date:
        day_start = datetime.combine(ref_date, datetime.min.time())
        day_end = datetime.combine(ref_date, datetime.max.time())
        base = base.filter(
            OrderItem.op_pickup_datetime.between(day_start, day_end))

    all_items = base.all()
    counts = {}
    for item in all_items:
        s = derive_dispatch_status(item, item.order)
        counts[s] = counts.get(s, 0) + 1

    return {
        'total': len(all_items),
        'agendados_hoje': (counts.get('confirmado', 0)
                          + counts.get('motorista_atribuido', 0)
                          + counts.get('pendente_escala', 0)
                          + counts.get('em_execucao', 0)),
        'pendente_escala': counts.get('pendente_escala', 0),
        'confirmados': (counts.get('confirmado', 0)
                       + counts.get('motorista_atribuido', 0)),
        'em_execucao': counts.get('em_execucao', 0),
        'concluidos': counts.get('concluido', 0),
        'cancelados': counts.get('cancelado', 0),
    }


# ── Item detail ──────────────────────────────────────────────────────────────
def get_item_detail(item_id):
    """Detalhes de um OrderItem para o drawer."""
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
        'id': item.id,
        'order_id': order.id,
        'order_number': order.number,
        'order_status': order.status,
        'dispatch_status': derive_dispatch_status(item, order),
        'dispatch_status_label': STATUS_LABELS.get(
            derive_dispatch_status(item, order), ''),
        'client_name': (order.client.name if order.client
                       else (order.client_name or '–')),
        'pickup_datetime': (item.op_pickup_datetime.isoformat()
                           if item.op_pickup_datetime else None),
        'pickup_location': item.op_pickup_location or '',
        'dropoff_location': item.op_dropoff_location or '',
        'driver_name': item.op_driver_name or '',
        'driver_phone': item.op_driver_phone or '',
        'vehicle_model': item.op_vehicle_model or '',
        'vehicle_plate': item.op_vehicle_plate or '',
        'passenger_name': item.op_passenger_name or '',
        'passenger_phone': item.op_passenger_phone or '',
        'flight_number': item.op_flight_number or '',
        'notes': item.op_notes or '',
        'description': item.description or '',
        'category_name': item.category.name if item.category else '–',
    }


# ── Actions ──────────────────────────────────────────────────────────────────
def update_item_driver(item_id, driver_name, driver_phone=''):
    """Atualiza motorista no OrderItem."""
    item = OrderItem.query.get(item_id)
    if not item:
        return False
    item.op_driver_name = driver_name
    if driver_phone:
        item.op_driver_phone = driver_phone
    db.session.commit()
    return True


def update_item_vehicle(item_id, vehicle_model, vehicle_plate=''):
    """Atualiza veículo no OrderItem."""
    item = OrderItem.query.get(item_id)
    if not item:
        return False
    item.op_vehicle_model = vehicle_model
    if vehicle_plate:
        item.op_vehicle_plate = vehicle_plate
    db.session.commit()
    return True


def start_item_service(item_id):
    """Inicia serviço: SO aberto → faturado."""
    item = OrderItem.query.options(joinedload(OrderItem.order)).get(item_id)
    if not item or not item.order:
        return False
    if item.order.status == 'aberto':
        item.order.status = 'faturado'
        db.session.commit()
        return True
    return False


def complete_item_service(item_id):
    """Conclui serviço: SO faturado → concluido."""
    item = OrderItem.query.options(joinedload(OrderItem.order)).get(item_id)
    if not item or not item.order:
        return False
    if item.order.status == 'faturado':
        item.order.status = 'concluido'
        db.session.commit()
        return True
    return False


def cancel_item_from_dispatch(item_id):
    """Remove dados operacionais do item (volta a Pend. Escala)."""
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


# ── Dashboard compatibility ──────────────────────────────────────────────────
def get_summary(company_id, ref_date=None):
    """Resumo para o Dashboard (mantém compatibilidade com ServiceOrder)."""
    from sqlalchemy.orm import lazyload as _lazyload
    from ..utils import now_br as _now_br

    if ref_date is None:
        ref_date = _now_br().date()

    day_start = datetime.combine(ref_date, datetime.min.time())
    day_end = datetime.combine(ref_date, datetime.max.time())

    base = (ServiceOrder.query
            .options(_lazyload('*'),
                     joinedload(ServiceOrder.assigned_driver).lazyload('*'))
            .filter_by(company_id=company_id)
            .filter(ServiceOrder.deleted_at.is_(None)))

    today_os = (base
                .filter(ServiceOrder.pickup_datetime.between(day_start, day_end))
                .filter(ServiceOrder.status.notin_(["cancelado", "finalizado"]))
                .order_by(ServiceOrder.pickup_datetime.asc())
                .all())

    pending = (base
               .filter(ServiceOrder.status.in_(["criado", "agendado"]))
               .filter(ServiceOrder.assigned_driver_id.is_(None))
               .filter(ServiceOrder.supplier_id.is_(None))
               .order_by(ServiceOrder.pickup_datetime.asc())
               .all())

    in_progress = (base
                   .filter_by(status="em_execucao")
                   .order_by(ServiceOrder.pickup_datetime.asc())
                   .all())

    now_dt = _now_br()
    overdue = (base
               .filter(ServiceOrder.pickup_datetime < now_dt)
               .filter(ServiceOrder.status.notin_(["finalizado", "cancelado"]))
               .order_by(ServiceOrder.pickup_datetime.asc())
               .all())

    return {
        "date": ref_date,
        "today_count": len(today_os),
        "today_list": today_os,
        "pending": pending,
        "in_progress": in_progress,
        "overdue": overdue,
        "pending_count": len(pending),
        "overdue_count": len(overdue),
    }
