from datetime import date, timedelta
from calendar import monthrange
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from . import financial_bp
from ...utils import now_br
from ...utils.helpers import parse_brl
from ...services.financial_service import void_payment_financial_records
from ...utils.decorators import require_permission
from ...models.financial import FinancialRecord, AccountReceivable, FINANCIAL_CATEGORIES
from ...extensions import db
from ...utils.audit import log_activity

_PAYMENT_METHODS = ["PIX", "TRANSFERÊNCIA", "BOLETO", "DINHEIRO", "CARTÃO", "CHEQUE"]

_PERIOD_LABELS = {
    "this_month":  "Mês Atual",
    "last_month":  "Mês Anterior",
    "last_30":     "Últimos 30 dias",
    "last_3m":     "Últimos 3 Meses",
    "last_6m":     "Últimos 6 Meses",
    "custom":      "Personalizado",
}


def _financial_period_bounds(period, date_from_str, date_to_str, today):
    """Return (first, last) date range for the selected period."""
    if period == "custom":
        try:
            first = date.fromisoformat(date_from_str) if date_from_str else today.replace(day=1)
            last  = date.fromisoformat(date_to_str)   if date_to_str   else today
        except ValueError:
            first = today.replace(day=1)
            last  = today
        return first, last

    if period == "last_month":
        first_this = today.replace(day=1)
        last  = first_this - timedelta(days=1)
        first = last.replace(day=1)
        return first, last

    if period == "last_30":
        return today - timedelta(days=29), today

    if period == "last_3m":
        m = today.month - 2
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today

    if period == "last_6m":
        m = today.month - 5
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today

    # Default: this_month
    first = today.replace(day=1)
    last  = today.replace(day=monthrange(today.year, today.month)[1])
    return first, last


@financial_bp.route("/")
@login_required
@require_permission("financial.view")
def index():
    cid   = current_user.company_id
    today = now_br().date()

    period    = request.args.get("period", "this_month")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to",   "")
    ftype     = request.args.get("type",   "")
    fstat     = request.args.get("status", "")

    first, last = _financial_period_bounds(period, date_from, date_to, today)

    # Data de referência contábil: emission_date > paid_date > date(created_at)
    ref_date = func.coalesce(
        FinancialRecord.emission_date,
        FinancialRecord.paid_date,
        func.date(FinancialRecord.created_at),
    )

    # P&L do período (pagos, referenciados pela data contábil)
    _base = [
        FinancialRecord.company_id == cid,
        FinancialRecord.status == "pago",
        FinancialRecord.deleted_at.is_(None),
        ref_date.between(first, last),
    ]
    revenue = (db.session.query(func.sum(FinancialRecord.amount))
               .filter(*_base, FinancialRecord.type == "revenue")
               .scalar() or 0)
    costs = (db.session.query(func.sum(FinancialRecord.amount))
             .filter(*_base, FinancialRecord.type == "cost")
             .scalar() or 0)

    # Totais pendentes (globais)
    pending_revenue = (db.session.query(func.sum(FinancialRecord.amount))
                       .filter(FinancialRecord.company_id == cid,
                               FinancialRecord.type == "revenue",
                               FinancialRecord.deleted_at.is_(None),
                               FinancialRecord.status == "pendente")
                       .scalar() or 0)
    pending_costs = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(FinancialRecord.company_id == cid,
                             FinancialRecord.type == "cost",
                             FinancialRecord.deleted_at.is_(None),
                             FinancialRecord.status == "pendente")
                     .scalar() or 0)

    # Registros filtrados pelo período + tipo + status
    q = (FinancialRecord.query
         .filter_by(company_id=cid)
         .filter(FinancialRecord.deleted_at.is_(None))
         .filter(ref_date.between(first, last)))
    if ftype:
        q = q.filter(FinancialRecord.type == ftype)
    if fstat:
        q = q.filter(FinancialRecord.status == fstat)
    records = q.order_by(FinancialRecord.created_at.desc()).limit(500).all()

    pending_ar = (AccountReceivable.query.filter_by(company_id=cid, status="pendente")
                  .order_by(AccountReceivable.due_date.asc()).all())

    period_label = _PERIOD_LABELS.get(period, "Mês Atual")
    if period == "custom" and date_from and date_to:
        period_label = f"{date_from} a {date_to}"

    return render_template(
        "financial/index.html",
        records=records, pending_ar=pending_ar,
        revenue=revenue, costs=costs, profit=revenue - costs,
        pending_revenue=pending_revenue, pending_costs=pending_costs,
        period=period, date_from=date_from, date_to=date_to,
        p_start=first, p_end=last,
        period_label=period_label,
        period_labels=_PERIOD_LABELS,
        ftype=ftype, fstat=fstat,
        today=today,
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
@require_permission("financial.manage")
def new_record():
    if request.method == "POST":
        r = FinancialRecord(company_id=current_user.company_id)
        _save_record(r, request.form)
        db.session.add(r)
        db.session.flush()
        log_activity("financial", r.id, current_user.company_id, f"Lançamento {r.type} R$ {r.amount:.2f} criado", current_user.id)
        db.session.commit()
        flash("Lançamento criado.", "success")
        return redirect(url_for("financial.index"))
    return render_template("financial/form.html", record=None,
                           categories=FINANCIAL_CATEGORIES,
                           payment_methods=_PAYMENT_METHODS)


@financial_bp.route("/record/<int:rid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def edit_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).filter(FinancialRecord.deleted_at.is_(None)).first_or_404()
    if request.method == "POST":
        _save_record(r, request.form)
        log_activity("financial", r.id, current_user.company_id, "Lançamento editado", current_user.id)
        db.session.commit()
        flash("Lançamento atualizado.", "success")
        return redirect(url_for("financial.index"))
    return render_template("financial/form.html", record=r,
                           categories=FINANCIAL_CATEGORIES,
                           payment_methods=_PAYMENT_METHODS)


@financial_bp.route("/record/<int:rid>/delete", methods=["POST"])
@login_required
@require_permission("financial.manage")
def delete_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).filter(FinancialRecord.deleted_at.is_(None)).first_or_404()
    r.soft_delete()

    # Cascade: lançamento vinculado a parcela de SO → exclui o SO e limpa registros associados
    if r.type == "revenue" and r.reference and r.reference.startswith("order_payment:"):
        try:
            from ...models.order import OrderPayment
            from ...models.quote import Quote
            op_id = int(r.reference.split(":", 1)[1])
            op = db.session.get(OrderPayment, op_id)
            if op:
                order = op.order
                if order and order.company_id == current_user.company_id and order.status != "excluido":
                    order.status = "excluido"
                    # Reverte orçamento vinculado para permitir criação de novo SO
                    if order.quote_id:
                        quote = db.session.get(Quote, order.quote_id)
                        if quote and quote.status == "reserva_confirmada":
                            quote.status = "aprovado"
                    # Void demais FRs de receita deste SO (exceto o já excluído)
                    void_payment_financial_records(
                        [p for p in order.payments if f"order_payment:{p.id}" != r.reference],
                        "order_payment",
                    )
                    # Exclui POs vinculadas e seus FRs de custo
                    for po in order.purchase_orders:
                        if po.status not in ("excluido", "cancelado"):
                            po.status = "excluido"
                        void_payment_financial_records(po.payments, "po_payment")
                    log_activity("order", order.id, order.company_id,
                                 f"Excluído via painel financeiro (FR {r.id})", current_user.id)
        except Exception:
            import logging
            logging.exception("Erro ao cascatear exclusão de FR para SO")

    log_activity("financial", r.id, current_user.company_id, f"Lançamento {r.type} R$ {r.amount:.2f} excluído", current_user.id)
    db.session.commit()
    flash("Lançamento excluído.", "success")
    return redirect(url_for("financial.index"))

@financial_bp.route("/record/<int:rid>/baixa", methods=["POST"])
@login_required
@require_permission("financial.manage")
def baixa_record(rid):
    r = FinancialRecord.query.filter_by(id=rid, company_id=current_user.company_id).filter(FinancialRecord.deleted_at.is_(None)).first_or_404()
    paid_date_str    = request.form.get("paid_date")
    r.paid_date      = date.fromisoformat(paid_date_str) if paid_date_str else now_br().date()
    r.payment_method = request.form.get("payment_method") or r.payment_method
    raw_amount = request.form.get("paid_amount", "").strip()
    if raw_amount:
        r.amount = parse_brl(raw_amount)
    r.status = "pago"

    # Commit do lançamento PRIMEIRO — garante que a receita fica salva mesmo que
    # a sincronização com SO/PO falhe depois (mesmo padrão de order_service.baixa).
    log_activity("financial", r.id, current_user.company_id,
                 f"Baixa registrada R$ {r.amount:.2f} ({r.payment_method or '-'})", current_user.id)
    db.session.commit()

    _order_for_sync = None

    # --- Sincroniza baixa com OrderPayment e Order (best-effort) ---
    if r.type == "revenue" and r.reference and r.reference.startswith("order_payment:"):
        try:
            from ...models.order import OrderPayment
            from ...services import margin_service
            op_id = int(r.reference.split(":", 1)[1])
            op = db.session.get(OrderPayment, op_id)
            if op and not op.is_paid:
                op.paid_amount = r.amount
                op.paid_at     = r.paid_date
                op.paid_by     = current_user.id
                db.session.flush()
                order = op.order
                if order and all(p.is_paid for p in order.payments) and order.status not in ("concluido", "cancelado"):
                    order.status    = "concluido"
                    order.closed_at = now_br()
                    order.closed_by = current_user.id
                if order:
                    margin_service.recalculate_order(order)
                    _order_for_sync = order
                db.session.commit()
        except Exception:
            db.session.rollback()   # limpa sessão inválida; FR já está committed acima
            _order_for_sync = None
            import logging
            logging.exception("Erro ao sincronizar baixa financeira com SO/parcela")

    # --- Sincroniza baixa com POPayment e PurchaseOrder (best-effort) ---
    elif r.type == "cost" and r.reference and r.reference.startswith("po_payment:"):
        try:
            from ...models.purchase_order import POPayment
            pp_id = int(r.reference.split(":", 1)[1])
            pp = db.session.get(POPayment, pp_id)
            if pp and not pp.is_paid:
                pp.paid_amount = r.amount
                pp.paid_at     = r.paid_date
                pp.paid_by     = current_user.id
                db.session.flush()
                po = pp.purchase_order
                if po:
                    all_pmts   = list(po.payments)
                    total_amt  = sum(p.amount or 0 for p in all_pmts)
                    total_paid = sum(p.paid_amount or 0 for p in all_pmts)
                    if total_amt > 0 and total_paid >= total_amt and po.status == "faturado":
                        po.status  = "pago"
                        po.paid_at = now_br()
                db.session.commit()
        except Exception:
            db.session.rollback()   # limpa sessão inválida; FR já está committed acima
            import logging
            logging.exception("Erro ao sincronizar baixa financeira com PO/parcela")

    # Sincroniza lançamentos pendentes do SO — fora do try, igual ao order_service.baixa
    if _order_for_sync is not None:
        from ...services.order_service import _sync_order_pending_financials
        _sync_order_pending_financials(_order_for_sync)
        db.session.commit()

    flash("Baixa registrada com sucesso.", "success")
    return redirect(url_for("financial.index"))


# ─────────────────────────────────────────────────────────────────────────────
# Contas a Pagar (painel dedicado)
# ─────────────────────────────────────────────────────────────────────────────

@financial_bp.route("/payables")
@login_required
@require_permission("financial.view")
def payables():
    """Painel de Contas a Pagar — extrato de custos/despesas com período."""
    cid   = current_user.company_id
    today = now_br().date()

    period    = request.args.get("period", "this_month")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to",   "")

    first, last = _financial_period_bounds(period, date_from, date_to, today)

    ref_date = func.coalesce(
        FinancialRecord.emission_date,
        FinancialRecord.paid_date,
        func.date(FinancialRecord.created_at),
    )

    # Base: custos do período
    _base = [
        FinancialRecord.company_id == cid,
        FinancialRecord.type == "cost",
        FinancialRecord.deleted_at.is_(None),
    ]

    # Totais do período
    paid_in_period = (db.session.query(func.sum(FinancialRecord.amount))
                      .filter(*_base, FinancialRecord.status == "pago",
                              ref_date.between(first, last))
                      .scalar() or 0)

    pending_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, FinancialRecord.status == "pendente")
                     .scalar() or 0)

    overdue_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .scalar() or 0)

    # Contagem
    pending_count = (FinancialRecord.query
                     .filter(*_base, FinancialRecord.status == "pendente")
                     .count())

    overdue_count = (FinancialRecord.query
                     .filter(*_base, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .count())

    # Lista de registros do período
    records = (FinancialRecord.query
               .filter(*_base)
               .filter(ref_date.between(first, last))
               .order_by(FinancialRecord.due_date.asc(),
                         FinancialRecord.created_at.desc())
               .limit(500).all())

    period_label = _PERIOD_LABELS.get(period, "Mês Atual")
    if period == "custom" and date_from and date_to:
        period_label = f"{date_from} a {date_to}"

    return render_template(
        "financial/payables.html",
        records=records,
        paid_in_period=paid_in_period,
        pending_total=pending_total,
        overdue_total=overdue_total,
        pending_count=pending_count,
        overdue_count=overdue_count,
        period=period, date_from=date_from, date_to=date_to,
        p_start=first, p_end=last,
        period_label=period_label,
        period_labels=_PERIOD_LABELS,
        today=today,
        payment_methods=_PAYMENT_METHODS,
    )
