from datetime import date
from calendar import monthrange
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from . import financial_bp
from ...utils import now_br
from ...models.financial import FinancialRecord, AccountReceivable
from ...extensions import db


@financial_bp.route("/")
@login_required
def index():
    cid   = current_user.company_id
    month = request.args.get("month", now_br().strftime("%Y-%m"))
    try:
        year, mon = map(int, month.split("-"))
    except ValueError:
        year, mon = now_br().year, now_br().month
    first = date(year, mon, 1)
    last  = date(year, mon, monthrange(year, mon)[1])

    revenue = (db.session.query(func.sum(FinancialRecord.amount))
               .filter(FinancialRecord.company_id == cid,
                       FinancialRecord.type == "revenue",
                       FinancialRecord.paid_date.between(first, last))
               .scalar() or 0)
    costs = (db.session.query(func.sum(FinancialRecord.amount))
             .filter(FinancialRecord.company_id == cid,
                     FinancialRecord.type == "cost",
                     FinancialRecord.paid_date.between(first, last))
             .scalar() or 0)

    records    = (FinancialRecord.query.filter_by(company_id=cid)
                  .order_by(FinancialRecord.created_at.desc()).limit(100).all())
    pending_ar = (AccountReceivable.query.filter_by(company_id=cid, status="pendente")
                  .order_by(AccountReceivable.due_date.asc()).all())

    return render_template("financial/index.html", records=records, pending_ar=pending_ar,
                           revenue=revenue, costs=costs, profit=revenue - costs, month=month)


@financial_bp.route("/record/new", methods=["GET", "POST"])
@login_required
def new_record():
    if request.method == "POST":
        r = FinancialRecord(
            company_id     = current_user.company_id,
            type           = request.form["type"],
            category       = request.form.get("category"),
            description    = request.form.get("description"),
            amount         = float(request.form["amount"]),
            status         = request.form.get("status", "pendente"),
            payment_method = request.form.get("payment_method"),
            notes          = request.form.get("notes"),
        )
        if request.form.get("due_date"):
            r.due_date = date.fromisoformat(request.form["due_date"])
        if request.form.get("paid_date"):
            r.paid_date = date.fromisoformat(request.form["paid_date"])
        db.session.add(r)
        db.session.commit()
        flash("Lançamento criado.", "success")
        return redirect(url_for("financial.index"))
    return render_template("financial/form.html", record=None)
