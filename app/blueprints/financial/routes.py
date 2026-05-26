from datetime import date
from calendar import monthrange
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from . import financial_bp
from ...utils import now_br
from ...models.financial import FinancialRecord, AccountReceivable, FINANCIAL_CATEGORIES
from ...extensions import db

_PAYMENT_METHODS = ["PIX", "TRANSFERÊNCIA", "BOLETO", "DINHEIRO", "CARTÃO", "CHEQUE"]


@financial_bp.route("/")
@login_required
def index():
    cid   = current_user.company_id
    month = request.args.get("month", now_br().strftime("%Y-%m"))
    ftype = request.args.get("type",   "")
    fstat = request.args.get("status", "")
    try:
        year, mon = map(int, month.split("-"))
    except ValueError:
        year, mon = now_br().year, now_br().month
    first = date(year, mon, 1)
    last  = date(year, mon, monthrange(year, mon)[1])

    # P&L do mês (pagos no período)
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

    # Totais pendentes (globais)
    pending_revenue = (db.session.query(func.sum(FinancialRecord.amount))
                       .filter(FinancialRecord.company_id == cid,
                               FinancialRecord.type == "revenue",
                               FinancialRecord.status == "pendente")
                       .scalar() or 0)
    pending_costs = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(FinancialRecord.company_id == cid,
                             FinancialRecord.type == "cost",
                             FinancialRecord.status == "pendente")
                     .scalar() or 0)

    # Registros filtrados
    q = FinancialRecord.query.filter_by(company_id=cid)
    if ftype:
        q = q.filter(FinancialRecord.type == ftype)
    if fstat:
        q = q.filter(FinancialRecord.status == fstat)
    records = q.order_by(FinancialRecord.created_at.desc()).limit(200).all()

    pending_ar = (AccountReceivable.query.filter_by(company_id=cid, status="pendente")
                  .order_by(AccountReceivable.due_date.asc()).all())

    return render_template(
        "financial/index.html",
        records=records, pending_ar=pending_ar,
        revenue=revenue, costs=costs, profit=revenue - costs,
        pending_revenue=pending_revenue, pending_costs=pending_costs,
        month=month, ftype=ftype, fstat=fstat,
        today=now_br().date(),
        payment_methods=_PAYMENT_METHODS,
    )


def _save_record(r, form):
    r.type           = form["type"]
    r.category       = form.get("category") or None
    r.description    = form.get("description")
    r.amount         = float(form["amount"])
    r.status         = form.get("status", "pendente")
    r.payment_method = form.get("payment_method") or None
    r.notes          = form.get("notes") or None
    r.due_date       = date.fromisoformat(form["due_date"])  if form.get("due_date")  else None
    r.paid_date      = date.fromisoformat(form["paid_date"]) if form.get("paid_date") else None


@financial_bp.route("/record/new", methods=["GET", "POST"])
@login_required
def new_record():
    if request.method == "POST":
        r = FinancialRecord(company_id=current_user.company_id)
        _save_record(r, request.form)
        db.session.add(r)
        db.session.commit()
        flash("Lançamento criado.", "success")
        return redirect(url_for("financial.index"))
    return render_template("financial/form.html", record=None,
                           categories=FINANCIAL_CATEGORIES,
                           payment_methods=_PAYMENT_METHODS)


@financial_bp.route("/record/<int:rid>/edit", methods=["GET", "POST"])
@login_required
def edit_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).first_or_404()
    if request.method == "POST":
        _save_record(r, request.form)
        db.session.commit()
        flash("Lançamento atualizado.", "success")
        return redirect(url_for("financial.index"))
    return render_template("financial/form.html", record=r,
                           categories=FINANCIAL_CATEGORIES,
                           payment_methods=_PAYMENT_METHODS)


@financial_bp.route("/record/<int:rid>/delete", methods=["POST"])
@login_required
def delete_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash("Lançamento excluído.", "success")
    return redirect(url_for("financial.index"))


@financial_bp.route("/record/<int:rid>/baixa", methods=["POST"])
@login_required
def baixa_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).first_or_404()
    paid_date_str    = request.form.get("paid_date")
    r.paid_date      = date.fromisoformat(paid_date_str) if paid_date_str else now_br().date()
    r.payment_method = request.form.get("payment_method") or r.payment_method
    r.status         = "pago"
    db.session.commit()
    flash("Baixa registrada com sucesso.", "success")
    return redirect(url_for("financial.index"))
