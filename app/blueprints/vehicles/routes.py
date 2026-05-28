from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import vehicles_bp
from ...models.vehicle import Vehicle, VehicleCategory
from ...extensions import db
from ...utils.audit import log_activity
from ...utils.decorators import require_permission


@vehicles_bp.route("/")
@login_required
@require_permission("vehicles.view")
def index():
    vehicles = Vehicle.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Vehicle.make).all()
    return render_template("vehicles/index.html", vehicles=vehicles)


@vehicles_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("vehicles.edit")
def new():
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    if request.method == "POST":
        v = Vehicle(
            company_id  = current_user.company_id,
            category_id = request.form["category_id"],
            make        = request.form.get("make"),
            model       = request.form.get("model"),
            year        = request.form.get("year") or None,
            plate       = request.form.get("plate"),
            color       = request.form.get("color"),
            capacity    = request.form.get("capacity") or None,
            notes       = request.form.get("notes"),
        )
        db.session.add(v)
        db.session.commit()
        flash("Veículo cadastrado.", "success")
        return redirect(url_for("vehicles.index"))
    return render_template("vehicles/form.html", vehicle=None, categories=categories)


@vehicles_bp.route("/<int:vid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("vehicles.edit")
def edit(vid):
    vehicle    = Vehicle.query.filter_by(id=vid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    if request.method == "POST":
        vehicle.category_id = request.form["category_id"]
        vehicle.make        = request.form.get("make")
        vehicle.model       = request.form.get("model")
        vehicle.year        = request.form.get("year") or None
        vehicle.plate       = request.form.get("plate")
        vehicle.color       = request.form.get("color")
        vehicle.capacity    = request.form.get("capacity") or None
        vehicle.notes       = request.form.get("notes")
        db.session.commit()
        flash("Veículo atualizado.", "success")
        return redirect(url_for("vehicles.index"))
    return render_template("vehicles/form.html", vehicle=vehicle, categories=categories)


@vehicles_bp.route("/<int:vid>/delete", methods=["POST"])
@login_required
@require_permission("vehicles.delete")
def delete(vid):
    vehicle = Vehicle.query.filter_by(id=vid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    vehicle.soft_delete()
    log_activity("vehicle", vehicle.id, current_user.company_id, f"Veículo {vehicle.plate!r} excluído", current_user.id)
    db.session.commit()
    flash("Veículo removido.", "info")
    return redirect(url_for("vehicles.index"))
