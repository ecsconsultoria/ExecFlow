"""Purchase Orders blueprint routes."""
import json
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, selectinload, lazyload
from . import purchase_orders_bp
from ...models.purchase_order import PurchaseOrder, POPayment, POItem, PO_STATUSES
from ...models.supplier import Supplier
from ...models.service import Service, ServicePricing
from ...models.vehicle import VehicleCategory
from ...models.service_order import ServiceOrder
from ...models.order import Order, OrderItem
from ...extensions import db
from ...services import purchase_order_service as pos
from ...services import margin_service
from ...utils.audit import log_activity
from ...utils.decorators import require_permission
from ...utils.helpers import parse_brl


def _void_po_financial_records(po):
    """Soft-delete todos os FinancialRecords vinculados às parcelas da PO."""
    from ...services.financial_service import void_payment_financial_records
    void_payment_financial_records(po.payments, "po_payment")



@purchase_orders_bp.route("/")
@login_required
@require_permission("po.view")
def index():
    cid    = current_user.company_id
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    # IMPORTANT: PurchaseOrder model declares many relationships as lazy="joined"
    # (creator, supplier, service, service_order, order, vehicle_category). When
    # cascaded through Order/ServiceOrder (which also have many lazy="joined"
    # users), a plain .all() generates a 15+ JOIN query that is catastrophically
    # slow on SQLite+OneDrive. We neutralize those defaults with lazyload('*')
    # and only eager-load what the template actually uses.
    query  = (PurchaseOrder.query
              .options(
                  lazyload('*'),
                  joinedload(PurchaseOrder.supplier).lazyload('*'),
                  joinedload(PurchaseOrder.order).lazyload('*'),
                  selectinload(PurchaseOrder.items),
              )
              .filter_by(company_id=cid)
              .filter(PurchaseOrder.deleted_at.is_(None)))
    if status:
        query = query.filter_by(status=status)
    else:
        # Exclui rascunhos não salvos e POs excluídas da listagem padrão
        query = query.filter(PurchaseOrder.status.notin_(["excluido", "rascunho"]))
    if q:
        query = query.filter(
            PurchaseOrder.number.ilike(f"%{q}%") |
            PurchaseOrder.passenger_name.ilike(f"%{q}%")
        )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(
        PurchaseOrder.pickup_datetime.asc().nullsfirst(),
        PurchaseOrder.id.desc()
    ).paginate(page=page, per_page=25, error_out=False)
    po_list = pagination.items
    return render_template("purchase_orders/index.html",
                           po_list=po_list, pagination=pagination,
                           status=status, q=q,
                           PO_STATUSES=PO_STATUSES)


# ─── Context helper ─────────────────────────────────────────────────────────

def _build_context(cid):
    """Returns (suppliers, services, categories, suppliers_json, services_json)."""
    suppliers  = Supplier.query.filter_by(company_id=cid, deleted_at=None, is_active=True).order_by(Supplier.name).all()
    services   = Service.query.filter_by(is_active=True).order_by(Service.name).all()
    categories = VehicleCategory.query.filter_by(is_active=True).order_by(VehicleCategory.sort_order).all()
    suppliers_json = json.dumps({str(s.id): {
        'contact': s.contact or '', 'email': s.email or '',
        'phone': s.phone or '', 'document': s.document or '',
    } for s in suppliers})
    services_json = json.dumps({str(sv.id): {
        'requires_vehicle': getattr(sv, 'requires_vehicle', False),
        'requires_route':   getattr(sv, 'requires_route',   False),
        'requires_passenger': getattr(sv, 'requires_passenger', False),
    } for sv in services})
    return suppliers, services, categories, suppliers_json, services_json


# ─── New — exibe formulário de criação de PO ────────────────────────────────

@purchase_orders_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("po.create")
def new():
    cid = current_user.company_id

    if request.method == "POST":
        data = request.form.to_dict()

        # Parse pickup_datetime from separate date+time fields
        pd = data.pop("pickup_date", "")
        pt = data.pop("pickup_time", "")
        if pd:
            data["pickup_datetime"] = f"{pd}T{pt}" if pt else f"{pd}T00:00"

        # Numeric conversions
        if data.get("amount"):
            data["amount"] = parse_brl(data["amount"])
        if data.get("pax_count"):
            try:
                data["pax_count"] = int(data["pax_count"])
            except ValueError:
                data["pax_count"] = 1

        po = pos.create(cid, data, current_user.id)
        log_activity("po", po.id, po.company_id, "Criada", current_user.id)
        if po.order_id and po.order:
            margin_service.recalculate_order(po.order)
        db.session.commit()
        flash(f"PO {po.number} criada com sucesso.", "success")
        return redirect(url_for("purchase_orders.detail", po_id=po.id))

    # GET — se order_id, auto-cria PO vinculada ao SO e redireciona para detail
    order_id = request.args.get("order_id", type=int)
    if order_id:
        linked_order = Order.query.filter_by(id=order_id, company_id=cid).first_or_404()
        po = pos.create_from_order(linked_order, current_user.id)
        log_activity("po", po.id, po.company_id, "Criada a partir de SO", current_user.id)
        margin_service.recalculate_order(linked_order)
        db.session.commit()
        flash(f"PO {po.number} criada a partir do pedido {linked_order.number}.", "success")
        return redirect(url_for("purchase_orders.detail", po_id=po.id))
    linked_order = None
    suppliers, services, categories, suppliers_json, services_json = _build_context(cid)
    return render_template("purchase_orders/detail.html",
                           po=None,
                           linked_order=linked_order,
                           suppliers=suppliers, services=services, categories=categories,
                           suppliers_json=suppliers_json, services_json=services_json,
                           PO_STATUSES=PO_STATUSES,
                           audit_logs=[])


# ─── PDF ─────────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/pdf")
@login_required
@require_permission("po.view")
def pdf(po_id):
    import gc
    from ...services.purchase_order_pdf import generate_po_pdf
    # Neutraliza lazy="joined" em cascata (6 relacionamentos) que estouram memoria.
    # NOTE: PurchaseOrder.payments e lazy="dynamic" — nao pode usar selectinload nele.
    po   = (PurchaseOrder.query
            .options(
                lazyload('*'),
                joinedload(PurchaseOrder.company).lazyload('*'),
                joinedload(PurchaseOrder.supplier).lazyload('*'),
                joinedload(PurchaseOrder.order).lazyload('*'),
                joinedload(PurchaseOrder.service_order).lazyload('*'),
                selectinload(PurchaseOrder.items),
            )
            .filter_by(id=po_id, company_id=current_user.company_id)
            .first_or_404())
    lang = request.args.get("lang", "pt")
    buf  = generate_po_pdf(po, lang=lang)
    buf.seek(0)
    gc.collect()
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"{po.number}.pdf",
                     as_attachment=False)


# ─── Detail ──────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>")
@login_required
@require_permission("po.view")
def detail(po_id):
    from ...models.audit import AuditLog
    # Neutraliza varios lazy="joined" do PurchaseOrder (6 relacionamentos)
    # que cascateiam Order/ServiceOrder/users — estoura memoria no Render 512MB.
    po  = (PurchaseOrder.query
           .options(
               lazyload('*'),
               joinedload(PurchaseOrder.supplier).lazyload('*'),
               joinedload(PurchaseOrder.order).lazyload('*'),
               selectinload(PurchaseOrder.items),
           )
           .filter_by(id=po_id, company_id=current_user.company_id)
           .first_or_404())
    cid = current_user.company_id
    suppliers, services, categories, suppliers_json, services_json = _build_context(cid)
    audit_logs = AuditLog.query.filter_by(entity="po", entity_id=po.id).order_by(AuditLog.created_at.asc()).all()
    return render_template("purchase_orders/detail.html",
                           po=po,
                           suppliers=suppliers, services=services, categories=categories,
                           suppliers_json=suppliers_json, services_json=services_json,
                           linked_order=po.order,
                           PO_STATUSES=PO_STATUSES,
                           audit_logs=audit_logs)


# ─── Save All ────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/save", methods=["POST"])
@login_required
@require_permission("po.edit")
def save_all(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    if po.status in ("concluido", "faturado", "cancelado"):
        flash("PO não pode ser editada no status atual.", "warning")
        return redirect(url_for("purchase_orders.detail", po_id=po_id))
    try:
        data = request.form.to_dict()
        data.pop("order_id", None)   # never change linked order via save
        pd = data.pop("pickup_date", "")
        pt = data.pop("pickup_time", "")
        if pd:
            data["pickup_datetime"] = f"{pd}T{pt}" if pt else f"{pd}T00:00"

        # Normalize numeric fields coming from the form (empty -> 0.0 / 1)
        for f in ("amount", "discount_value", "freight_amount", "other_costs_amount"):
            raw = data.get(f, None)
            if raw in (None, ""):
                data[f] = 0.0
                continue
            if isinstance(raw, (int, float)):
                data[f] = float(raw)
                continue
            try:
                data[f] = parse_brl(raw)
            except (ValueError, TypeError):
                data[f] = 0.0

        raw_pax = data.get("pax_count", None)
        if raw_pax in (None, ""):
            data["pax_count"] = 1
        else:
            try:
                data["pax_count"] = int(raw_pax)
            except ValueError:
                data["pax_count"] = 1

        data["discount_type"] = (data.get("discount_type") or "R$")

        # Emissão editável → atualiza created_at
        emission_raw = data.pop("emission_date", "")
        if emission_raw:
            from datetime import datetime
            try:
                dt = datetime.strptime(str(emission_raw).strip(), "%Y-%m-%d")
                po.created_at = dt.replace(
                    hour=po.created_at.hour if po.created_at else 0,
                    minute=po.created_at.minute if po.created_at else 0,
                )
            except ValueError:
                pass

        pos._apply_data(po, data)
        log_activity("po", po.id, po.company_id, "Dados salvos", current_user.id)
        if po.order_id and po.order:
            margin_service.recalculate_order(po.order)
        db.session.commit()
        flash("PO salva.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar PO: {e}", "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Ajustes financeiros ─────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/update-adjustments", methods=["POST"])
@login_required
@require_permission("po.edit")
def update_adjustments(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    d = request.form.to_dict()

    def _pf(v):
        try:
            return float(str(v or 0).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    po.discount_type      = d.get("discount_type", "R$") or "R$"
    po.discount_value     = _pf(d.get("discount_value"))
    po.freight_amount     = _pf(d.get("freight_amount"))
    po.other_costs_amount = _pf(d.get("other_costs_amount"))
    po.other_costs_label  = d.get("other_costs_label", "") or ""
    log_activity("po", po.id, po.company_id, "Ajustes financeiros atualizados", current_user.id)
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    db.session.commit()
    flash("Ajustes financeiros salvos.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Edit (redirect to unified detail page) ─────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("po.edit")
def edit(po_id):
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Transições de status ────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/open", methods=["POST"])
@login_required
@require_permission("po.edit")
def open_po(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    # Salva supplier_id se o usuário selecionou no form antes de clicar Abrir
    sid = request.form.get("supplier_id", type=int)
    if sid:
        po.supplier_id = sid
    try:
        pos.open_po(po, current_user.id)
        log_activity("po", po.id, po.company_id, "PO aberta", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} aberta com sucesso.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/send", methods=["POST"])
@login_required
@require_permission("po.edit")
def send(po_id):
    """Compat backward para links/ações antigas."""
    return open_po(po_id)


@purchase_orders_bp.route("/<int:po_id>/approve", methods=["POST"])
@login_required
@require_permission("po.edit")
def approve(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.approve(po, current_user.id)
        log_activity("po", po.id, po.company_id, "Aprovada", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} aprovada.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/start", methods=["POST"])
@login_required
@require_permission("po.edit")
def start_execution(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.start_execution(po, current_user.id)
        log_activity("po", po.id, po.company_id, "Em execução", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} em execução.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/conclude", methods=["POST"])
@login_required
@require_permission("po.close")
def conclude(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.conclude(po, current_user.id)
        log_activity("po", po.id, po.company_id, "Concluída", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} concluída.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/faturar", methods=["POST"])
@login_required
@require_permission("financial.manage")
def faturar(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    # Salva supplier_id se enviado pelo form (usuário selecionou mas não salvou antes)
    sid = request.form.get("supplier_id", type=int)
    if sid and not po.supplier_id:
        po.supplier_id = sid
    try:
        pos.faturar(po, current_user.id)
        log_activity("po", po.id, po.company_id, "Faturada", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} faturada com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/cancel", methods=["POST"])
@login_required
@require_permission("po.cancel")
def cancel(po_id):
    po     = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    reason = request.form.get("reason", "")
    try:
        pos.cancel(po, current_user.id, reason)
        _void_po_financial_records(po)
        log_activity("po", po.id, po.company_id, "Cancelada", current_user.id)
        db.session.commit()
        flash(f"PO {po.number} cancelada.", "info")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Pagamentos / Parcelas ────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/generate-payments", methods=["POST"])
@login_required
@require_permission("po.edit")
def generate_payments(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    pm = request.form.get("payment_method", "").strip()
    pt = request.form.get("payment_terms", "").strip()
    if pm:
        po.payment_method = pm
    if pt:
        po.payment_terms = pt
    supplier_id = request.form.get("supplier_id", type=int)
    if supplier_id:
        po.supplier_id = supplier_id
    db.session.flush()
    custom_total = None
    raw_custom = request.form.get("custom_amount", "").strip()
    if raw_custom:
        custom_total = parse_brl(raw_custom)
    pmts = pos.generate_payments(po, custom_total=custom_total)
    log_activity("po", po.id, po.company_id, "Parcelas geradas", current_user.id)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        total_scheduled = sum(p.amount or 0 for p in po.payments)
        a_pagar = max(po.computed_total - total_scheduled, 0)
        return jsonify({
            "ok": True,
            "installments": [{
                "id":       p.id,
                "no":       p.installment_no,
                "due_date": p.due_date.isoformat() if p.due_date else "",
                "amount":   float(p.amount or 0),
                "notes":    p.notes or "",
            } for p in pmts],
            "a_pagar":     a_pagar,
            "total_count": len(list(po.payments)),
        })
    flash(f"{len(pmts)} parcela(s) gerada(s).", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/recalculate-payments", methods=["POST"])
@login_required
@require_permission("po.edit")
def recalculate_payments(po_id):
    """Apaga parcelas não-pagas e regera com base no total atual."""
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    if po.status in ("concluido", "faturado", "cancelado"):
        flash("PO não pode ser editada no status atual.", "warning")
        return redirect(url_for("purchase_orders.detail", po_id=po_id))
    pmts = pos.generate_payments(po)  # REGENERATE MODE
    log_activity("po", po.id, po.company_id, "Parcelas recalculadas", current_user.id)
    db.session.commit()
    flash(f"Parcelas recalculadas — {len(pmts)} parcela(s) gerada(s).", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/payments/<int:pid>/update", methods=["POST"])
@login_required
@require_permission("po.edit")
def update_payment(pid):
    pmt = POPayment.query.get_or_404(pid)
    po  = pmt.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    pos.update_payment_inline(pmt, request.form.to_dict())
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash("Parcela atualizada.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/payments/<int:pid>/delete", methods=["POST"])
@login_required
@require_permission("po.edit")
def delete_payment(pid):
    pmt = POPayment.query.get_or_404(pid)
    po  = pmt.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    try:
        pos.delete_payment(pmt)
    except ValueError as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": str(e)}), 400
        flash(str(e), "warning")
        return redirect(url_for("purchase_orders.detail", po_id=po.id))
    log_activity("po", po.id, po.company_id, "Parcela removida", current_user.id)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        total_scheduled = sum(p.amount or 0 for p in po.payments)
        a_pagar = max(po.computed_total - total_scheduled, 0)
        return jsonify({"ok": True, "a_pagar": a_pagar, "total_count": len(list(po.payments))})
    flash("Parcela removida.", "info")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/payments/<int:pid>/baixa", methods=["POST"])
@login_required
@require_permission("financial.manage")
def baixa(pid):
    pmt = POPayment.query.get_or_404(pid)
    po  = pmt.purchase_order
    if po.company_id != current_user.company_id:
        flash("Não autorizado.", "warning")
        return redirect(url_for("purchase_orders.index"))
    try:
        raw         = request.form.get("paid_amount", "")
        paid_amount = float(str(raw).replace(",", ".")) if raw else (pmt.amount or 0)
        paid_date_str = request.form.get("paid_date", "")
        from datetime import date as _date_type
        paid_date = _date_type.fromisoformat(paid_date_str) if paid_date_str else None
        pos.baixa(pmt, paid_amount, current_user.id, paid_date=paid_date)
        log_activity("po", po.id, po.company_id, f"Parcela {pmt.installment_no} baixada", current_user.id)
        db.session.commit()
        flash("Pagamento registrado.", "success")
    except Exception as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─── Items da PO ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/items/add", methods=["POST"])
@login_required
@require_permission("po.edit")
def add_item(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    pos.add_item(po, request.form.to_dict())
    log_activity("po", po.id, po.company_id, "Item adicionado", current_user.id)
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        items_data = [{
            "id":          i.id,
            "description": i.description or "",
            "quantity":    i.quantity,
            "unit_cost":   i.unit_cost,
            "total_cost":  i.total_cost,
            "sort_order":  i.sort_order,
        } for i in po.items]
        return jsonify({"ok": True, "items": items_data, "computed_total": po.computed_total})
    flash("Item adicionado.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/items/<int:item_id>/update", methods=["POST"])
@login_required
@require_permission("po.edit")
def update_item(item_id):
    item = POItem.query.get_or_404(item_id)
    po   = item.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    pos.update_item(item, request.form.to_dict())
    log_activity("po", po.id, po.company_id, "Item atualizado", current_user.id)
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "total_cost": item.total_cost, "computed_total": po.computed_total})
    flash("Item atualizado.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/items/<int:item_id>/update-operational", methods=["POST"])
@login_required
@require_permission("po.edit")
def update_item_operational(item_id):
    item = POItem.query.get_or_404(item_id)
    po   = item.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    apply_all = request.form.get("apply_to_all") in ("1", "true", "on")
    pos.update_item_operational(item, request.form.to_dict(), apply_to_all=apply_all)
    log_activity(
        "po", po.id, po.company_id,
        "Dados operacionais do item atualizados (todos)" if apply_all
        else f"Dados operacionais do item #{item.sort_order + 1 if item.sort_order is not None else item.id} atualizados",
        current_user.id,
    )
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash("Dados operacionais salvos.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
@require_permission("po.edit")
def delete_item(item_id):
    item = POItem.query.get_or_404(item_id)
    po   = item.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    pos.delete_item(item)
    log_activity("po", po.id, po.company_id, "Item removido", current_user.id)
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "computed_total": po.computed_total})
    flash("Item removido.", "info")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─── Deletar PO ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/delete", methods=["POST"])
@login_required
@require_permission("po.delete")
def delete(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).filter(
        PurchaseOrder.status != "excluido"
    ).first_or_404()
    po.status = "excluido"
    _void_po_financial_records(po)
    # Recalcula margem do SO vinculado, se houver
    if po.order_id and po.order:
        margin_service.recalculate_order(po.order)
    log_activity("po", po.id, po.company_id, "Excluída", current_user.id)
    db.session.commit()
    flash(f"PO {po.number} excluída.", "info")
    return redirect(url_for("purchase_orders.index"))


# ─── Observações ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/update-obs", methods=["POST"])
@login_required
@require_permission("po.edit")
def update_obs(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    po.notes = request.form.get("notes", "").strip()
    log_activity("po", po.id, po.company_id, "Observações atualizadas", current_user.id)
    db.session.commit()
    flash("Observações salvas.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))
