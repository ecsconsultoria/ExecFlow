import json
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, abort, send_file
from flask_login import login_required, current_user
from . import quotes_bp
from ...models.quote   import Quote, QuoteItem, QuoteInclusion, BILLING_TYPES, QUOTE_STATUSES, DEFAULT_INCLUSIONS
from ...models.client  import Client
from ...models.service import Service, ServicePricing, State
from ...models.vehicle import VehicleCategory
from ...models.driver  import Driver
from ...models.company import Company
from ...extensions import db
from ...services.quote_service   import QuoteService
from ...services.booking_service import BookingService
from ...utils import now_br, make_client_token
from ...models.service_order import ServiceOrder
from ...services             import service_order_service as sos


def _get_rates():
    company  = Company.query.get(current_user.company_id)
    s        = (company.settings or {}) if company else {}
    nf   = float(s.get("nf_rate",   current_app.config.get("NF_RATE",   0.10)))
    card = float(s.get("card_rate", current_app.config.get("CARD_RATE", 0.065)))
    return nf, card


def _catalog_json():
    """Return JSON-serialisable structure: list of categories, each with services+prices."""
    nf_rate, card_rate = _get_rates()
    cats = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    result = []
    for cat in cats:
        pricings = (ServicePricing.query
                    .filter_by(category_id=cat.id, is_active=True)
                    .join(Service, ServicePricing.service_id == Service.id)
                    .filter(Service.is_active == True)
                    .order_by(Service.name, ServicePricing.driver_type)
                    .all())
        if not pricings:
            continue
        services = []
        for p in pricings:
            services.append({
                "id":               p.id,           # pricing_id — unique cart key
                "service_id":       p.service_id,
                "name":             p.service.name,
                "driver_type":      p.driver_type or "",
                "description":      p.service.description or "",
                "km_included":      p.service.km_included or 0,
                "duration_hours":   p.service.duration_hours or 0,
                "km_extra_rate":    p.category.km_extra_rate or 0,
                "price_base":       p.price_base or 0,
                "price_nf":         p.price_nf if p.price_nf else round((p.price_base or 0) * (1 + nf_rate), 2),
                "price_cartao":     p.price_cartao if p.price_cartao else round((p.price_base or 0) * (1 + card_rate), 2),
                "price_nf_cartao":  p.price_nf_cartao if p.price_nf_cartao else round((p.price_base or 0) * (1 + nf_rate + card_rate), 2),
                "state_code":       (p.service.state.code if p.service.state else ""),
            })
        result.append({
            "id":          cat.id,
            "name":        cat.name,
            "slug":        cat.slug or "",
            "description": cat.description or "",  # vehicle model, e.g. "Toyota Corolla or Similar"
            "services":    services,
        })
    return result


@quotes_bp.route("/")
@login_required
def index():
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    query  = Quote.query.filter_by(company_id=current_user.company_id, deleted_at=None)
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(Quote.client_name.ilike(f"%{q}%") | Quote.number.ilike(f"%{q}%"))
    quotes = query.order_by(Quote.created_at.desc()).all()
    return render_template("quotes/index.html", quotes=quotes, status=status, q=q,
                           QUOTE_STATUSES=QUOTE_STATUSES)


@quotes_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
        else:
            data = {
                "client_id":   request.form.get("client_id"),
                "obs":         request.form.get("notes", ""),
                "billing_type": request.form.get("billing_type", "recibo"),
                "language":    request.form.get("language", "pt"),
                "items":       [],
                "inclusions":  [],
            }
        quote = QuoteService.create_quote(current_user.company_id, data, current_user.id)
        if request.is_json:
            return jsonify({"id": quote.id, "number": quote.number,
                            "redirect": url_for("quotes.detail", qid=quote.id)})
        return redirect(url_for("quotes.detail", qid=quote.id))

    clients    = Client.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Client.name).all()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.name).all()
    states     = State.query.order_by(State.code).all()
    catalog    = _catalog_json()
    nf_rate, card_rate = _get_rates()
    return render_template(
        "quotes/new.html",
        clients=clients,
        categories=categories,
        states=states,
        catalog_json=json.dumps(catalog),
        default_inclusions=DEFAULT_INCLUSIONS,
        billing_types=BILLING_TYPES,
        nf_rate=nf_rate,
        card_rate=card_rate,
    )


@quotes_bp.route("/<int:qid>")
@login_required
def detail(qid):
    from ...models.order import Order
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote_order   = Order.query.filter_by(quote_id=quote.id, deleted_at=None).first()
    service_order = ServiceOrder.query.filter_by(quote_id=quote.id).filter(ServiceOrder.deleted_at.is_(None)).first()
    return render_template("quotes/detail.html", quote=quote, billing_types=BILLING_TYPES,
                           service_order=service_order, quote_order=quote_order)


@quotes_bp.route("/<int:qid>/edit", methods=["GET", "POST"])
@login_required
def edit(qid):
    from ...models.order import Order
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    # Lock: cannot edit a quote that already has an open order
    linked_order = Order.query.filter_by(quote_id=quote.id, deleted_at=None).first()
    if linked_order:
        flash(
            f"Orçamento bloqueado para edição — já existe o Pedido #{linked_order.number} "
            f"gerado a partir dele. Edite o pedido diretamente.",
            "danger",
        )
        return redirect(url_for("quotes.detail", qid=qid))
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        was_approved = quote.status == "aprovado"
        QuoteService.update_quote(quote, data)
        if was_approved:
            quote.status = "pendente"
            db.session.commit()
            flash("Orçamento editado — status revertido para Pendente. O cliente precisará aprovar novamente.", "warning")
        if request.is_json:
            return jsonify({"id": quote.id, "number": quote.number,
                            "redirect": url_for("quotes.detail", qid=qid)})
        return redirect(url_for("quotes.detail", qid=qid))
    edit_data = json.dumps({"id": quote.id, "form": {
        "client_id": quote.client_id, "client_name": quote.client_name or "",
        "contact_name": quote.contact_name or "", "email": quote.email or "",
        "phone": quote.phone or "", "language": quote.language or "pt",
        "billing_type": quote.billing_type or "recibo",
        "payment_method": quote.payment_method or "",
        "payment_terms":  quote.payment_terms  or "",
        "obs": quote.obs or "",
        "items": [{"service_id": it.service_id, "category_id": it.category_id,
                   "ref_note": it.ref_note or "", "description": it.description or "",
                   "vehicle_description": it.vehicle_description or "",
                   "driver_name": it.driver_name or "", "state_code": it.state_code or "",
                   "quantity": it.quantity, "unit_price": it.unit_price,
                   "hour_extra": it.hour_extra or 0, "total_price": it.total_price,
                   "price_base": it.price_base or 0, "price_nf": it.price_nf or 0,
                   "price_cartao": it.price_cartao or 0, "price_nf_cartao": it.price_nf_cartao or 0,
                   "km_extra": it.km_extra or 0, "km_extra_rate": it.km_extra_rate or 0,
                   "sort_order": it.sort_order or 0}
                  for it in sorted(quote.items, key=lambda x: x.sort_order or 0)]
    }})
    states     = State.query.order_by(State.code).all()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    clients    = Client.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Client.name).all()
    drivers    = Driver.query.filter_by(company_id=current_user.company_id, deleted_at=None, is_active=True).order_by(Driver.name).all()
    services   = Service.query.filter_by(is_active=True).order_by(Service.name).all()
    catalog    = _catalog_json()
    nf_rate, card_rate = _get_rates()
    return render_template("quotes/new.html", states=states, categories=categories,
                           clients=clients, drivers=drivers, services=services,
                           billing_types=BILLING_TYPES, nf_rate=nf_rate, card_rate=card_rate,
                           catalog_json=json.dumps(catalog),
                           default_inclusions=DEFAULT_INCLUSIONS,
                           edit_data=edit_data, edit_quote=quote)


@quotes_bp.route("/<int:qid>/pdf/<lang>")
@login_required
def pdf(qid, lang):
    """Generate and download PDF in PT or EN."""
    if lang not in ("pt", "en"):
        abort(400)
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    from ...services.quote_pdf import generate_quote_pdf
    buf = generate_quote_pdf(quote, lang=lang)
    filename = f"{quote.number}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


@quotes_bp.route("/<int:qid>/approve", methods=["POST"])
@login_required
def approve(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote.status      = "aprovado"
    quote.approved_at = now_br()
    db.session.commit()
    flash("Orçamento aprovado.", "success")
    return redirect(url_for("quotes.detail", qid=qid))


@quotes_bp.route("/<int:qid>/reject", methods=["POST"])
@login_required
def reject(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote.status           = "reprovado"
    quote.rejected_at      = now_br()
    quote.rejection_reason = request.form.get("reason", "")
    db.session.commit()
    flash("Orçamento reprovado.", "info")
    return redirect(url_for("quotes.index"))


@quotes_bp.route("/<int:qid>/confirm-booking", methods=["POST"])
@login_required
def confirm_booking(qid):
    """Confirma orçamento aprovado → cria Booking + OS automaticamente."""
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    if quote.status not in ("aprovado", "pago"):
        flash("Orçamento precisa estar aprovado para gerar reserva.", "warning")
        return redirect(url_for("quotes.detail", qid=qid))
    booking = BookingService.create_from_quote(quote, user_id=current_user.id)
    flash(f"Reserva {booking.number} criada com Ordem de Serviço.", "success")
    return redirect(url_for("bookings.detail", bid=booking.id))


@quotes_bp.route("/<int:qid>/create-os", methods=["POST"])
@login_required
def create_os(qid):
    """Cria OS diretamente a partir de um orçamento aprovado."""
    from datetime import datetime
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    if quote.status not in ("aprovado", "pago"):
        flash("Orçamento precisa estar aprovado para criar OS.", "warning")
        return redirect(url_for("quotes.detail", qid=qid))
    f = request.form
    pickup_dt = None
    date_str  = f.get("pickup_date", "").strip()
    time_str  = f.get("pickup_time", "").strip()
    if date_str and time_str:
        try:
            pickup_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    elif date_str:
        try:
            pickup_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    os_obj = sos.create_from_quote(quote, current_user.id, {
        "pickup_datetime":  pickup_dt,
        "pickup_location":  f.get("pickup_location",  "").strip() or None,
        "dropoff_location": f.get("dropoff_location", "").strip() or None,
        "passenger_name":   f.get("passenger_name",   "").strip() or None,
        "passenger_phone":  f.get("passenger_phone",  "").strip() or None,
        "pax_count":        int(f.get("pax_count", 1) or 1),
        "flight_number":    f.get("flight_number",    "").strip() or None,
        "notes":            f.get("notes",            "").strip() or None,
    })
    db.session.commit()
    flash(f"OS {os_obj.code} criada com sucesso.", "success")
    return redirect(url_for("quotes.detail", qid=quote.id))


@quotes_bp.route("/<int:qid>/delete", methods=["POST"])
@login_required
def delete(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote.soft_delete()
    db.session.commit()
    flash("Orçamento removido.", "info")
    return redirect(url_for("quotes.index"))
