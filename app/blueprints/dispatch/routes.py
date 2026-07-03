"""Dispatch blueprint — Centro de Operações (Agenda Operacional).

Baseado em OrderItems com op_pickup_datetime preenchido.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from . import dispatch_bp
from ...services import dispatch_service
from ...utils import now_br
from ...utils.decorators import require_permission


# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_date(date_str, fallback=None):
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass
    return fallback or now_br().date()


def _week_range(ref_date):
    """Retorna (start, end) da semana (seg a dom)."""
    weekday = ref_date.weekday()
    start = ref_date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end


def _month_range(ref_date):
    """Retorna (start, end) do mês."""
    start = ref_date.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end


def _collect_filters(args):
    """Extrai filtros dos query params."""
    filters = {}
    for key in ['search', 'driver', 'client', 'status']:
        val = args.get(key, '').strip()
        if val:
            filters[key] = val
    return filters or None


def _item_to_dict(item):
    """Serializa OrderItem para dict (apenas campos que existem no model)."""
    order = item.order
    status = dispatch_service.derive_dispatch_status(item, order)
    return {
        'id':              item.id,
        'order_id':        order.id,
        'order_number':    order.number,
        'order_status':    order.status,
        'dispatch_status': status,
        'status_label':    dispatch_service.STATUS_LABELS.get(status, status),
        'status_color':    dispatch_service.STATUS_COLORS.get(status, 'slate'),
        'client_name':     (order.client.name if order.client
                            else (order.client_name or '–')),
        'time':            (item.op_pickup_datetime.strftime('%H:%M')
                            if item.op_pickup_datetime else ''),
        'date_iso':        (item.op_pickup_datetime.strftime('%Y-%m-%d')
                            if item.op_pickup_datetime else ''),
        'pickup_location':  item.op_pickup_location or '',
        'dropoff_location': item.op_dropoff_location or '',
        'driver_name':      item.op_driver_name or '',
        'vehicle_model':    item.op_vehicle_model or '',
        'vehicle_plate':    item.op_vehicle_plate or '',
        'passenger_name':   item.op_passenger_name or '',
        'description':      item.description or '',
    }


# ── Routes ───────────────────────────────────────────────────────────────────
@dispatch_bp.route("/")
@login_required
@require_permission("dispatch.view")
def index():
    """Calendário operacional (view padrão: week)."""
    cid = current_user.company_id
    view = request.args.get("view", "week")
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
    else:
        view = "week"
        start_date, end_date = _week_range(ref_date)
        prev_date = (start_date - timedelta(days=7)).isoformat()
        next_date = (end_date + timedelta(days=1)).isoformat()
        date_label = (f"{start_date.strftime('%d/%m')} – "
                      f"{end_date.strftime('%d/%m')}")

    items = dispatch_service.get_calendar_items(cid, start_date, end_date, filters)
    kpi = dispatch_service.get_kpi_summary(cid, ref_date)
    pending_scheduling = dispatch_service.count_pending_scheduling(cid)

    items_data = [_item_to_dict(it) for it in items]

    items_by_date = defaultdict(list)
    for d in items_data:
        if d['date_iso']:
            items_by_date[d['date_iso']].append(d)

    # week_days for weekly view
    week_days = []
    if view == 'week':
        d = start_date
        for _ in range(7):
            week_days.append(d.isoformat())
            d += timedelta(days=1)

    # month_days for monthly view
    month_days = []
    month_first_weekday = 0
    if view == 'month':
        month_first_weekday = start_date.weekday()
        d = start_date
        while d <= end_date:
            month_days.append(d.isoformat())
            d += timedelta(days=1)

    return render_template(
        "dispatch/index.html",
        items_data=items_data,
        items_by_date=dict(items_by_date),
        kpi=kpi,
        pending_scheduling=pending_scheduling,
        view=view,
        ref_date=ref_date.isoformat(),
        today=now_br().date().isoformat(),
        prev_date=prev_date,
        next_date=next_date,
        date_label=date_label,
        week_days=week_days,
        month_days=month_days,
        month_first_weekday=month_first_weekday,
        status_labels=dispatch_service.STATUS_LABELS,
        status_colors=dispatch_service.STATUS_COLORS,
    )


# ── AJAX: Item detail ───────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>")
@login_required
@require_permission("dispatch.view")
def item_detail(item_id):
    detail = dispatch_service.get_item_detail(item_id)
    if not detail:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True, 'item': detail})


# ── AJAX: Update driver ─────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/driver", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def update_driver(item_id):
    data = request.get_json() or {}
    driver_name = data.get('driver_name', '').strip()
    driver_phone = data.get('driver_phone', '').strip()
    if not driver_name:
        return jsonify({'ok': False, 'error': 'Nome do motorista obrigatório'}), 400
    ok = dispatch_service.update_item_driver(item_id, driver_name, driver_phone)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True})


# ── AJAX: Update vehicle ────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/vehicle", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def update_vehicle(item_id):
    data = request.get_json() or {}
    vehicle_model = data.get('vehicle_model', '').strip()
    vehicle_plate = data.get('vehicle_plate', '').strip()
    if not vehicle_model:
        return jsonify({'ok': False, 'error': 'Modelo do veículo obrigatório'}), 400
    ok = dispatch_service.update_item_vehicle(item_id, vehicle_model, vehicle_plate)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True})


# ── AJAX: Start service ─────────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/start", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def start_service(item_id):
    ok = dispatch_service.start_item_service(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Não foi possível iniciar'}), 400
    return jsonify({'ok': True})


# ── AJAX: Complete service ──────────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/complete", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def complete_service(item_id):
    ok = dispatch_service.complete_item_service(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Não foi possível concluir'}), 400
    return jsonify({'ok': True})


# ── AJAX: Cancel from dispatch ──────────────────────────────────────────────
@dispatch_bp.route("/item/<int:item_id>/cancel", methods=["POST"])
@login_required
@require_permission("dispatch.view")
def cancel_service(item_id):
    ok = dispatch_service.cancel_item_from_dispatch(item_id)
    if not ok:
        return jsonify({'ok': False, 'error': 'Item não encontrado'}), 404
    return jsonify({'ok': True})
