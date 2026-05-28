from datetime import date
from calendar import monthrange
from flask import render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func
from . import reports_bp
from ...utils import now_br
from ...models.quote    import Quote
from ...models.booking  import Booking
from ...models.financial import FinancialRecord
from ...models.service_order import ServiceOrder
from ...extensions import db
from ...utils.decorators import require_permission


@reports_bp.route("/")
@login_required
@require_permission("reports.view")
def index():
    cid   = current_user.company_id
    month = request.args.get("month", now_br().strftime("%Y-%m"))
    try:
        year, mon = map(int, month.split("-"))
    except ValueError:
        year, mon = now_br().year, now_br().month
    first = date(year, mon, 1)
    last  = date(year, mon, monthrange(year, mon)[1])

    total_quotes    = Quote.query.filter_by(company_id=cid, deleted_at=None).count()
    approved_quotes = Quote.query.filter_by(company_id=cid, status="aprovado", deleted_at=None).count()
    confirmed       = Quote.query.filter_by(company_id=cid, status="reserva_confirmada", deleted_at=None).count()

    booking_stats = (db.session.query(Booking.status, func.count(Booking.id))
                     .filter_by(company_id=cid, deleted_at=None)
                     .group_by(Booking.status).all())

    os_stats = (db.session.query(ServiceOrder.status, func.count(ServiceOrder.id))
                .filter_by(company_id=cid)
                .filter(ServiceOrder.deleted_at.is_(None))
                .group_by(ServiceOrder.status).all())

    revenue = (db.session.query(func.sum(FinancialRecord.amount))
               .filter(FinancialRecord.company_id == cid, FinancialRecord.type == "revenue",
                       FinancialRecord.deleted_at.is_(None),
                       FinancialRecord.paid_date.between(first, last))
               .scalar() or 0)
    costs = (db.session.query(func.sum(FinancialRecord.amount))
             .filter(FinancialRecord.company_id == cid, FinancialRecord.type == "cost",
                     FinancialRecord.deleted_at.is_(None),
                     FinancialRecord.paid_date.between(first, last))
             .scalar() or 0)

    return render_template("reports/index.html", month=month,
                           total_quotes=total_quotes, approved_quotes=approved_quotes,
                           confirmed=confirmed, booking_stats=dict(booking_stats),
                           os_stats=dict(os_stats),
                           revenue=revenue, costs=costs, profit=revenue - costs)
