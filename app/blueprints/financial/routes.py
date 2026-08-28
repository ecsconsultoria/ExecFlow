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
from ...models.financial_catalog import (
    FinancialCategory, CostCenter,
    FINANCIAL_CATEGORY_TYPES, FINANCIAL_CATEGORY_TYPE_LABELS,
)
from ...extensions import db
from ...utils.audit import log_activity

_PAYMENT_METHODS = ["PIX", "TRANSFERÊNCIA", "BOLETO", "DINHEIRO", "CARTÃO", "CHEQUE"]

_PERIOD_LABELS = {
    "all":          "Todos",
    "today":        "Hoje",
    "yesterday":    "Ontem",
    "last_7":       "Últimos 7 dias",
    "last_30":      "Últimos 30 dias",
    "this_month":   "Este mês",
    "last_month":   "Mês passado",
    "this_quarter": "Este trimestre",
    "this_year":    "Este ano",
    "custom":       "Personalizado...",
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

    if period == "all":
        return date(2000, 1, 1), date(2099, 12, 31)

    if period == "today":
        return today, today

    if period == "yesterday":
        return today - timedelta(days=1), today - timedelta(days=1)

    if period == "last_7":
        return today - timedelta(days=6), today

    if period == "last_30":
        return today - timedelta(days=29), today

    if period == "last_month":
        first_this = today.replace(day=1)
        last  = first_this - timedelta(days=1)
        first = last.replace(day=1)
        return first, last

    if period == "this_quarter":
        q = (today.month - 1) // 3
        first = date(today.year, q * 3 + 1, 1)
        last_month = q * 3 + 3
        last = date(today.year, last_month, monthrange(today.year, last_month)[1])
        return first, last

    if period == "this_year":
        return date(today.year, 1, 1), today

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

    period    = request.args.get("period", "all")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to",   "")
    ftype     = request.args.get("type",   "")
    fstat     = request.args.get("status", "")
    fclient   = request.args.get("client", "")
    fsupplier = request.args.get("supplier", "")

    first, last = _financial_period_bounds(period, date_from, date_to, today)

    # ── Filtro por cliente (SO) ou fornecedor (PO) ──
    allowed_refs = None  # se definido, filtra FinancialRecord.reference
    if fclient:
        from ...models.client import Client
        from ...models.order import Order, OrderPayment
        client_obj = Client.query.filter_by(
            company_id=cid, id=int(fclient) if fclient.isdigit() else 0, deleted_at=None
        ).first()
        if client_obj:
            order_ids = [o[0] for o in db.session.query(Order.id).filter_by(
                company_id=cid, client_id=client_obj.id, deleted_at=None
            ).all()]
            if order_ids:
                pmt_ids = [p[0] for p in db.session.query(OrderPayment.id).filter(
                    OrderPayment.order_id.in_(order_ids)
                ).all()]
                if pmt_ids:
                    allowed_refs = {f"order_payment:{pid}" for pid in pmt_ids}
    if fsupplier:
        from ...models.purchase_order import PurchaseOrder, POPayment
        po_ids = [p[0] for p in db.session.query(PurchaseOrder.id).filter_by(
            company_id=cid, supplier_id=int(fsupplier) if fsupplier.isdigit() else 0, deleted_at=None
        ).all()]
        if po_ids:
            pmt_ids = [p[0] for p in db.session.query(POPayment.id).filter(
                POPayment.po_id.in_(po_ids)
            ).all()]
            if pmt_ids:
                po_refs = {f"po_payment:{pid}" for pid in pmt_ids}
                allowed_refs = po_refs if allowed_refs is None else allowed_refs | po_refs

    # Data de referência contábil: emission_date > paid_date > date(created_at)
    ref_date = func.coalesce(
        FinancialRecord.emission_date,
        FinancialRecord.paid_date,
        func.date(FinancialRecord.created_at),
    )

    # Totais do período (pagos + pendentes, referenciados pela data contábil)
    _base_period = [
        FinancialRecord.company_id == cid,
        FinancialRecord.deleted_at.is_(None),
        ref_date.between(first, last),
    ]
    _ref_filter = [FinancialRecord.reference.in_(allowed_refs)] if allowed_refs is not None else []

    revenue_paid = (db.session.query(func.sum(FinancialRecord.amount))
                    .filter(*_base_period, *_ref_filter,
                            FinancialRecord.type == "revenue",
                            FinancialRecord.status == "pago")
                    .scalar() or 0)
    revenue_pending = (db.session.query(func.sum(FinancialRecord.amount))
                       .filter(*_base_period, *_ref_filter,
                               FinancialRecord.type == "revenue",
                               FinancialRecord.status == "pendente")
                       .scalar() or 0)
    costs_paid = (db.session.query(func.sum(FinancialRecord.amount))
                  .filter(*_base_period, *_ref_filter,
                          FinancialRecord.type == "cost",
                          FinancialRecord.status == "pago")
                  .scalar() or 0)
    costs_pending = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base_period, *_ref_filter,
                             FinancialRecord.type == "cost",
                             FinancialRecord.status == "pendente")
                     .scalar() or 0)

    # Aliases para o template (compatibilidade + novos nomes)
    revenue = revenue_paid
    costs = costs_paid
    # Etapa 2: cards "A Receber/A Pagar" agora respeitam o período selecionado
    # (mesma data contábil ref_date dos totais pagos/pendentes).
    pending_revenue = (db.session.query(func.sum(FinancialRecord.amount))
                       .filter(FinancialRecord.company_id == cid,
                               FinancialRecord.type == "revenue",
                               FinancialRecord.deleted_at.is_(None),
                               FinancialRecord.status == "pendente",
                               ref_date.between(first, last),
                               *_ref_filter)
                       .scalar() or 0)
    pending_costs = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(FinancialRecord.company_id == cid,
                             FinancialRecord.type == "cost",
                             FinancialRecord.deleted_at.is_(None),
                             FinancialRecord.status == "pendente",
                             ref_date.between(first, last),
                             *_ref_filter)
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
    if allowed_refs is not None:
        q = q.filter(FinancialRecord.reference.in_(allowed_refs))
    records = q.order_by(FinancialRecord.created_at.desc()).limit(500).all()

    # Resolve SO number + client name from reference (e.g. "order_payment:42")
    record_refs = {}  # record_id -> {so_number, client_name, order_id}
    if ftype in ("revenue", ""):
        pmt_ids = []
        for r in records:
            if r.reference and r.reference.startswith("order_payment:"):
                try:
                    pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if pmt_ids:
            from ...models.order import OrderPayment, Order
            from sqlalchemy import func as sa_func
            pmt_rows = (db.session.query(OrderPayment.id, OrderPayment.order_id, OrderPayment.installment_no)
                        .filter(OrderPayment.id.in_(pmt_ids)).all())
            pmt_map = {p.id: (p.order_id, p.installment_no) for p in pmt_rows}
            order_ids = list(set(oid for oid, _ in pmt_map.values()))
            if order_ids:
                order_rows = (db.session.query(Order.id, Order.number, Order.client_name)
                              .filter(Order.id.in_(order_ids)).all())
                order_map = {o.id: (o.number, o.client_name) for o in order_rows}
                # Conta total de parcelas por SO
                total_pmts = dict(db.session.query(
                    OrderPayment.order_id, sa_func.count(OrderPayment.id)
                ).filter(OrderPayment.order_id.in_(order_ids)).group_by(OrderPayment.order_id).all())
                for r in records:
                    if r.reference and r.reference.startswith("order_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            entry = pmt_map.get(pid)
                            if entry:
                                oid, inst_no = entry
                                if oid and oid in order_map:
                                    tot = total_pmts.get(oid, 1)
                                    record_refs[r.id] = {
                                        "order_id": oid,
                                        "so_number": order_map[oid][0],
                                        "client_name": order_map[oid][1],
                                        "installment": f"{inst_no}/{tot}" if tot > 1 else "",
                                    }
                        except (ValueError, IndexError):
                            pass

    # Resolve PO number + supplier name from reference (e.g. "po_payment:42")
    if ftype in ("cost", ""):
        po_pmt_ids = []
        for r in records:
            if r.reference and r.reference.startswith("po_payment:"):
                try:
                    po_pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if po_pmt_ids:
            from ...models.purchase_order import POPayment, PurchaseOrder
            from sqlalchemy import func as sa_func2
            po_pmt_rows = (db.session.query(POPayment.id, POPayment.po_id, POPayment.installment_no)
                           .filter(POPayment.id.in_(po_pmt_ids)).all())
            po_pmt_map = {p.id: (p.po_id, p.installment_no) for p in po_pmt_rows}
            po_ids = list(set(po_id for po_id, _ in po_pmt_map.values()))
            if po_ids:
                po_rows = (db.session.query(PurchaseOrder.id, PurchaseOrder.number, PurchaseOrder.supplier_id)
                           .filter(PurchaseOrder.id.in_(po_ids)).all())
                supplier_ids = [p.supplier_id for p in po_rows if p.supplier_id]
                supplier_map = {}
                if supplier_ids:
                    from ...models.supplier import Supplier
                    sup_rows = (db.session.query(Supplier.id, Supplier.name)
                                .filter(Supplier.id.in_(supplier_ids)).all())
                    supplier_map = {s.id: s.name for s in sup_rows}
                # Conta total de parcelas por PO
                total_po_pmts = dict(db.session.query(
                    POPayment.po_id, sa_func2.count(POPayment.id)
                ).filter(POPayment.po_id.in_(po_ids)).group_by(POPayment.po_id).all())
                for r in records:
                    if r.reference and r.reference.startswith("po_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            entry = po_pmt_map.get(pid)
                            if entry:
                                po_id, inst_no = entry
                                po_row = next((p for p in po_rows if p.id == po_id), None)
                                if po_row:
                                    tot = total_po_pmts.get(po_id, 1)
                                    record_refs[r.id] = {
                                        "po_id": po_id,
                                        "po_number": po_row.number,
                                        "supplier_name": supplier_map.get(po_row.supplier_id, ""),
                                        "installment": f"{inst_no}/{tot}" if tot > 1 else "",
                                    }
                        except (ValueError, IndexError):
                            pass

    # ── Previsto (pendentes NÃO faturados) ──
    forecast_revenue = 0.0
    forecast_costs = 0.0
    # SO: pendentes de SOs não faturados/concluídos (filtrado por período)
    pending_rev_records = (FinancialRecord.query
                           .filter(FinancialRecord.company_id == cid,
                                   FinancialRecord.type == "revenue",
                                   FinancialRecord.status == "pendente",
                                   FinancialRecord.deleted_at.is_(None),
                                   ref_date.between(first, last),
                                   *_ref_filter)
                           .all())
    if pending_rev_records:
        rev_pmt_ids = []
        for r in pending_rev_records:
            if r.reference and r.reference.startswith("order_payment:"):
                try:
                    rev_pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if rev_pmt_ids:
            from ...models.order import OrderPayment, Order
            rev_orders = dict(db.session.query(OrderPayment.id, OrderPayment.order_id)
                              .filter(OrderPayment.id.in_(rev_pmt_ids)).all())
            rev_order_ids = set(rev_orders.values())
            if rev_order_ids:
                non_invoiced = set(db.session.query(Order.id)
                                   .filter(Order.id.in_(rev_order_ids),
                                           Order.status.notin_(['faturado', 'concluido']))
                                   .all())
                non_invoiced = {o[0] for o in non_invoiced}
                for r in pending_rev_records:
                    if r.reference and r.reference.startswith("order_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            oid = rev_orders.get(pid)
                            if oid and oid in non_invoiced:
                                forecast_revenue += r.amount or 0
                        except (ValueError, IndexError):
                            pass
    # PO: pendentes de POs não faturados/concluídos (filtrado por período)
    pending_cost_records = (FinancialRecord.query
                            .filter(FinancialRecord.company_id == cid,
                                    FinancialRecord.type == "cost",
                                    FinancialRecord.status == "pendente",
                                    FinancialRecord.deleted_at.is_(None),
                                    ref_date.between(first, last),
                                    *_ref_filter)
                            .all())
    if pending_cost_records:
        cost_pmt_ids = []
        for r in pending_cost_records:
            if r.reference and r.reference.startswith("po_payment:"):
                try:
                    cost_pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if cost_pmt_ids:
            from ...models.purchase_order import POPayment, PurchaseOrder
            cost_orders = dict(db.session.query(POPayment.id, POPayment.po_id)
                               .filter(POPayment.id.in_(cost_pmt_ids)).all())
            cost_po_ids = set(cost_orders.values())
            if cost_po_ids:
                non_invoiced_po = set(db.session.query(PurchaseOrder.id)
                                      .filter(PurchaseOrder.id.in_(cost_po_ids),
                                              PurchaseOrder.status.notin_(['faturado', 'concluido', 'pago']))
                                      .all())
                non_invoiced_po = {o[0] for o in non_invoiced_po}
                for r in pending_cost_records:
                    if r.reference and r.reference.startswith("po_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            po_id = cost_orders.get(pid)
                            if po_id and po_id in non_invoiced_po:
                                forecast_costs += r.amount or 0
                        except (ValueError, IndexError):
                            pass

    pending_ar = (AccountReceivable.query.filter_by(company_id=cid, status="pendente")
                  .order_by(AccountReceivable.due_date.asc()).all())

    period_label = _PERIOD_LABELS.get(period, "Todos")
    if period == "custom" and date_from and date_to:
        period_label = f"{date_from} a {date_to}"

    # Listas para dropdowns de cliente/fornecedor
    from ...models.client import Client as ClientModel
    from ...models.supplier import Supplier as SupplierModel
    clients = ClientModel.query.filter_by(company_id=cid, deleted_at=None).order_by(ClientModel.name).all()
    suppliers = SupplierModel.query.filter_by(company_id=cid, deleted_at=None, is_active=True).order_by(SupplierModel.name).all()

    return render_template(
        "financial/index.html",
        records=records, pending_ar=pending_ar, record_refs=record_refs,
        revenue=revenue, costs=costs, profit=revenue_paid - costs_paid,
        pending_revenue=pending_revenue, pending_costs=pending_costs,
        revenue_paid=revenue_paid, revenue_pending=revenue_pending,
        costs_paid=costs_paid, costs_pending=costs_pending,
        forecast_revenue=forecast_revenue, forecast_costs=forecast_costs,
        period=period, date_from=date_from, date_to=date_to,
        p_start=first, p_end=last,
        period_label=period_label,
        period_labels=_PERIOD_LABELS,
        ftype=ftype, fstat=fstat, fclient=fclient, fsupplier=fsupplier,
        clients=clients, suppliers=suppliers,
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
    if r.type == "expense":
        # Etapa 3B: despesas são editadas somente pela tela própria (com restrições)
        flash("Despesas são editadas pela tela Financeiro → Despesas.", "info")
        return redirect(url_for("financial.expenses"))
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
    if r.type == "expense":
        # Etapa 3B: despesa usa cancelamento, nunca soft-delete (histórico preservado)
        flash("Despesas não são excluídas — use Cancelar (despesa pendente).", "info")
        return redirect(url_for("financial.expenses"))
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

    # ── Etapa 2: baixa ATÔMICA — FR + parcela + status commitados juntos.
    # Se qualquer etapa falhar, um único rollback desfaz tudo (nada fica
    # "meio atualizado"), ao contrário do fluxo anterior em dois commits.
    _order_for_sync = None
    try:
        if r.type == "revenue" and r.reference and r.reference.startswith("order_payment:"):
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

        elif r.type == "cost" and r.reference and r.reference.startswith("po_payment:"):
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

        if _order_for_sync is not None:
            from ...services.order_service import _sync_order_pending_financials
            _sync_order_pending_financials(_order_for_sync)

        log_activity("financial", r.id, current_user.company_id,
                     f"Baixa registrada R$ {r.amount:.2f} ({r.payment_method or '-'})", current_user.id)
        db.session.commit()
    except Exception:
        db.session.rollback()   # transação única — nada persiste parcialmente
        import logging
        logging.exception("Erro na baixa financeira — operação revertida")
        flash("Erro ao registrar a baixa. Operação revertida — nada foi alterado.", "danger")
        return redirect(url_for("financial.index"))

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

    period    = request.args.get("period", "all")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to",   "")
    fsupplier = request.args.get("supplier", "")

    first, last = _financial_period_bounds(period, date_from, date_to, today)

    # ── Filtro por fornecedor ──
    allowed_refs = None
    if fsupplier:
        from ...models.purchase_order import PurchaseOrder, POPayment
        po_ids = [p[0] for p in db.session.query(PurchaseOrder.id).filter_by(
            company_id=cid, supplier_id=int(fsupplier) if fsupplier.isdigit() else 0, deleted_at=None
        ).all()]
        if po_ids:
            pmt_ids = [p[0] for p in db.session.query(POPayment.id).filter(
                POPayment.po_id.in_(po_ids)
            ).all()]
            if pmt_ids:
                allowed_refs = {f"po_payment:{pid}" for pid in pmt_ids}

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
    _ref_filter = [FinancialRecord.reference.in_(allowed_refs)] if allowed_refs is not None else []

    # Totais do período
    paid_in_period = (db.session.query(func.sum(FinancialRecord.amount))
                      .filter(*_base, *_ref_filter, FinancialRecord.status == "pago",
                              ref_date.between(first, last))
                      .scalar() or 0)

    pending_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente")
                     .scalar() or 0)

    overdue_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .scalar() or 0)

    # Contagem
    pending_count = (FinancialRecord.query
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente")
                     .count())

    overdue_count = (FinancialRecord.query
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .count())

    # Lista de registros do período
    records = (FinancialRecord.query
               .filter(*_base, *_ref_filter)
               .filter(ref_date.between(first, last))
               .order_by(FinancialRecord.due_date.asc(),
                         FinancialRecord.created_at.desc())
               .limit(500).all())

    # Resolve PO number + supplier name from reference
    record_refs = {}
    if records:
        po_pmt_ids = []
        for r in records:
            if r.reference and r.reference.startswith("po_payment:"):
                try:
                    po_pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if po_pmt_ids:
            from ...models.purchase_order import POPayment, PurchaseOrder
            from ...models.supplier import Supplier
            from sqlalchemy import func as sa_func3
            po_pmt_rows = (db.session.query(POPayment.id, POPayment.po_id, POPayment.installment_no)
                           .filter(POPayment.id.in_(po_pmt_ids)).all())
            po_pmt_map = {p.id: (p.po_id, p.installment_no) for p in po_pmt_rows}
            po_ids = list(set(po_id for po_id, _ in po_pmt_map.values()))
            if po_ids:
                po_rows = (db.session.query(PurchaseOrder.id, PurchaseOrder.number, PurchaseOrder.supplier_id)
                           .filter(PurchaseOrder.id.in_(po_ids)).all())
                supplier_ids = [p.supplier_id for p in po_rows if p.supplier_id]
                supplier_map = {}
                if supplier_ids:
                    sup_rows = (db.session.query(Supplier.id, Supplier.name)
                                .filter(Supplier.id.in_(supplier_ids)).all())
                    supplier_map = {s.id: s.name for s in sup_rows}
                total_po_pmts = dict(db.session.query(
                    POPayment.po_id, sa_func3.count(POPayment.id)
                ).filter(POPayment.po_id.in_(po_ids)).group_by(POPayment.po_id).all())
                for r in records:
                    if r.reference and r.reference.startswith("po_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            entry = po_pmt_map.get(pid)
                            if entry:
                                po_id, inst_no = entry
                                po_row = next((p for p in po_rows if p.id == po_id), None)
                                if po_row:
                                    tot = total_po_pmts.get(po_id, 1)
                                    record_refs[r.id] = {
                                        "po_id": po_id,
                                        "po_number": po_row.number,
                                        "supplier_name": supplier_map.get(po_row.supplier_id, ""),
                                        "installment": f"{inst_no}/{tot}" if tot > 1 else "",
                                    }
                        except (ValueError, IndexError):
                            pass

    period_label = _PERIOD_LABELS.get(period, "Todos")
    if period == "custom" and date_from and date_to:
        period_label = f"{date_from} a {date_to}"

    from ...models.supplier import Supplier as SupplierModel
    suppliers = SupplierModel.query.filter_by(company_id=cid, deleted_at=None, is_active=True).order_by(SupplierModel.name).all()

    return render_template(
        "financial/payables.html",
        records=records, record_refs=record_refs,
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
        suppliers=suppliers, fsupplier=fsupplier,
    )


@financial_bp.route("/receivables")
@login_required
@require_permission("financial.view")
def receivables():
    """Painel de Contas a Receber — extrato de receitas com período e cliente."""
    cid   = current_user.company_id
    today = now_br().date()

    period    = request.args.get("period", "all")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to",   "")
    fclient   = request.args.get("client", "")

    first, last = _financial_period_bounds(period, date_from, date_to, today)

    # ── Filtro por cliente ──
    allowed_refs = None
    if fclient:
        from ...models.client import Client
        from ...models.order import Order, OrderPayment
        client_obj = Client.query.filter_by(
            company_id=cid, id=int(fclient) if fclient.isdigit() else 0, deleted_at=None
        ).first()
        if client_obj:
            order_ids = [o[0] for o in db.session.query(Order.id).filter_by(
                company_id=cid, client_id=client_obj.id, deleted_at=None
            ).all()]
            if order_ids:
                pmt_ids = [p[0] for p in db.session.query(OrderPayment.id).filter(
                    OrderPayment.order_id.in_(order_ids)
                ).all()]
                if pmt_ids:
                    allowed_refs = {f"order_payment:{pid}" for pid in pmt_ids}

    ref_date = func.coalesce(
        FinancialRecord.emission_date,
        FinancialRecord.paid_date,
        func.date(FinancialRecord.created_at),
    )

    _base = [
        FinancialRecord.company_id == cid,
        FinancialRecord.type == "revenue",
        FinancialRecord.deleted_at.is_(None),
    ]
    _ref_filter = [FinancialRecord.reference.in_(allowed_refs)] if allowed_refs is not None else []

    # Totais do período
    received_in_period = (db.session.query(func.sum(FinancialRecord.amount))
                          .filter(*_base, *_ref_filter, FinancialRecord.status == "pago",
                                  ref_date.between(first, last))
                          .scalar() or 0)

    pending_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente")
                     .scalar() or 0)

    overdue_total = (db.session.query(func.sum(FinancialRecord.amount))
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .scalar() or 0)

    pending_count = (FinancialRecord.query
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente")
                     .count())
    overdue_count = (FinancialRecord.query
                     .filter(*_base, *_ref_filter, FinancialRecord.status == "pendente",
                             FinancialRecord.due_date.isnot(None),
                             FinancialRecord.due_date < today)
                     .count())

    records = (FinancialRecord.query
               .filter(*_base, *_ref_filter)
               .filter(ref_date.between(first, last))
               .order_by(FinancialRecord.due_date.asc(),
                         FinancialRecord.created_at.desc())
               .limit(500).all())

    # Resolve SO number + client name from reference
    record_refs = {}
    if records:
        pmt_ids = []
        for r in records:
            if r.reference and r.reference.startswith("order_payment:"):
                try:
                    pmt_ids.append(int(r.reference.split(":")[1]))
                except (ValueError, IndexError):
                    pass
        if pmt_ids:
            from ...models.order import OrderPayment, Order
            from sqlalchemy import func as sa_func4
            pmt_rows = (db.session.query(OrderPayment.id, OrderPayment.order_id, OrderPayment.installment_no)
                        .filter(OrderPayment.id.in_(pmt_ids)).all())
            pmt_map = {p.id: (p.order_id, p.installment_no) for p in pmt_rows}
            order_ids = list(set(oid for oid, _ in pmt_map.values()))
            if order_ids:
                order_rows = (db.session.query(Order.id, Order.number, Order.client_name)
                              .filter(Order.id.in_(order_ids)).all())
                order_map = {o.id: (o.number, o.client_name) for o in order_rows}
                total_pmts = dict(db.session.query(
                    OrderPayment.order_id, sa_func4.count(OrderPayment.id)
                ).filter(OrderPayment.order_id.in_(order_ids)).group_by(OrderPayment.order_id).all())
                for r in records:
                    if r.reference and r.reference.startswith("order_payment:"):
                        try:
                            pid = int(r.reference.split(":")[1])
                            entry = pmt_map.get(pid)
                            if entry:
                                oid, inst_no = entry
                                if oid and oid in order_map:
                                    tot = total_pmts.get(oid, 1)
                                    record_refs[r.id] = {
                                        "order_id": oid,
                                        "so_number": order_map[oid][0],
                                        "client_name": order_map[oid][1],
                                        "installment": f"{inst_no}/{tot}" if tot > 1 else "",
                                    }
                        except (ValueError, IndexError):
                            pass

    period_label = _PERIOD_LABELS.get(period, "Todos")
    if period == "custom" and date_from and date_to:
        period_label = f"{date_from} a {date_to}"

    from ...models.client import Client as ClientModel
    clients = ClientModel.query.filter_by(company_id=cid, deleted_at=None).order_by(ClientModel.name).all()

    return render_template(
        "financial/receivables.html",
        records=records, record_refs=record_refs,
        received_in_period=received_in_period,
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
        clients=clients, fclient=fclient,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 3A — Categorias financeiras e Centros de custo (administração)
# RBAC: mesmas permissões do módulo financeiro (financial.manage).
# ─────────────────────────────────────────────────────────────────────────────

@financial_bp.route("/categories")
@login_required
@require_permission("financial.manage")
def categories():
    cats = (FinancialCategory.query
            .filter_by(company_id=current_user.company_id)
            .order_by(FinancialCategory.type, FinancialCategory.id)
            .all())
    by_parent = {}
    for c in cats:
        by_parent.setdefault(c.parent_id, []).append(c)

    def _walk(pid, depth, acc):
        for child in by_parent.get(pid, []):
            acc.append({"cat": child, "depth": depth})
            _walk(child.id, depth + 1, acc)

    items = []
    for root in [c for c in cats if c.parent_id is None]:
        items.append({"cat": root, "depth": 0})
        _walk(root.id, 1, items)
    return render_template("financial/categories.html", items=items,
                           labels=FINANCIAL_CATEGORY_TYPE_LABELS)


@financial_bp.route("/categories/new", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def new_category():
    parents = (FinancialCategory.query
               .filter_by(company_id=current_user.company_id, active=True)
               .order_by(FinancialCategory.type, FinancialCategory.name).all())
    if request.method == "POST":
        try:
            ctype = request.form.get("type", "expense")
            if ctype not in FINANCIAL_CATEGORY_TYPES:
                raise ValueError("Tipo inválido")
            parent_id = request.form.get("parent_id")
            parent = None
            if parent_id:
                parent = (FinancialCategory.query
                          .filter_by(id=int(parent_id), company_id=current_user.company_id)
                          .first_or_404())
                if parent.type != ctype:
                    raise ValueError("O pai deve ter o mesmo tipo da categoria")
            cat = FinancialCategory(
                company_id=current_user.company_id,
                name=(request.form.get("name", "") or "").strip(),
                description=(request.form.get("description", "") or "").strip() or None,
                type=ctype,
                parent_id=parent.id if parent else None,
                active=True,
            )
            if not cat.name:
                raise ValueError("Nome é obrigatório")
            db.session.add(cat)
            db.session.commit()
            flash("Categoria criada.", "success")
            return redirect(url_for("financial.categories"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/category_form.html", cat=None,
                           parents=parents, types=FINANCIAL_CATEGORY_TYPES,
                           labels=FINANCIAL_CATEGORY_TYPE_LABELS)


@financial_bp.route("/categories/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def edit_category(cid):
    cat = (FinancialCategory.query
           .filter_by(id=cid, company_id=current_user.company_id)
           .first_or_404())
    parents = (FinancialCategory.query
               .filter_by(company_id=current_user.company_id, active=True)
               .filter(FinancialCategory.id != cat.id)
               .order_by(FinancialCategory.type, FinancialCategory.name).all())
    if request.method == "POST":
        try:
            ctype = request.form.get("type", cat.type)
            if ctype not in FINANCIAL_CATEGORY_TYPES:
                raise ValueError("Tipo inválido")
            parent_id = request.form.get("parent_id")
            parent = None
            if parent_id:
                parent = (FinancialCategory.query
                          .filter_by(id=int(parent_id), company_id=current_user.company_id)
                          .first_or_404())
                if parent.type != ctype:
                    raise ValueError("O pai deve ter o mesmo tipo da categoria")
                if parent.id == cat.id:
                    raise ValueError("A categoria não pode ser pai dela mesma")
            cat.name = (request.form.get("name", "") or "").strip()
            if not cat.name:
                raise ValueError("Nome é obrigatório")
            cat.description = (request.form.get("description", "") or "").strip() or None
            cat.type = ctype
            cat.parent_id = parent.id if parent else None
            db.session.commit()
            flash("Categoria atualizada.", "success")
            return redirect(url_for("financial.categories"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/category_form.html", cat=cat,
                           parents=parents, types=FINANCIAL_CATEGORY_TYPES,
                           labels=FINANCIAL_CATEGORY_TYPE_LABELS)


@financial_bp.route("/categories/<int:cid>/toggle", methods=["POST"])
@login_required
@require_permission("financial.manage")
def toggle_category(cid):
    cat = (FinancialCategory.query
           .filter_by(id=cid, company_id=current_user.company_id)
           .first_or_404())
    cat.active = not cat.active
    db.session.commit()
    flash("Categoria " + ("ativada." if cat.active else "desativada."), "success")
    return redirect(url_for("financial.categories"))


@financial_bp.route("/cost-centers")
@login_required
@require_permission("financial.manage")
def cost_centers():
    centers = (CostCenter.query
               .filter_by(company_id=current_user.company_id)
               .order_by(CostCenter.name).all())
    return render_template("financial/cost_centers.html", centers=centers)


@financial_bp.route("/cost-centers/new", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def new_cost_center():
    if request.method == "POST":
        try:
            name = (request.form.get("name", "") or "").strip()
            if not name:
                raise ValueError("Nome é obrigatório")
            db.session.add(CostCenter(
                company_id=current_user.company_id,
                name=name,
                description=(request.form.get("description", "") or "").strip() or None,
                active=True,
            ))
            db.session.commit()
            flash("Centro de custo criado.", "success")
            return redirect(url_for("financial.cost_centers"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/cost_center_form.html", center=None)


@financial_bp.route("/cost-centers/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def edit_cost_center(cid):
    center = (CostCenter.query
              .filter_by(id=cid, company_id=current_user.company_id)
              .first_or_404())
    if request.method == "POST":
        try:
            name = (request.form.get("name", "") or "").strip()
            if not name:
                raise ValueError("Nome é obrigatório")
            center.name = name
            center.description = (request.form.get("description", "") or "").strip() or None
            db.session.commit()
            flash("Centro de custo atualizado.", "success")
            return redirect(url_for("financial.cost_centers"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/cost_center_form.html", center=center)


@financial_bp.route("/cost-centers/<int:cid>/toggle", methods=["POST"])
@login_required
@require_permission("financial.manage")
def toggle_cost_center(cid):
    center = (CostCenter.query
              .filter_by(id=cid, company_id=current_user.company_id)
              .first_or_404())
    center.active = not center.active
    db.session.commit()
    flash("Centro de custo " + ("ativado." if center.active else "desativado."), "success")
    return redirect(url_for("financial.cost_centers"))


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 3B — Despesas Gerais
# A despesa É o próprio FinancialRecord (type='expense', reference='expense:{id}').
# Não existe tabela própria: description/amount/datas/status vivem no ledger.
# SO/PO e fornecedor são opcionais; categoria (type=expense) e centro de custo
# são obrigatórios e sempre isolados por company_id.
# ─────────────────────────────────────────────────────────────────────────────

_EXPENSE_STATUS_LABELS = {
    "pendente":  "Pendente",
    "pago":      "Paga",
    "cancelado": "Cancelada",
}


def _expense_base_query():
    return (FinancialRecord.query
            .filter_by(company_id=current_user.company_id, type="expense")
            .filter(FinancialRecord.deleted_at.is_(None)))


@financial_bp.route("/expenses")
@login_required
def expenses():
    cid   = current_user.company_id
    today = now_br().date()
    first, last = _financial_period_bounds(
        request.args.get("period", "this_month"),
        request.args.get("date_from"), request.args.get("date_to"), today)

    q = _expense_base_query()
    fstatus = request.args.get("status", "")
    if fstatus:
        q = q.filter(FinancialRecord.status == fstatus)
    if request.args.get("category"):
        q = q.filter(FinancialRecord.financial_category_id == int(request.args["category"]))
    if request.args.get("cost_center"):
        q = q.filter(FinancialRecord.cost_center_id == int(request.args["cost_center"]))
    if request.args.get("supplier"):
        q = q.filter(FinancialRecord.supplier_id == int(request.args["supplier"]))
    records = q.order_by(FinancialRecord.due_date.desc()).limit(500).all()

    def _sum(cond, extra=()):
        return (db.session.query(func.sum(FinancialRecord.amount))
                .filter(FinancialRecord.company_id == cid,
                        FinancialRecord.type == "expense",
                        FinancialRecord.deleted_at.is_(None),
                        cond, *extra)
                .scalar() or 0.0)

    total_period = _sum(FinancialRecord.status != "cancelado",
                        (FinancialRecord.emission_date.isnot(None),
                         FinancialRecord.emission_date.between(first, last)))
    pending_total = _sum(FinancialRecord.status == "pendente")
    overdue_total = _sum(FinancialRecord.status == "pendente",
                         (FinancialRecord.due_date.isnot(None),
                          FinancialRecord.due_date < today))
    paid_total = _sum(FinancialRecord.status == "pago",
                      (FinancialRecord.paid_date.isnot(None),
                       FinancialRecord.paid_date.between(first, last)))

    categories = (FinancialCategory.query
                  .filter_by(company_id=cid, type="expense", active=True)
                  .order_by(FinancialCategory.name).all())
    centers = (CostCenter.query
               .filter_by(company_id=cid, active=True)
               .order_by(CostCenter.name).all())
    from ...models.supplier import Supplier
    suppliers = (Supplier.query
                 .filter_by(company_id=cid, deleted_at=None)
                 .order_by(Supplier.name).all())

    return render_template(
        "financial/expenses.html",
        records=records, today=today,
        total_period=total_period, pending_total=pending_total,
        overdue_total=overdue_total, paid_total=paid_total,
        categories=categories, centers=centers, suppliers=suppliers,
        fstatus=fstatus,
        status_labels=_EXPENSE_STATUS_LABELS,
        period=request.args.get("period", "this_month"),
        date_from=request.args.get("date_from", ""),
        date_to=request.args.get("date_to", ""),
        period_labels=_PERIOD_LABELS,
    )


def _expense_form_context():
    cid = current_user.company_id
    categories = (FinancialCategory.query
                  .filter_by(company_id=cid, type="expense", active=True)
                  .order_by(FinancialCategory.name).all())
    centers = (CostCenter.query
               .filter_by(company_id=cid, active=True)
               .order_by(CostCenter.name).all())
    from ...models.supplier import Supplier
    suppliers = (Supplier.query
                 .filter_by(company_id=cid, deleted_at=None)
                 .order_by(Supplier.name).all())
    from ...models.order import Order
    from ...models.purchase_order import PurchaseOrder
    orders = (Order.query.filter_by(company_id=cid, deleted_at=None)
              .filter(Order.status.notin_(["excluido", "cancelado"]))
              .order_by(Order.number).all())
    pos = (PurchaseOrder.query.filter_by(company_id=cid, deleted_at=None)
           .filter(PurchaseOrder.status.notin_(["excluido", "cancelado"]))
           .order_by(PurchaseOrder.number).all())
    return categories, centers, suppliers, orders, pos


def _apply_expense_form(r, form, *, edit: bool = False):
    """Valida e aplica o formulário na FinancialRecord de despesa.

    Regras: categoria obrigatória com type='expense'; centro de custo
    obrigatório; ambos da MESMA company; fornecedor/SO/PO opcionais (da
    mesma company); emissão e vencimento obrigatórios; valor > 0.
    """
    cid = current_user.company_id

    def _cid_int(field):
        raw = (form.get(field) or "").strip()
        return int(raw) if raw.isdigit() else None

    cat_id = _cid_int("financial_category_id")
    cc_id  = _cid_int("cost_center_id")
    sup_id = _cid_int("supplier_id")
    o_id   = _cid_int("order_id")
    po_id  = _cid_int("purchase_order_id")

    if cat_id is None:
        raise ValueError("Categoria é obrigatória")
    cat = (FinancialCategory.query
           .filter_by(id=cat_id, company_id=cid).first())
    if cat is None or cat.type != "expense":
        raise ValueError("A categoria deve ser do tipo Despesa (expense) da sua empresa")

    if cc_id is None:
        raise ValueError("Centro de custo é obrigatório")
    if CostCenter.query.filter_by(id=cc_id, company_id=cid).first() is None:
        raise ValueError("Centro de custo inválido (outra empresa)")

    if sup_id is not None:
        from ...models.supplier import Supplier
        if Supplier.query.filter_by(id=sup_id, company_id=cid, deleted_at=None).first() is None:
            raise ValueError("Fornecedor inválido (outra empresa)")

    def _optional_doc(model, doc_id, label):
        if doc_id is None:
            return None
        obj = (model.query.filter_by(id=doc_id, company_id=cid, deleted_at=None)
               .filter(model.status.notin_(["excluido", "cancelado"])).first())
        if obj is None:
            raise ValueError(f"{label} inválido (outra empresa ou excluído)")
        return doc_id

    from ...models.order import Order
    from ...models.purchase_order import PurchaseOrder
    o_id  = _optional_doc(Order, o_id, "SO")
    po_id = _optional_doc(PurchaseOrder, po_id, "PO")

    name = (form.get("description", "") or "").strip()
    if not name:
        raise ValueError("Descrição é obrigatória")
    try:
        amount = parse_brl(form.get("amount", ""))
    except ValueError:
        raise ValueError("Valor inválido")
    if amount <= 0:
        raise ValueError("Valor deve ser maior que zero")

    emission = None
    if form.get("emission_date"):
        try:
            emission = date.fromisoformat(form["emission_date"])
        except ValueError:
            raise ValueError("Data de emissão inválida")
    if emission is None:
        raise ValueError("Data de emissão é obrigatória")

    due = None
    if form.get("due_date"):
        try:
            due = date.fromisoformat(form["due_date"])
        except ValueError:
            raise ValueError("Data de vencimento inválida")
    if due is None:
        raise ValueError("Vencimento é obrigatório")

    r.description           = name
    r.amount                = amount
    r.financial_category_id = cat_id
    r.cost_center_id        = cc_id
    r.supplier_id           = sup_id
    r.order_id              = o_id
    r.purchase_order_id     = po_id
    r.emission_date         = emission
    r.due_date              = due
    r.notes                 = (form.get("notes", "") or "").strip() or None
    if not edit:
        r.type    = "expense"
        r.category = "outro"   # classificação legada; o vínculo real é financial_category_id
        r.status  = "pendente"


@financial_bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def new_expense():
    categories, centers, suppliers, orders, pos = _expense_form_context()
    if request.method == "POST":
        try:
            r = FinancialRecord(company_id=current_user.company_id)
            _apply_expense_form(r, request.form)
            db.session.add(r)
            db.session.flush()
            r.reference = f"expense:{r.id}"   # convenção única de despesa
            log_activity("financial", r.id, current_user.company_id,
                         f"Despesa '{r.description}' R$ {r.amount:.2f} criada", current_user.id)
            db.session.commit()
            flash("Despesa criada.", "success")
            return redirect(url_for("financial.expenses"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/expense_form.html", r=None,
                           categories=categories, centers=centers,
                           suppliers=suppliers, orders=orders, pos=pos)


@financial_bp.route("/expenses/<int:eid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("financial.manage")
def edit_expense(eid):
    r = _expense_base_query().filter(FinancialRecord.id == eid).first_or_404()
    if r.status == "pago":
        flash("Despesa paga não pode ser editada livremente (valor/categoria/centro/"
              "datas de pagamento). Use estorno/ajuste futuro se necessário.", "warning")
        return redirect(url_for("financial.expenses"))
    categories, centers, suppliers, orders, pos = _expense_form_context()
    if request.method == "POST":
        try:
            _apply_expense_form(r, request.form, edit=True)
            log_activity("financial", r.id, current_user.company_id,
                         "Despesa editada", current_user.id)
            db.session.commit()
            flash("Despesa atualizada.", "success")
            return redirect(url_for("financial.expenses"))
        except ValueError as e:
            db.session.rollback()
            flash(f"Erro: {e}", "danger")
    return render_template("financial/expense_form.html", r=r,
                           categories=categories, centers=centers,
                           suppliers=suppliers, orders=orders, pos=pos)


@financial_bp.route("/expenses/<int:eid>/cancel", methods=["POST"])
@login_required
@require_permission("financial.manage")
def cancel_expense(eid):
    r = _expense_base_query().filter(FinancialRecord.id == eid).first_or_404()
    if r.status == "pago":
        flash("Despesa paga não pode ser cancelada — o histórico financeiro é preservado.", "danger")
        return redirect(url_for("financial.expenses"))
    r.status = "cancelado"
    log_activity("financial", r.id, current_user.company_id,
                 "Despesa cancelada", current_user.id)
    db.session.commit()
    flash("Despesa cancelada.", "success")
    return redirect(url_for("financial.expenses"))


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 4 — Fluxo de Caixa REALIZADO (fonte oficial: FinancialRecord)
# Tela SOMENTE LEITURA: nenhuma rota de mutação aqui.
# ─────────────────────────────────────────────────────────────────────────────

_CASH_PERIOD_LABELS = {
    "today":        "Hoje",
    "this_week":    "Esta semana",
    "this_month":   "Este mês",
    "last_month":   "Mês anterior",
    "custom":       "Personalizado...",
}


@financial_bp.route("/cash-flow")
@login_required
def cash_flow():
    from ...services.cash_flow_service import (
        realized_entries, split_movements, movement_info, pending_forecast,
    )
    cid   = current_user.company_id
    today = now_br().date()
    period = request.args.get("period", "this_month")

    if period == "this_week":
        # Segunda-feira da semana atual até domingo
        first = today - timedelta(days=today.weekday())
        last  = first + timedelta(days=6)
    else:
        first, last = _financial_period_bounds(
            period, request.args.get("date_from"), request.args.get("date_to"), today)

    entries = realized_entries(cid, first, last)
    inflows, outflows = split_movements(entries)

    total_in = round(sum(float(e.amount or 0) for e in inflows), 2)
    total_out = round(sum(float(e.amount or 0) for e in outflows), 2)
    period_balance = round(total_in - total_out, 2)

    # Saldo inicial: NÃO inventado. Sem configuração, saldo final = resultado
    # líquido do período (rotulado como tal, nunca como saldo bancário real).
    initial_configured = False
    initial_balance = 0.0
    final_balance = round(initial_balance + period_balance, 2)

    # Previsto (informativo, separado do realizado)
    to_receive, to_pay = pending_forecast(cid)

    # Monta linhas com detalhes resolvidos
    def _rows(entries_list):
        rows = []
        for e in entries_list:
            info = movement_info(e)
            rows.append({
                "entry": e,
                **info,
            })
        return rows

    inflow_rows = _rows(inflows)
    # Saídas agrupadas pela categoria-raiz (Custos Diretos, Despesas Operacionais, ...)
    outflow_groups = {}
    for row in _rows(outflows):
        outflow_groups.setdefault(row["group"], []).append(row)

    return render_template(
        "financial/cash_flow.html",
        period=period,
        date_from=request.args.get("date_from", ""),
        date_to=request.args.get("date_to", ""),
        p_start=first, p_end=last,
        period_labels=_CASH_PERIOD_LABELS,
        total_in=total_in, total_out=total_out,
        period_balance=period_balance,
        initial_configured=initial_configured, initial_balance=initial_balance,
        final_balance=final_balance,
        to_receive=to_receive, to_pay=to_pay,
        inflow_rows=inflow_rows, outflow_groups=outflow_groups,
        today=today,
    )
