from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import drivers_bp
from ...models.driver import Driver
from ...models.supplier import Supplier
from ...extensions import db
from ...utils.decorators import require_permission
from ...utils.audit import log_activity


@drivers_bp.route("/")
@login_required
@require_permission("drivers.view")
def index():
    q     = request.args.get("q", "").strip()
    query = Driver.query.filter_by(company_id=current_user.company_id, deleted_at=None)
    if q:
        query = query.filter(Driver.name.ilike(f"%{q}%"))
    drivers = query.order_by(Driver.name).all()
    return render_template("drivers/index.html", drivers=drivers, q=q)


@drivers_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("drivers.edit")
def new():
    suppliers = Supplier.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).order_by(Supplier.name).all()
    if request.method == "POST":
        d = Driver(
            company_id     = current_user.company_id,
            supplier_id    = request.form.get("supplier_id") or None,
            name           = request.form["name"],
            phone          = request.form.get("phone"),
            email          = request.form.get("email"),
            license_number = request.form.get("license_number"),
            language       = request.form.get("language", "monolingual"),
            state          = request.form.get("state"),
            notes          = request.form.get("notes"),
        )
        db.session.add(d)
        db.session.commit()
        flash("Motorista cadastrado.", "success")
        return redirect(url_for("drivers.index"))
    return render_template("drivers/form.html", driver=None, suppliers=suppliers)


@drivers_bp.route("/<int:did>/edit", methods=["GET", "POST"])
@login_required
@require_permission("drivers.edit")
def edit(did):
    driver    = Driver.query.filter_by(id=did, company_id=current_user.company_id, deleted_at=None).first_or_404()
    suppliers = Supplier.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).order_by(Supplier.name).all()
    if request.method == "POST":
        driver.supplier_id    = request.form.get("supplier_id") or None
        driver.name           = request.form["name"]
        driver.phone          = request.form.get("phone")
        driver.email          = request.form.get("email")
        driver.license_number = request.form.get("license_number")
        driver.language       = request.form.get("language", "monolingual")
        driver.state          = request.form.get("state")
        driver.notes          = request.form.get("notes")
        db.session.commit()
        flash("Motorista atualizado.", "success")
        return redirect(url_for("drivers.index"))
    return render_template("drivers/form.html", driver=driver, suppliers=suppliers)


@drivers_bp.route("/<int:did>/delete", methods=["POST"])
@login_required
@require_permission("drivers.delete")
def delete(did):
    driver = Driver.query.filter_by(id=did, company_id=current_user.company_id, deleted_at=None).first_or_404()
    driver.soft_delete()
    log_activity("driver", driver.id, current_user.company_id, f"Motorista {driver.name!r} excluído", current_user.id)
    db.session.commit()
    flash("Motorista removido.", "info")
    return redirect(url_for("drivers.index"))
