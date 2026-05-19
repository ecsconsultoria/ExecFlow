from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import clients_bp
from ...models.client import Client
from ...extensions import db


@clients_bp.route("/")
@login_required
def index():
    q     = request.args.get("q", "").strip()
    query = Client.query.filter_by(company_id=current_user.company_id, deleted_at=None)
    if q:
        query = query.filter(Client.name.ilike(f"%{q}%"))
    clients = query.order_by(Client.name).all()
    return render_template("clients/index.html", clients=clients, q=q)


@clients_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        client = Client(
            company_id     = current_user.company_id,
            name           = request.form["name"],
            contact        = request.form.get("contact"),
            email          = request.form.get("email"),
            phone          = request.form.get("phone"),
            whatsapp       = request.form.get("whatsapp"),
            document       = request.form.get("document"),
            address        = request.form.get("address"),
            city           = request.form.get("city"),
            state          = request.form.get("state"),
            country        = request.form.get("country", "Brasil"),
            language       = request.form.get("language", "pt"),
            billing_type   = request.form.get("billing_type", "recibo"),
            payment_method = request.form.get("payment_method"),
            notes          = request.form.get("notes"),
        )
        db.session.add(client)
        db.session.commit()
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("clients.index"))
    return render_template("clients/form.html", client=None)


@clients_bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def edit(cid):
    client = Client.query.filter_by(id=cid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    if request.method == "POST":
        client.name           = request.form["name"]
        client.contact        = request.form.get("contact")
        client.email          = request.form.get("email")
        client.phone          = request.form.get("phone")
        client.whatsapp       = request.form.get("whatsapp")
        client.document       = request.form.get("document")
        client.address        = request.form.get("address")
        client.city           = request.form.get("city")
        client.state          = request.form.get("state")
        client.country        = request.form.get("country", "Brasil")
        client.language       = request.form.get("language", "pt")
        client.billing_type   = request.form.get("billing_type", "recibo")
        client.payment_method = request.form.get("payment_method")
        client.notes          = request.form.get("notes")
        db.session.commit()
        flash("Cliente atualizado.", "success")
        return redirect(url_for("clients.index"))
    return render_template("clients/form.html", client=client)


@clients_bp.route("/<int:cid>/delete", methods=["POST"])
@login_required
def delete(cid):
    client = Client.query.filter_by(id=cid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    client.soft_delete()
    db.session.commit()
    flash("Cliente removido.", "info")
    return redirect(url_for("clients.index"))


@clients_bp.route("/search")
@login_required
def search():
    q = request.args.get("q", "")
    clients = (Client.query
               .filter_by(company_id=current_user.company_id, deleted_at=None)
               .filter(Client.name.ilike(f"%{q}%") | Client.email.ilike(f"%{q}%"))
               .order_by(Client.name).limit(15).all())
    return jsonify([{"id": c.id, "name": c.name, "contact": c.contact or "",
                     "email": c.email or "", "phone": c.phone or "",
                     "language": c.language or "pt", "billing_type": c.billing_type or "recibo",
                     "payment_method": c.payment_method or ""} for c in clients])
