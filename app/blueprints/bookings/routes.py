from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import bookings_bp
from ...models.booking  import Booking
from ...models.driver   import Driver
from ...models.vehicle  import Vehicle
from ...models.supplier import Supplier
from ...extensions import db
from ...utils import now_br


@bookings_bp.route("/")
@login_required
def index():
    status = request.args.get("status", "")
    query  = Booking.query.filter_by(company_id=current_user.company_id, deleted_at=None)
    if status:
        query = query.filter_by(status=status)
    bookings = query.order_by(Booking.service_date.asc()).all()
    return render_template("bookings/index.html", bookings=bookings, status=status)


@bookings_bp.route("/<int:bid>")
@login_required
def detail(bid):
    booking   = Booking.query.filter_by(id=bid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    drivers   = Driver.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Driver.name).all()
    vehicles  = Vehicle.query.filter_by(company_id=current_user.company_id, deleted_at=None).all()
    suppliers = Supplier.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Supplier.name).all()
    return render_template("bookings/detail.html", booking=booking,
                           drivers=drivers, vehicles=vehicles, suppliers=suppliers)


@bookings_bp.route("/<int:bid>/update-info", methods=["POST"])
@login_required
def update_info(bid):
    booking = Booking.query.filter_by(id=bid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    sd = request.form.get("service_date", "").strip()
    if sd:
        try:
            booking.service_date = datetime.strptime(sd, "%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    booking.pickup_address  = request.form.get("pickup_address",  "").strip() or None
    booking.dropoff_address = request.form.get("dropoff_address", "").strip() or None
    booking.flight_number   = request.form.get("flight_number",   "").strip() or None
    booking.pax_count       = int(request.form.get("pax_count", 1) or 1)
    booking.notes           = request.form.get("notes",           "").strip() or None
    db.session.commit()
    flash("Dados atualizados.", "success")
    return redirect(url_for("bookings.detail", bid=bid))


@bookings_bp.route("/<int:bid>/assign-driver", methods=["POST"])
@login_required
def assign_driver(bid):
    booking = Booking.query.filter_by(id=bid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    booking.driver_id    = request.form.get("driver_id")   or None
    booking.vehicle_id   = request.form.get("vehicle_id")  or None
    booking.supplier_id  = request.form.get("supplier_id") or None
    booking.driver_notes = request.form.get("driver_notes")
    db.session.commit()
    flash("Motorista/fornecedor atribuído.", "success")
    return redirect(url_for("bookings.detail", bid=bid))


@bookings_bp.route("/<int:bid>/complete", methods=["POST"])
@login_required
def complete(bid):
    booking = Booking.query.filter_by(id=bid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    booking.status       = "concluido"
    booking.completed_at = now_br()
    db.session.commit()
    flash("Agendamento concluído.", "success")
    return redirect(url_for("bookings.detail", bid=bid))


@bookings_bp.route("/<int:bid>/cancel", methods=["POST"])
@login_required
def cancel(bid):
    booking = Booking.query.filter_by(id=bid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    booking.status = "cancelado"
    db.session.commit()
    flash("Agendamento cancelado.", "info")
    return redirect(url_for("bookings.index"))
