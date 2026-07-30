"""blueprints/orders/routes.py — Rotas do módulo Pedidos (Orders)."""
from datetime import datetime

from flask import make_response, render_template, request, redirect, url_for, flash, abort, send_file, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import lazyload, joinedload, selectinload

from . import orders_bp
from ...models.order          import Order, OrderItem, OrderPayment, ORDER_STATUSES
from ...models.quote          import Quote
from ...models.service_order  import ServiceOrder
from ...models.purchase_order import PurchaseOrder
from ...models.service        import Service
from ...models.vehicle        import VehicleCategory
from ...models.company        import Company
from ...extensions            import db
from ...services              import order_service
from ...services              import service_order_service as sos
from ...services              import purchase_order_service as pos
from ...utils                 import now_br
from ...utils.export          import csv_response
from ...utils.helpers         import parse_brl
from ...utils.audit           import log_activity
from ...utils.decorators      import require_permission


def _void_order_financial_records(order):
    """Soft-delete todos os FinancialRecords vinculados às parcelas do SO."""
    from ...services.financial_service import void_payment_financial_records
    void_payment_financial_records(order.payments, "order_payment")


def _void_linked_po_financial_records(order):
    """Soft-delete FinancialRecords das parcelas de todas as POs vinculadas ao SO."""
    from ...services.financial_service import void_payment_financial_records
    for po in order.purchase_orders:
        void_payment_financial_records(po.payments, "po_payment")


# ─────────────────────────────────────────────────────────────────────────────
# Lista
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/")
@login_required
@require_permission("so.view")
def index():
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    # Order declares 6 users (creator/opener/invoicer/closer/canceller/reopener)
    # plus quote as lazy="joined". Cascaded with Quote's joineds this generates
    # 10+ JOINs per row. Neutralize defaults and eager-load only `quote` (used
    # in template), with its own joineds disabled.
    query  = (Order.query
              .options(
                  lazyload('*'),
                  joinedload(Order.quote).lazyload('*'),
              )
              .filter_by(company_id=current_user.company_id, deleted_at=None))
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Order.status != "excluido")
    if q:
        query = query.filter(
            Order.client_name.ilike(f"%{q}%") | Order.number.ilike(f"%{q}%")
        )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    orders = pagination.items
    return render_template("orders/index.html", orders=orders, pagination=pagination,
                           status=status, q=q, ORDER_STATUSES=ORDER_STATUSES)


@orders_bp.route("/export")
@login_required
@require_permission("so.view")
def export_csv():
    """Exporta lista de Sales Orders como CSV (Excel)."""
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    query  = (Order.query
              .options(
                  lazyload('*'),
                  joinedload(Order.quote).lazyload('*'),
              )
              .filter_by(company_id=current_user.company_id, deleted_at=None))
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Order.status != "excluido")
    if q:
        query = query.filter(
            Order.client_name.ilike(f"%{q}%") | Order.number.ilike(f"%{q}%")
        )
    orders = query.order_by(Order.created_at.desc()).all()

    from datetime import date as _date
    headers = ["Nº SO", "Nº RFQ", "Cliente", "Data", "Total", "Status"]
    rows = []
    for o in orders:
        total = o.computed_total if o.computed_total else 0
        rows.append([
            o.number,
            o.quote.number if o.quote else "–",
            o.client_name or "–",
            o.created_at.strftime("%d/%m/%Y") if o.created_at else "–",
            f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            o.status_label,
        ])
    filename = f"sales_orders_{_date.today().isoformat()}.csv"
    return csv_response(filename, headers, rows)


# ─────────────────────────────────────────────────────────────────────────────
# Criação Manual (sem orçamento)
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/new", methods=["GET"])
@login_required
@require_permission("so.create")
def new():
    """Cria um Pedido em branco e redireciona para o detalhe para preenchimento."""
    order = order_service.create_manual(current_user.company_id, current_user.id)
    log_activity("order", order.id, order.company_id, "Criado manualmente", current_user.id)
    db.session.commit()
    flash(f"Pedido {order.number} criado. Preencha os dados abaixo.", "info")
    return redirect(url_for("orders.detail", oid=order.id))


# ─────────────────────────────────────────────────────────────────────────────
# Criação a partir de Orçamento
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/create/<int:qid>", methods=["POST"])
@login_required
@require_permission("so.create")
def create(qid):
    """Cria Pedido a partir de um Orçamento aprovado."""
    quote = Quote.query.filter_by(
        id=qid, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    if quote.status not in ("aprovado", "pago"):
        flash("Orçamento precisa estar aprovado para criar Pedido.", "warning")
        return redirect(url_for("quotes.detail", qid=qid))

    # Evita duplicatas (ignora SOs cancelados ou excluídos)
    existing = Order.query.filter_by(quote_id=qid).filter(
        Order.status.notin_(["cancelado", "excluido"])
    ).first()
    if existing:
        flash(f"Pedido {existing.number} já existe para este orçamento.", "info")
        return redirect(url_for("orders.detail", oid=existing.id))

    order = order_service.create_from_quote(quote, current_user.id)
    log_activity("order", order.id, order.company_id, f"Criado a partir do Orçamento {quote.number}", current_user.id)
    db.session.commit()
    flash(f"Pedido {order.number} criado com sucesso.", "success")
    return redirect(url_for("orders.detail", oid=order.id))


# ─────────────────────────────────────────────────────────────────────────────
# Detalhe
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>")
@login_required
@require_permission("so.view")
def detail(oid):
    # Neutraliza os varios lazy="joined" do Order (6 users + quote cascateado).
    # Sem isso, um unico SELECT vira 15+ JOINs e estoura memoria no Render 512MB.
    order = (Order.query
             .options(lazyload('*'), joinedload(Order.quote).lazyload('*'))
             .filter_by(id=oid, company_id=current_user.company_id, deleted_at=None)
             .first_or_404())

    # OS vinculadas via quote_id (dispatch center)
    linked_os = []
    if order.quote_id:
        linked_os = (
            ServiceOrder.query
            .options(lazyload('*'))
            .filter_by(quote_id=order.quote_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .order_by(ServiceOrder.id.desc())
            .all()
        )

    # POs vinculadas via order_id
    linked_po = (
        PurchaseOrder.query
        .options(lazyload('*'))
        .filter_by(order_id=order.id)
        .filter(PurchaseOrder.deleted_at.is_(None))
        .order_by(PurchaseOrder.id.desc())
        .all()
    )

    # Nome do vendedor (criador do pedido)
    seller_name = "–"
    if order.created_by:
        try:
            from ...models.user import User
            u = User.query.get(order.created_by)
            seller_name = u.name if u else "–"
        except Exception:
            pass

    from sqlalchemy import or_
    from ...models.audit import AuditLog
    from ...models.client import Client
    services   = Service.query.filter(
        or_(Service.company_id == current_user.company_id, Service.company_id.is_(None))
    ).filter_by(is_active=True).order_by(Service.name).all()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.name).all()
    company    = Company.query.get(order.company_id)
    audit_logs = AuditLog.query.filter_by(entity="order", entity_id=order.id).order_by(AuditLog.created_at.asc()).all()
    clients    = Client.query.filter_by(company_id=current_user.company_id, deleted_at=None).order_by(Client.name).all()

    resp = make_response(render_template(
        "orders/detail.html",
        order=order,
        linked_os=linked_os,
        linked_po=linked_po,
        seller_name=seller_name,
        ORDER_STATUSES=ORDER_STATUSES,
        services=services,
        categories=categories,
        company=company,
        audit_logs=audit_logs,
        clients=clients,
    ))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Transições de status
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/open", methods=["POST"])
@login_required
@require_permission("so.edit")
def open_order(oid):
    order = _get_order(oid)
    bt = request.form.get("billing_type", "").strip()
    if bt and bt in ("recibo", "nf", "cartao", "nf_cartao"):
        order.billing_type = bt
    cid = request.form.get("client_id", type=int)
    if cid:
        from ...models.client import Client
        c = Client.query.filter_by(id=cid, company_id=current_user.company_id, deleted_at=None).first()
        if c:
            order.client_id   = c.id
            order.client_name = c.name
            if not order.email and c.email:
                order.email = c.email
            if not order.phone and c.phone:
                order.phone = c.phone
            if not order.celular and c.whatsapp:
                order.celular = c.whatsapp
    try:
        order_service.open_order(order, current_user.id)
        log_activity("order", order.id, order.company_id, "Aberto", current_user.id)
        db.session.commit()
        flash("Pedido aberto.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/faturar", methods=["POST"])
@login_required
@require_permission("so.invoice")
def faturar(oid):
    order = _get_order(oid)
    try:
        order_service.faturar(order, request.form.to_dict(), current_user.id)
        log_activity("order", order.id, order.company_id, "Faturado", current_user.id)
        db.session.commit()
        flash("Pedido faturado.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/fechar", methods=["POST"])
@login_required
@require_permission("so.close")
def fechar(oid):
    order = _get_order(oid)
    try:
        order_service.fechar(order, current_user.id)
        log_activity("order", order.id, order.company_id, "Conclu\u00eddo", current_user.id)
        db.session.commit()
        flash("Pedido conclu\u00eddo.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/cancel", methods=["POST"])
@login_required
@require_permission("so.cancel")
def cancel(oid):
    order = _get_order(oid)
    reason = request.form.get("reason", "")
    try:
        order_service.cancel(order, reason, current_user.id)
        _void_order_financial_records(order)
        # Void FRs das POs cascade-canceladas (o service só marca status, não soft-deleta)
        _void_linked_po_financial_records(order)
        log_activity("order", order.id, order.company_id, "Cancelado", current_user.id)
        db.session.commit()
        flash("Pedido cancelado.", "info")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/reabrir", methods=["POST"])
@login_required
@require_permission("so.reopen")
def reabrir(oid):
    order = _get_order(oid)
    try:
        order_service.reabrir(order, current_user.id)
        log_activity("order", order.id, order.company_id, "Reaberto", current_user.id)
        db.session.commit()
        flash("Pedido reaberto para edição.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


# ─────────────────────────────────────────────────────────────────────────────
# Pagamentos / Parcelas
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/generate-payments", methods=["POST"])
@login_required
@require_permission("so.edit")
def generate_payments(oid):
    order = _get_order(oid)
    if order.status in ("concluido", "cancelado"):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'Pedido bloqueado'}), 403
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    # Atualiza forma/prazo antes de gerar parcelas
    pm = request.form.get("payment_method", "").strip()
    pt = request.form.get("payment_terms", "").strip()
    if pm:
        order.payment_method = pm
    if pt:
        order.payment_terms = pt
    # Preserva campos de data/hora do cabeçalho enviados junto ao form de pagamentos
    header_fields = ("emission_date", "delivery_date", "delivery_time")
    if any(request.form.get(f) for f in header_fields):
        hdata = request.form.to_dict()
        d_date = hdata.pop("delivery_date", "").strip()
        d_time = hdata.pop("delivery_time", "").strip()
        if d_date:
            hdata["delivery_datetime"] = f"{d_date}T{d_time or '00:00'}"
        else:
            hdata.pop("delivery_datetime", None)
        order_service.update_header(order, hdata)
    # Custom total override (campo VALOR)
    custom_total = None
    raw_custom = request.form.get("custom_amount", "").strip()
    if raw_custom:
        custom_total = parse_brl(raw_custom)
    pmts = order_service.generate_payments(order, custom_total=custom_total)
    log_activity("order", order.id, order.company_id, "Parcelas geradas", current_user.id)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        total_scheduled = sum(p.amount or 0 for p in order.payments)
        paid_total = order.total_paid()
        a_pagar = max(float(order.total_pending()), 0.0) if paid_total > 0 else max(order.computed_total - total_scheduled, 0)
        return jsonify({
            'ok': True,
            'installments': [{
                'id':       p.id,
                'no':       p.installment_no,
                'due_date': p.due_date.isoformat() if p.due_date else '',
                'amount':   float(p.amount or 0),
                'notes':    p.notes or '',
            } for p in pmts],
            'a_pagar':     a_pagar,
            'total_count': len(order.payments),
        })
    flash(f"{len(pmts)} parcela(s) gerada(s).", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/recalculate-payments", methods=["POST"])
@login_required
@require_permission("so.edit")
def recalculate_payments(oid):
    """Apaga parcelas não-pagas e regera com base no total atual."""
    order = _get_order(oid)
    if order.status in ("concluido", "cancelado"):
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    pmts = order_service.generate_payments(order)  # REGENERATE MODE
    log_activity("order", order.id, order.company_id, "Parcelas recalculadas", current_user.id)
    db.session.commit()
    flash(f"Parcelas recalculadas — {len(pmts)} parcela(s) gerada(s).", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/payments/add", methods=["POST"])
@login_required
@require_permission("so.edit")
def add_payment(oid):
    order = _get_order(oid)
    try:
        order_service.add_payment(order, request.form.to_dict())
        log_activity("order", order.id, order.company_id, "Parcela adicionada", current_user.id)
        db.session.commit()
        flash("Parcela adicionada.", "success")
    except Exception as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/payments/<int:pid>/delete", methods=["POST"])
@login_required
@require_permission("so.edit")
def delete_payment(pid):
    pmt   = OrderPayment.query.get_or_404(pid)
    order = pmt.order
    _check_company(order)
    if order.status in ("concluido", "faturado", "cancelado"):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'Pedido bloqueado'}), 403
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    try:
        order_service.delete_payment(pmt)
    except ValueError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': str(e)}), 400
        flash(str(e), "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    log_activity("order", order.id, order.company_id, "Parcela removida", current_user.id)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        total_scheduled = sum(p.amount or 0 for p in order.payments)
        paid_total = order.total_paid()
        a_pagar = max(float(order.total_pending()), 0.0) if paid_total > 0 else max(order.computed_total - total_scheduled, 0)
        return jsonify({'ok': True, 'a_pagar': a_pagar, 'total_count': len(order.payments)})
    flash("Parcela removida.", "info")
    return redirect(url_for("orders.detail", oid=order.id))


@orders_bp.route("/payments/<int:pid>/baixa", methods=["POST"])
@login_required
@require_permission("financial.manage")
def baixa(pid):
    pmt   = OrderPayment.query.get_or_404(pid)
    order = pmt.order
    _check_company(order)
    if order.status == "cancelado":
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    try:
        raw         = request.form.get("paid_amount", "")
        paid_amount = float(str(raw).replace(",", ".")) if raw else (pmt.amount or 0)
        paid_date_str = request.form.get("paid_date", "")
        from datetime import date as _date_type
        paid_date = _date_type.fromisoformat(paid_date_str) if paid_date_str else None
        order_service.baixa(pmt, paid_amount, current_user.id, paid_date=paid_date)
        log_activity("order", order.id, order.company_id, f"Parcela {pmt.installment_no} baixada", current_user.id)
        db.session.commit()

        # Se saldo total está zerado e SO está em status permitido, concluir
        if order.total_pending() <= 0 and order.status in ('rascunho', 'novo', 'aberto', 'faturado'):
            order.status = 'concluido'
            log_activity("order", order.id, order.company_id, "SO concluída automaticamente (todas as parcelas pagas)", current_user.id)
            db.session.commit()

        flash("Pagamento registrado.", "success")
    except Exception as e:
        flash(str(e), "warning")
    return redirect(url_for("orders.detail", oid=order.id))


@orders_bp.route("/payments/<int:pid>/estornar", methods=["POST"])
@login_required
@require_permission("so.edit")
def estornar(pid):
    """Estorna um pagamento já registrado, voltando a parcela para pendente."""
    pmt = OrderPayment.query.get_or_404(pid)
    order = pmt.order
    if order.company_id != current_user.company_id:
        flash("Não autorizado.", "warning")
        return redirect(url_for("orders.index"))
    if not pmt.is_paid:
        flash("Esta parcela não possui pagamento para estornar.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    try:
        pmt.paid_amount = 0
        pmt.paid_at = None
        pmt.paid_by = None
        # Reverte status concluido → faturado se necessário
        if order.status == "concluido":
            order.status = "faturado"
            order.closed_at = None
            order.closed_by = None
        # Reverte FinancialRecord vinculado
        from ...models.financial import FinancialRecord
        ref = f"order_payment:{pmt.id}"
        fr = FinancialRecord.query.filter_by(company_id=order.company_id, reference=ref).filter(
            FinancialRecord.deleted_at.is_(None)
        ).first()
        if fr and fr.status == "pago":
            fr.status = "pendente"
            fr.paid_date = None
        log_activity("order", order.id, order.company_id,
                     f"Pagamento parcela {pmt.installment_no} estornado", current_user.id)
        db.session.commit()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": True})
        flash("Pagamento estornado com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": str(e)}), 500
        flash(f"Erro ao estornar: {e}", "danger")
    return redirect(url_for("orders.detail", oid=order.id))


# ─────────────────────────────────────────────────────────────────────────────
# Atualização de campos (cabeçalho / ajustes / parcela inline)
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/update-header", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_header(oid):
    order = _get_order(oid)
    data = request.form.to_dict()
    # Combine delivery_date + delivery_time into delivery_datetime
    d_date = data.pop("delivery_date", "").strip()
    d_time = data.pop("delivery_time", "").strip()
    if d_date:
        data["delivery_datetime"] = f"{d_date}T{d_time or '00:00'}"
    order_service.update_header(order, data)
    log_activity("order", order.id, order.company_id, "Cabeçalho atualizado", current_user.id)
    db.session.commit()
    flash("Cabeçalho atualizado.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/update-adjustments", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_adjustments(oid):
    order = _get_order(oid)
    order_service.update_adjustments(order, request.form.to_dict())
    log_activity("order", order.id, order.company_id, "Ajustes financeiros atualizados", current_user.id)
    db.session.commit()
    flash("Ajustes financeiros salvos.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/<int:oid>/save-all", methods=["POST"])
@login_required
@require_permission("so.edit")
def save_all(oid):
    """Salva cabeçalho + ajustes. Se action='faturar', também fatura o pedido."""
    order  = _get_order(oid)
    if order.status in ("concluido", "faturado", "cancelado"):
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    data   = request.form.to_dict()
    # Combine delivery_date + delivery_time
    d_date = data.pop("delivery_date", "").strip()
    d_time = data.pop("delivery_time", "").strip()
    if d_date:
        data["delivery_datetime"] = f"{d_date}T{d_time or '00:00'}"
    else:
        data.pop("delivery_datetime", None)
    order_service.update_header(order, data)
    # client_id (seleção de cliente cadastrado)
    cid_str = data.get("client_id", "").strip()
    if cid_str:
        try:
            from ...models.client import Client
            c = Client.query.filter_by(id=int(cid_str), company_id=current_user.company_id, deleted_at=None).first()
            if c:
                order.client_id   = c.id
                order.client_name = c.name
        except (ValueError, TypeError):
            pass
    # Contact fields
    for field in ("client_name", "email", "phone", "celular"):
        if field in data:
            setattr(order, field, data[field] or "")
    db.session.commit()
    # Adjustments
    order_service.update_adjustments(order, data)
    # Action
    action = data.get("action", "save")
    if action == "faturar":
        if not order.emission_date:
            flash("Preencha a Data de Emissão antes de faturar.", "warning")
            return redirect(url_for("orders.detail", oid=oid))
        if not list(order.payments):
            flash("Gere as contas a receber antes de faturar.", "warning")
            return redirect(url_for("orders.detail", oid=oid))
        try:
            order_service.faturar(order, data, current_user.id)
            log_activity("order", order.id, order.company_id, "Faturado", current_user.id)
            db.session.commit()
            flash("Pedido salvo e faturado com sucesso.", "success")
        except ValueError as e:
            flash(str(e), "warning")
    else:
        log_activity("order", order.id, order.company_id, "Dados salvos", current_user.id)
        db.session.commit()
        flash("Pedido salvo.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/payments/<int:pid>/update", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_payment(pid):
    pmt   = OrderPayment.query.get_or_404(pid)
    order = pmt.order
    _check_company(order)
    if order.status == "cancelado":
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'Pedido bloqueado'}), 403
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    order_service.update_payment_inline(pmt, request.form.to_dict())
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    flash("Parcela atualizada.", "success")
    return redirect(url_for("orders.detail", oid=order.id))


# ─────────────────────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/pdf/<lang>")
@login_required
@require_permission("so.view")
def pdf(oid, lang):
    import gc
    from ...services.order_pdf import generate_order_pdf
    # Neutraliza lazy="joined" em cascata (6 users + quote) que dispara 15+ JOINs
    # e hidrata MB desnecessarios -> estouro de memoria no Render 512MB.
    order = (Order.query
             .options(
                 lazyload('*'),
                 selectinload(Order.items),
                 selectinload(Order.payments),
             )
             .filter_by(id=oid, company_id=current_user.company_id, deleted_at=None)
             .first_or_404())
    lang  = lang if lang in ("pt", "en") else "pt"
    # selectinload já garante dados frescos; refresh() quebraria o eager load
    import logging
    logger = logging.getLogger("execflow")
    logger.warning(f"PDF {lang}: order={order.id}, items={len(order.items)}, payments={len(order.payments)}")
    for p in order.payments:
        logger.warning(f"  payment {p.installment_no}: amount={p.amount}, paid={p.paid_amount}, is_paid={p.is_paid}")
    buf   = generate_order_pdf(order, lang=lang)
    gc.collect()
    filename = f"{order.number}.pdf"
    resp = make_response(send_file(buf, mimetype="application/pdf",
                           as_attachment=True, download_name=filename))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Itens do pedido
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/items/add", methods=["POST"])
@login_required
@require_permission("so.edit")
def add_item(oid):
    order = _get_order(oid)
    _check_company(order)
    if order.status in ("concluido", "faturado", "cancelado"):
        flash("Não é possível adicionar itens neste status.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    order_service.add_item(order, request.form.to_dict())
    log_activity("order", order.id, order.company_id, "Item adicionado", current_user.id)
    db.session.commit()
    flash("Item adicionado.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/items/<int:iid>/delete", methods=["POST"])
@login_required
@require_permission("so.edit")
def delete_item(iid):
    item = OrderItem.query.get_or_404(iid)
    order = item.order
    _check_company(order)
    if order.status in ("concluido", "faturado", "cancelado"):
        flash("Não é possível remover itens neste status.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    oid = order.id
    order_service.delete_item(item)
    log_activity("order", oid, order.company_id, "Item removido", current_user.id)
    db.session.commit()
    flash("Item removido.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@orders_bp.route("/items/<int:iid>/update", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_item(iid):
    item  = OrderItem.query.get_or_404(iid)
    order = item.order
    _check_company(order)
    if order.status in ("concluido", "faturado", "cancelado"):
        flash("Não é possível editar itens neste status.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))
    order_service.update_item(item, request.form.to_dict())
    log_activity("order", order.id, order.company_id, "Item atualizado", current_user.id)
    db.session.commit()
    flash("Item atualizado.", "success")
    return redirect(url_for("orders.detail", oid=order.id))


@orders_bp.route("/items/<int:iid>/update-operational", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_item_operational(iid):
    item  = OrderItem.query.get_or_404(iid)
    order = item.order
    _check_company(order)
    if order.status in ("cancelado", "excluido"):
        flash("Não é possível editar itens neste status.", "warning")
        return redirect(url_for("orders.detail", oid=order.id))

    apply_to_all = (request.form.get("apply_to_all", "") or "").lower() in ("1", "true", "on", "yes")
    order_service.update_item_operational(item, request.form.to_dict(), apply_to_all=apply_to_all)
    if apply_to_all:
        log_activity("order", order.id, order.company_id, "Dados operacionais aplicados a todos os itens", current_user.id)
        flash("Dados operacionais aplicados em todos os itens.", "success")
    else:
        log_activity("order", order.id, order.company_id, "Dados operacionais de item atualizados", current_user.id)
        flash("Dados operacionais do item salvos.", "success")
    db.session.commit()
    return redirect(url_for("orders.detail", oid=order.id))


@orders_bp.route("/<int:oid>/update-obs", methods=["POST"])
@login_required
@require_permission("so.edit")
def update_obs(oid):
    order = _get_order(oid)
    _check_company(order)
    if order.status in ("cancelado", "excluido"):
        flash("Pedido não pode ser editado no status atual.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    order.obs = request.form.get("obs", "") or ""
    log_activity("order", order.id, order.company_id, "Observação atualizada", current_user.id)
    db.session.commit()
    flash("Observação salva.", "success")
    return redirect(url_for("orders.detail", oid=oid))


# ─────────────────────────────────────────────────────────────────────────────
# Deletar Sales Order
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/delete", methods=["POST"])
@login_required
@require_permission("so.delete")
def delete(oid):
    order = Order.query.filter_by(id=oid, company_id=current_user.company_id).filter(
        Order.status != "excluido"
    ).first_or_404()
    order.status = "excluido"
    # Reverte o orçamento vinculado para "aprovado" para permitir criar novo SO
    if order.quote_id:
        quote = Quote.query.get(order.quote_id)
        if quote and quote.status == "reserva_confirmada":
            quote.status = "aprovado"
    _void_order_financial_records(order)
    # Exclui POs vinculadas e seus lançamentos financeiros
    for po in order.purchase_orders:
        if po.status not in ("excluido", "cancelado"):
            po.status = "excluido"
    _void_linked_po_financial_records(order)
    log_activity("order", order.id, order.company_id, "Excluído", current_user.id)
    db.session.commit()
    flash(f"Pedido {order.number} excluído.", "info")
    return redirect(url_for("orders.index"))


# ─────────────────────────────────────────────────────────────────────────────
# Criar PO a partir do Sales Order
# ─────────────────────────────────────────────────────────────────────────────

@orders_bp.route("/<int:oid>/create-po", methods=["POST"])
@login_required
@require_permission("po.create")
def create_po(oid):
    order = _get_order(oid)
    if order.status not in ("aberto", "faturado"):
        flash("Sales Order precisa estar aberta ou faturada para criar PO.", "warning")
        return redirect(url_for("orders.detail", oid=oid))

    data = request.form.to_dict()
    data["order_id"] = order.id
    if order.quote_id:
        data["quote_id"] = order.quote_id
    # Pré-preenche cliente como passageiro se não informado
    if not data.get("passenger_name") and order.client:
        data["passenger_name"] = order.client.name
    if not data.get("passenger_phone") and order.phone:
        data["passenger_phone"] = order.phone

    po = pos.create(order.company_id, data, current_user.id)
    log_activity("order", order.id, order.company_id, f"PC/PO {po.number} criada", current_user.id)
    db.session.commit()
    flash(f"PO {po.number} criada vinculada ao Sales Order {order.number}.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─────────────────────────────────────────────────────────────────────────────
# Criar OS a partir do Pedido (mantido para uso interno do dispatch)

@orders_bp.route("/<int:oid>/create-os", methods=["POST"])
@login_required
@require_permission("dispatch.edit")
def create_os(oid):
    order = _get_order(oid)
    if order.status not in ("aberto", "faturado"):
        flash("Pedido precisa estar aberto ou faturado para criar OS.", "warning")
        return redirect(url_for("orders.detail", oid=oid))

    # Verifica se já existe OS para este pedido (via quote_id)
    if order.quote_id:
        existing_os = (
            ServiceOrder.query
            .filter_by(quote_id=order.quote_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .first()
        )
        if existing_os:
            flash(f"OS {existing_os.code} já existe para este pedido.", "info")
            return redirect(url_for("orders.detail", oid=oid))

    f         = request.form
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

    # Usa o orçamento associado ao pedido como fonte para a OS
    quote = order.quote
    if not quote:
        flash("Pedido sem orçamento associado — crie a OS manualmente.", "warning")
        return redirect(url_for("orders.detail", oid=oid))

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
    log_activity("order", order.id, order.company_id, f"OS {os_obj.code} criada", current_user.id)
    db.session.commit()
    flash(f"OS {os_obj.code} criada com sucesso.", "success")
    return redirect(url_for("orders.detail", oid=oid))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_order(oid: int) -> Order:
    return Order.query.filter_by(
        id=oid, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()


def _check_company(order: Order) -> None:
    if order.company_id != current_user.company_id:
        abort(403)
