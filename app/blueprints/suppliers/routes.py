from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import suppliers_bp
from ...models.supplier import Supplier
from ...extensions import db


@suppliers_bp.route("/")
@login_required
def index():
    q     = request.args.get("q", "").strip()
    query = Supplier.query.filter_by(company_id=current_user.company_id, deleted_at=None)
    if q:
        query = query.filter(Supplier.name.ilike(f"%{q}%"))
    suppliers = query.order_by(Supplier.name).all()
    return render_template("suppliers/index.html", suppliers=suppliers, q=q)


@suppliers_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        s = Supplier(
            company_id    = current_user.company_id,
            name          = request.form["name"],
            contact       = request.form.get("contact"),
            email         = request.form.get("email"),
            phone         = request.form.get("phone"),
            document      = request.form.get("document"),
            address       = request.form.get("address"),
            city          = request.form.get("city"),
            state         = request.form.get("state"),
            service_type  = request.form.get("service_type"),
            payment_terms = request.form.get("payment_terms"),
            notes         = request.form.get("notes"),
        )
        db.session.add(s)
        db.session.commit()
        flash("Fornecedor cadastrado.", "success")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", supplier=None)


@suppliers_bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit(sid):
    supplier = Supplier.query.filter_by(id=sid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    if request.method == "POST":
        supplier.name          = request.form["name"]
        supplier.contact       = request.form.get("contact")
        supplier.email         = request.form.get("email")
        supplier.phone         = request.form.get("phone")
        supplier.document      = request.form.get("document")
        supplier.address       = request.form.get("address")
        supplier.city          = request.form.get("city")
        supplier.state         = request.form.get("state")
        supplier.service_type  = request.form.get("service_type")
        supplier.payment_terms = request.form.get("payment_terms")
        supplier.notes         = request.form.get("notes")
        db.session.commit()
        flash("Fornecedor atualizado.", "success")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", supplier=supplier)


@suppliers_bp.route("/<int:sid>/delete", methods=["POST"])
@login_required
def delete(sid):
    supplier = Supplier.query.filter_by(id=sid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    supplier.soft_delete()
    db.session.commit()
    flash("Fornecedor removido.", "info")
    return redirect(url_for("suppliers.index"))
