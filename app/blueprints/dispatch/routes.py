"""Dispatch blueprint — Centro de Operações (Agenda Operacional).

Baseado automaticamente nas Sales Orders que possuem OrderItems com
dados operacionais preenchidos (op_pickup_datetime).
"""
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import dispatch_bp
from ...services import dispatch_service
from ...utils import now_br
from ...utils.decorators import require_permission
from collections import defaultdict
from datetime import date, datetime, timedelta


# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_date(date_str, fallback=None):
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass
    return fallback or now_br().date()


def _week_range(ref_date):
    """Retorna (start, end) para a semana contendo ref_date (seg→dom)."""
    weekday = ref_date.weekday()  # 0=seg, 6=dom
    start = ref_date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end


def _month_range(ref_date):
    """Retorna (start, end) para o mês contendo ref_date."""
    start = ref_date.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end


def _collect_filters(args):
    """Extrai filtros dos query params."""
    filters = {}
    for key in ['search', 'driver', 'vehicle', 'client', 'origin', 'destination', 'status']:
        val = args.get(key, '').strip()
        if val:
            filters[key] = val
    if args.get('category', '').strip():
        filters['category'] = args.get('category', '').strip()
    return filters or None


# ── Serializer ───────────────────────────────────────────────────────────────
def _item_to_dict(item):
    """Converte OrderItem para dict JSON para o front-end."""
    order = item.order
    status = dispatch_service.derive_dispatch_status(item, order)
    return {
        'id':               item.id,
        'order_id':         order.id,
        'order_number':     order.number,
        'order_status':     order.status,
        'dispatch_status':  status,
        'status_label':     dispatch_service.STATUS_LABELS.get(status, status),
        'status_color':     dispatch_service.STATUS_COLORS.get(status, 'slate'),
        'client_name':      order.client.name if order.client else (order.client_name or '–'),
        'time':             item.op_pickup_datetime.strftime('%H:%M') if item.op_pickup_datetime else '',
        'date_iso':         item.op_pickup_datetime.strftime('%Y-%m-%d') if item.op_pickup_datetime else '',
        'pickup_location':  item.op_pickup_location or '',
        'dropoff_location': item.op_dropoff_location or '',
        'driver_name':      item.op_driver_name or '',
        'vehicle_model':    item.op_vehicle_model or '',
        'vehicle_plate':    item.op_vehicle_plate or '',
        'passenger_name':   item.op_passenger_name or '',
        'pax_count':        '',
        'service_name':     item.description or '–',
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@dispatch_bp.route("/")
@login_required
@require_permission("dispatch.view")
def index():
    """Calendário operacional (default: view=week)."""
    cid = current_user.company_id
    view = request.args.get("view", "week")  # day | week | month
    ref_date = _parse_date(request.args.get("date"))
    filters = _collect_filters(request.args)

    if view == "day":
        start_date = end_date = ref_date
        prev_date = (ref_date - timedelta(days=1)).isoformat()
        next_date = (ref_date + timedelta(days=1)).isoformat()
        date_label = ref_date.strftime('%d/%m/%Y')
    elif view == "month":
        start_date, end_date = _month_range(ref_date)
        prev_date = ((start_date - timedelta(days=1)).replace(day=1)).isoformat()
        next_date = ((end_date + timedelta(days=1)).replace(day=1)).isoformat()
        date_label = ref_date.strftime('%B/%Y').capitalize()
    else:  # week (default)
        view = "week"
        start_date, end_date = _week_range(ref_date)
        prev_date = (start_date - timedelta(days=7)).isoformat()
        next_date = (end_date + timedelta(days=1)).isoformat()
        date_label = f"{start_date.strftime('%d/%m')} – {end_date.strftime('%d/%m')}"

    items = dispatch_service.get_calendar_items(cid, start_date, end_date, filters)
    kpi = dispatch_service.get_kpi_summary(cid, ref_date)

    # Serialize items to dicts with pre-computed dispatch status
    items_data = [_item_to_dict(it) for it in items]

    # Group items by date for calendar views
    items_by_date = defaultdict(list)
    for d in items_data:
        items_by_date[d['date_iso']].append(d)

    # Generate week_days list for weekly view
    week_days = []
    if view == 'week':
        d = start_date
        for _ in range(7):
            week_days.append(d.isoformat())
            d += timedelta(days=1)

    # Generate month_days for monthly view
    month_days = []
    month_first_weekday = 0
    if view == 'month':
        month_first_weekday = start_date.weekday()  # 0=Seg
        d = start_date
        while d <= end_date:
            month_days.append(d.isoformat())
            d += timedelta(days=1)

    return render_template(
        "dispatch/index.html",
        items_data=items_data,
        items_by_date=dict(items_by_date),
        kpi=kpi,
        view=view,
        ref_date=ref_date.isoformat(),
        today=now_br().date().isoformat(),
        prev_date=prev_date,
        next_date=next_date,
        date_label=date_label,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        week_days=week_days,
        month_days=month_days,
        month_first_weekday=month_first_weekday,
        status_labels=dispatch_service.STATUS_LABELS,
        status_colors=dispatch_service.STATUS_COLORS,
    )


# ── AJAX: Item detail (drawer) ───────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>")
@login_required
@require_permission("dispatch.view")
def item_detail(item_id):
    """Retorna JSON com detalhes do OrderItem para o drawer."""
    detail = dispatch_service.get_item_detail(item_id)
    if not detail:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True, 'item': detail})


# ── AJAX: Update driver ─────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/driver", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def update_driver(item_id):
    """Atualiza op_driver_name e op_driver_phone no OrderItem."""
    data = request.get_json() or {}
    driver_name = data.get('driver_name', '').strip()
    driver_phone = data.get('driver_phone', '').strip()
    if not driver_name:
        return jsonify({'ok': False, 'error': 'Nome do motorista é obrigatório'}), 400

    ok = dispatch_service.update_item_driver(item_id, driver_name, driver_phone)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True, 'message': 'Motorista atualizado'})


# ── AJAX: Update vehicle ────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/vehicle", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def update_vehicle(item_id):
    """Atualiza op_vehicle_model e op_vehicle_plate no OrderItem."""
    data = request.get_json() or {}
    vehicle_model = data.get('vehicle_model', '').strip()
    vehicle_plate = data.get('vehicle_plate', '').strip()
    if not vehicle_model:
        return jsonify({'ok': False, 'error': 'Modelo do veículo é obrigatório'}), 400

    ok = dispatch_service.update_item_vehicle(item_id, vehicle_model, vehicle_plate)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True, 'message': 'Veículo atualizado'})


# ── AJAX: Start service ─────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/start", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def start_service(item_id):
    """Inicia serviço: SO aberto → faturado."""
    ok = dispatch_service.start_item_service(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Não foi possível iniciar o serviço'}), 400
    return jsonify({'ok': True, 'message': 'Serviço iniciado'})


# ── AJAX: Complete service ──────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/complete", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def complete_service(item_id):
    """Conclui serviço: SO faturado → concluido."""
    ok = dispatch_service.complete_item_service(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Não foi possível concluir o serviço'}), 400
    return jsonify({'ok': True, 'message': 'Serviço concluído'})


# ── AJAX: Cancel service ────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/cancel", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def cancel_service(item_id):
    """Cancela agendamento: limpa dados operacionais do item."""
    ok = dispatch_service.cancel_item_service(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True, 'message': 'Agendamento cancelado'})
