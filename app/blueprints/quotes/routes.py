import json
import os
from flask import make_response, render_template, request, redirect, url_for, flash, jsonify, current_app, abort, send_file
from flask_login import login_required, current_user
from sqlalchemy.orm import lazyload, joinedload
from . import quotes_bp
from ...models.quote   import Quote, QuoteItem, QuoteInclusion, BILLING_TYPES, QUOTE_STATUSES, DEFAULT_INCLUSIONS
from ...models.client  import Client
from ...models.service import Service, ServicePricing, State
from ...models.vehicle import VehicleCategory
from ...models.driver  import Driver
from ...models.company import Company
from ...extensions import db
from ...utils.decorators import require_permission
from ...services.quote_service   import QuoteService
from ...utils import now_br, make_client_token
from ...utils.export import csv_response
from ...utils.audit import log_activity
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
@require_permission("quote.view")
def index():
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    # Quote declares creator/approver/rejecter as lazy="joined". Template only
    # uses scalar columns, so neutralize default joineds for speed.
    query  = (Quote.query
              .options(lazyload('*'), joinedload(Quote.client))
              .filter_by(company_id=current_user.company_id, deleted_at=None))
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Quote.status != "excluido")
    if q:
        query = query.filter(Quote.client_name.ilike(f"%{q}%") | Quote.number.ilike(f"%{q}%"))
    quotes = query.order_by(Quote.created_at.desc()).all()
    return render_template("quotes/index.html", quotes=quotes, status=status, q=q,
                           QUOTE_STATUSES=QUOTE_STATUSES)


@quotes_bp.route("/export")
@login_required
@require_permission("quote.view")
def export_csv():
    """Exporta lista de RFQs como CSV (Excel)."""
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    query  = (Quote.query
              .options(lazyload('*'), joinedload(Quote.client))
              .filter_by(company_id=current_user.company_id, deleted_at=None))
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Quote.status != "excluido")
    if q:
        query = query.filter(Quote.client_name.ilike(f"%{q}%") | Quote.number.ilike(f"%{q}%"))
    quotes = query.order_by(Quote.created_at.desc()).all()

    from datetime import date as _date
    headers = ["Nº RFQ", "Nº SO", "Cliente", "Data", "Total", "Status"]
    rows = []
    for qt in quotes:
        so_number = "–"
        if qt.orders:
            active = [o for o in qt.orders if o.status not in ("cancelado", "excluido") and o.deleted_at is None]
            if active:
                so_number = active[0].number
        rows.append([
            qt.number,
            so_number,
            qt.client.name if qt.client else (qt.client_name or "–"),
            qt.created_at.strftime("%d/%m/%Y") if qt.created_at else "–",
            f"R$ {qt.total_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if qt.total_amount else "R$ 0,00",
            qt.status_label,
        ])
    filename = f"rfqs_{_date.today().isoformat()}.csv"
    return csv_response(filename, headers, rows)


@quotes_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("quote.create")
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
                "usd_rate":    request.form.get("usd_rate", ""),
                "items":       [],
                "inclusions":  [],
            }
        quote = QuoteService.create_quote(current_user.company_id, data, current_user.id)
        log_activity("quote", quote.id, current_user.company_id, "Orçamento criado", current_user.id)
        db.session.commit()
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
@require_permission("quote.view")
def detail(qid):
    from ...models.order import Order
    from ...models.audit import AuditLog
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    # SO ativa (não cancelada, não excluída) — usada para bloquear nova criação
    quote_order = Order.query.filter_by(quote_id=quote.id, deleted_at=None).filter(
        Order.status.notin_(["cancelado", "excluido"])
    ).first()
    # Histórico completo de SOs vinculadas (inclui canceladas)
    all_orders = Order.query.filter_by(quote_id=quote.id, deleted_at=None).order_by(Order.id.desc()).all()
    service_order = ServiceOrder.query.filter_by(quote_id=quote.id).filter(ServiceOrder.deleted_at.is_(None)).first()
    audit_logs    = AuditLog.query.filter_by(entity="quote", entity_id=quote.id).order_by(AuditLog.created_at.asc()).all()
    resp = make_response(render_template("quotes/detail.html", quote=quote, billing_types=BILLING_TYPES,
                           service_order=service_order, quote_order=quote_order,
                           all_orders=all_orders, audit_logs=audit_logs))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@quotes_bp.route("/<int:qid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("quote.edit")
def edit(qid):
    from ...models.order import Order
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    # Lock: cannot edit a quote that has an active (non-cancelled, non-excluded) order
    active_order = Order.query.filter_by(quote_id=quote.id, deleted_at=None).filter(
        Order.status.notin_(['cancelado', 'excluido'])
    ).first()
    if active_order:
        flash(
            f"Orçamento bloqueado para edição — já existe o Pedido #{active_order.number} "
            f"gerado a partir dele. Edite o pedido diretamente.",
            "danger",
        )
        return redirect(url_for("quotes.detail", qid=qid))
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        was_approved = quote.status == "aprovado"
        QuoteService.update_quote(quote, data)
        log_activity("quote", quote.id, current_user.company_id, "Orçamento editado", current_user.id)
        if was_approved:
            quote.status = "pendente"
        db.session.commit()
        if was_approved:
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
        "usd_rate": quote.usd_rate or "",
        "obs": quote.obs or "",
        "inclusions": [{"text_pt": inc.text_pt, "text_en": inc.text_en or "",
                         "included": inc.included, "sort_order": inc.sort_order}
                        for inc in sorted(quote.inclusions, key=lambda x: x.sort_order or 0)]
                      or [{"text_pt": d["text_pt"], "text_en": d["text_en"],
                            "included": True, "sort_order": i}
                           for i, d in enumerate(DEFAULT_INCLUSIONS)],
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
@require_permission("quote.view")
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
@require_permission("quote.approve")
def approve(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote.status      = "aprovado"
    quote.approved_at = now_br()
    quote.approved_by = current_user.id
    log_activity("quote", quote.id, current_user.company_id, "Aprovado", current_user.id)
    db.session.commit()
    flash("Orçamento aprovado.", "success")
    return redirect(url_for("quotes.detail", qid=qid))


@quotes_bp.route("/<int:qid>/reopen", methods=["POST"])
@login_required
@require_permission("quote.approve")
def reopen(qid):
    """Reabre RFQ aprovada (volta para pendente) — apenas se não houver SO ativa."""
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    if quote.status not in ('aprovado', 'pago'):
        flash("Apenas orçamentos aprovados podem ser reabertos.", "warning")
        return redirect(url_for("quotes.detail", qid=qid))

    # Verifica se existe SO ativa vinculada
    from ...models.order import Order
    active_order = Order.query.filter_by(quote_id=quote.id, deleted_at=None).filter(
        Order.status.notin_(['cancelado', 'excluido'])).first()
    if active_order:
        flash(f"Não é possível reabrir: existe SO ativa ({active_order.number}).", "warning")
        return redirect(url_for("quotes.detail", qid=qid))

    quote.status      = "pendente"
    quote.approved_at = None
    quote.approved_by = None
    log_activity("quote", quote.id, current_user.company_id, "Reaberto (SO excluída)", current_user.id)
    db.session.commit()
    flash("Orçamento reaberto. Agora você pode editar ou reprovar.", "success")
    return redirect(url_for("quotes.detail", qid=qid))


@quotes_bp.route("/<int:qid>/reject", methods=["POST"])
@login_required
@require_permission("quote.approve")
def reject(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).first_or_404()
    quote.status           = "reprovado"
    quote.rejected_at      = now_br()
    quote.rejected_by      = current_user.id
    quote.rejection_reason = request.form.get("reason", "")
    log_activity("quote", quote.id, current_user.company_id, "Reprovado", current_user.id)
    db.session.commit()
    flash("Orçamento reprovado.", "info")
    return redirect(url_for("quotes.index"))



@quotes_bp.route("/<int:qid>/create-os", methods=["POST"])
@login_required
@require_permission("quote.approve")
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
    log_activity("quote", quote.id, current_user.company_id, f"OS {os_obj.code} criada", current_user.id)
    db.session.commit()
    flash(f"OS {os_obj.code} criada com sucesso.", "success")
    return redirect(url_for("quotes.detail", qid=quote.id))


@quotes_bp.route("/<int:qid>/delete", methods=["POST"])
@login_required
@require_permission("quote.delete")
def delete(qid):
    quote = Quote.query.filter_by(id=qid, company_id=current_user.company_id, deleted_at=None).filter(
        Quote.status != "excluido"
    ).first_or_404()
    quote.status = "excluido"
    log_activity("quote", quote.id, current_user.company_id, "Excluído", current_user.id)
    db.session.commit()
    flash("Orçamento removido.", "info")
    return redirect(url_for("quotes.index"))
