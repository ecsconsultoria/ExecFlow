from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import dashboard_bp
from ...models.client   import Client
from ...models.quote    import Quote
from ...models.booking  import Booking
from ...models.financial import FinancialRecord
from ...models.company  import Company
from ...models.service_order import ServiceOrder
from ...models.order import Order
from ...extensions import db
import os
import uuid


@dashboard_bp.route("/")
@login_required
def index():
    cid = current_user.company_id
    total_clients  = Client.query.filter_by(company_id=cid, deleted_at=None).count()
    total_quotes   = Quote.query.filter_by(company_id=cid,  deleted_at=None).count()
    total_bookings = Booking.query.filter_by(company_id=cid, deleted_at=None).count()
    total_orders   = Order.query.filter_by(company_id=cid, deleted_at=None).count()

    pending_quotes = (Quote.query
                      .filter_by(company_id=cid, status="pendente", deleted_at=None)
                      .order_by(Quote.created_at.desc()).limit(10).all())

    upcoming_bookings = (Booking.query
                         .filter_by(company_id=cid, status="confirmado", deleted_at=None)
                         .order_by(Booking.service_date.asc()).limit(10).all())

    os_today = []
    from ...utils import now_br
    from datetime import datetime
    today = now_br().date()
    day_start = datetime.combine(today, datetime.min.time())
    day_end   = datetime.combine(today, datetime.max.time())
    os_today = (ServiceOrder.query
                .filter_by(company_id=cid)
                .filter(ServiceOrder.deleted_at.is_(None))
                .filter(ServiceOrder.pickup_datetime.between(day_start, day_end))
                .filter(ServiceOrder.status.notin_(["cancelado", "finalizado"]))
                .order_by(ServiceOrder.pickup_datetime.asc())
                .limit(5).all())

    revenue = (
        FinancialRecord.query
        .filter(FinancialRecord.company_id == cid,
                FinancialRecord.type == "revenue",
                FinancialRecord.status == "pago")
        .with_entities(__import__("sqlalchemy").func.sum(FinancialRecord.amount))
        .scalar() or 0
    )

    return render_template(
        "dashboard/index.html",
        total_clients=total_clients,
        total_quotes=total_quotes,
        total_bookings=total_bookings,
        total_orders=total_orders,
        revenue=revenue,
        pending_quotes=pending_quotes,
        upcoming_bookings=upcoming_bookings,
        os_today=os_today,
    )


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    company = Company.query.get(current_user.company_id)
    if request.method == "POST":
        company.name     = (request.form.get("name", "") or company.name).strip() or company.name
        company.document = (request.form.get("document", "") or "").strip()
        company.email    = (request.form.get("email",   "") or "").strip()
        company.phone    = (request.form.get("phone",   "") or "").strip()
        company.address  = (request.form.get("address", "") or "").strip()

        # Logo: prefer file upload, fall back to URL field
        logo_file = request.files.get("logo_file")
        if logo_file and logo_file.filename:
            ext       = os.path.splitext(logo_file.filename)[1].lower()
            allowed   = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
            if ext not in allowed:
                flash("Formato de imagem não suportado. Use PNG, JPG, GIF, WEBP ou SVG.", "danger")
                return redirect(url_for("dashboard.settings"))
            filename  = f"logo_{company.id}_{uuid.uuid4().hex[:8]}{ext}"
            upload_dir = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_dir, exist_ok=True)
            logo_file.save(os.path.join(upload_dir, filename))
            company.logo_url = f"/uploads/{filename}"
        else:
            logo_url = (request.form.get("logo_url", "") or "").strip()
            company.logo_url = logo_url if logo_url else company.logo_url

        db.session.commit()
        flash("Configurações salvas.", "success")
        return redirect(url_for("dashboard.settings"))
    s = (company.settings or {}) if company else {}
    nf_rate   = float(s.get("nf_rate",   current_app.config.get("NF_RATE",   0.10)))
    card_rate = float(s.get("card_rate", current_app.config.get("CARD_RATE", 0.065)))
    return render_template("dashboard/settings.html", company=company,
                           nf_rate=nf_rate, card_rate=card_rate)


@dashboard_bp.route("/settings/rates", methods=["POST"])
@login_required
def save_rates():
    company = Company.query.get(current_user.company_id)
    try:
        nf   = float(request.form.get("nf_rate",   "0.10").replace(",", "."))
        card = float(request.form.get("card_rate", "0.065").replace(",", "."))
        if not (0 <= nf <= 1 and 0 <= card <= 1):
            raise ValueError
    except ValueError:
        flash("Valores inválidos. Use decimais entre 0 e 1.", "danger")
        return redirect(url_for("dashboard.settings"))
    s = dict(company.settings or {})
    s["nf_rate"]   = nf
    s["card_rate"] = card
    company.settings = s
    db.session.commit()
    flash("Taxas atualizadas.", "success")
    return redirect(url_for("dashboard.settings"))
