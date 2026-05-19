"""Service Orders blueprint routes — Ordens de Serviço (OS)."""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import service_orders_bp
from ...models.service_order import ServiceOrder, OS_STATUSES
from ...models.driver        import Driver
from ...models.vehicle       import Vehicle
from ...models.supplier      import Supplier
from ...models.operation_cost import OperationCost, COST_TYPES, COST_TYPE_LABELS
from ...extensions import db
from ... import services as svc_module
from ...services import service_order_service as sos


# ─── List ────────────────────────────────────────────────────────────────────

@service_orders_bp.route("/")
@login_required
def index():
    cid    = current_user.company_id
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    query  = (ServiceOrder.query
              .filter_by(company_id=cid)
              .filter(ServiceOrder.deleted_at.is_(None)))
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(
            ServiceOrder.code.ilike(f"%{q}%") |
            ServiceOrder.passenger_name.ilike(f"%{q}%")
        )
    os_list = query.order_by(ServiceOrder.pickup_datetime.asc().nullsfirst(),
                             ServiceOrder.id.desc()).all()
    return render_template("service_orders/index.html", os_list=os_list,
                           status=status, q=q, OS_STATUSES=OS_STATUSES)


# ─── New (manual) ─────────────────────────────────────────────────────────────

@service_orders_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        from datetime import datetime
        data = request.form.to_dict()
        # parse datetime
        pd = data.pop("pickup_datetime", "")
        if pd:
            try:
                data["pickup_datetime"] = datetime.strptime(pd, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass
        data["client_id"]   = data.get("client_id")   or None
        data["service_id"]  = data.get("service_id")  or None
        data["category_id"] = data.get("category_id") or None
        os_obj = sos.create_manual(current_user.company_id, data, current_user.id)
        db.session.commit()
        flash(f"OS {os_obj.code} criada.", "success")
        return redirect(url_for("service_orders.detail", os_id=os_obj.id))
    from ...models.client  import Client
    from ...models.service import Service
    from ...models.vehicle import VehicleCategory
    clients    = Client.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Client.name).all()
    services   = Service.query.filter_by(is_active=True).order_by(Service.name).all()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    return render_template("service_orders/form.html", clients=clients,
                           services=services, categories=categories)


# ─── Detail ───────────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>")
@login_required
def detail(os_id):
    os_obj    = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    drivers   = Driver.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).order_by(Driver.name).all()
    vehicles  = Vehicle.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).all()
    suppliers = Supplier.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).order_by(Supplier.name).all()
    costs     = OperationCost.query.filter_by(service_order_id=os_id).order_by(OperationCost.created_at.desc()).all()
    events    = os_obj.events.order_by(None).order_by(
        __import__("sqlalchemy").text("service_order_events.created_at ASC")).all()
    return render_template("service_orders/detail.html", os=os_obj,
                           drivers=drivers, vehicles=vehicles, suppliers=suppliers,
                           costs=costs, events=events,
                           COST_TYPES=COST_TYPES, COST_TYPE_LABELS=COST_TYPE_LABELS,
                           OS_STATUSES=OS_STATUSES)


# ─── Assign driver ────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/assign-driver", methods=["POST"])
@login_required
def assign_driver(os_id):
    os_obj     = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    driver_id  = request.form.get("driver_id",  type=int)
    vehicle_id = request.form.get("vehicle_id", type=int)
    notes      = request.form.get("notes", "")
    if not driver_id:
        flash("Selecione um motorista.", "warning")
        return redirect(url_for("service_orders.detail", os_id=os_id))
    sos.assign_driver(os_obj, driver_id, vehicle_id, current_user.id, notes=notes)
    db.session.commit()
    flash("Motorista atribuído à OS.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Assign supplier ──────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/assign-supplier", methods=["POST"])
@login_required
def assign_supplier(os_id):
    os_obj = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    sid    = request.form.get("supplier_id", type=int)
    if not sid:
        flash("Selecione um fornecedor.", "warning")
        return redirect(url_for("service_orders.detail", os_id=os_id))
    sos.assign_supplier(
        os_obj,
        supplier_id          = sid,
        supplier_driver_name = request.form.get("supplier_driver_name", ""),
        supplier_vehicle     = request.form.get("supplier_vehicle", ""),
        supplier_contact     = request.form.get("supplier_contact", ""),
        supplier_price       = float(request.form.get("supplier_price") or 0),
        user_id              = current_user.id,
        notes                = request.form.get("notes", ""),
    )
    db.session.commit()
    flash("Fornecedor atribuído à OS.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Add cost ─────────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/add-cost", methods=["POST"])
@login_required
def add_cost(os_id):
    os_obj      = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    cost_type   = request.form.get("cost_type", "misc")
    try:
        amount  = float(request.form.get("amount", 0))
    except ValueError:
        amount  = 0.0
    description = request.form.get("description", "")
    sos.add_cost(os_obj, cost_type, amount, description=description, user_id=current_user.id)
    db.session.commit()
    flash(f"Custo adicionado: R$ {amount:.2f}.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Update status ────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/update-status", methods=["POST"])
@login_required
def update_status(os_id):
    os_obj     = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    new_status = request.form.get("status", "")
    if new_status not in OS_STATUSES:
        flash("Status inválido.", "warning")
        return redirect(url_for("service_orders.detail", os_id=os_id))
    sos.update_status(os_obj, new_status, current_user.id,
                      description=request.form.get("description", ""))
    db.session.commit()
    flash(f"Status atualizado para '{os_obj.status_label}'.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Add note ─────────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/add-note", methods=["POST"])
@login_required
def add_note(os_id):
    os_obj = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    note   = request.form.get("note", "").strip()
    if note:
        sos.add_event(os_obj, "nota", note, current_user.id)
        db.session.commit()
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Send driver info ──────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/send-driver-info", methods=["POST"])
@login_required
def send_driver_info(os_id):
    os_obj = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    sos.send_driver_info(os_obj, current_user.id)
    db.session.commit()
    flash("Dados de motorista marcados como enviados.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))


# ─── Close ─────────────────────────────────────────────────────────────────────

@service_orders_bp.route("/<int:os_id>/close", methods=["POST"])
@login_required
def close(os_id):
    os_obj = ServiceOrder.query.filter_by(id=os_id, company_id=current_user.company_id).first_or_404()
    notes  = request.form.get("notes", "")
    sos.close(os_obj, current_user.id, notes=notes)
    db.session.commit()
    flash(f"OS {os_obj.code} finalizada.", "success")
    return redirect(url_for("service_orders.detail", os_id=os_id))
