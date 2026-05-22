"""Purchase Orders blueprint routes."""
import json
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from . import purchase_orders_bp
from ...models.purchase_order import PurchaseOrder, POPayment, POItem, PO_STATUSES
from ...models.supplier import Supplier
from ...models.service import Service, ServicePricing
from ...models.vehicle import VehicleCategory
from ...models.service_order import ServiceOrder
from ...models.order import Order, OrderItem
from ...extensions import db
from ...services import purchase_order_service as pos


# ─── List ────────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/")
@login_required
def index():
    cid    = current_user.company_id
    status = request.args.get("status", "")
    q      = request.args.get("q", "")
    query  = (PurchaseOrder.query
              .filter_by(company_id=cid)
              .filter(PurchaseOrder.deleted_at.is_(None)))
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(
            PurchaseOrder.number.ilike(f"%{q}%") |
            PurchaseOrder.passenger_name.ilike(f"%{q}%")
        )
    po_list = query.order_by(
        PurchaseOrder.pickup_datetime.asc().nullsfirst(),
        PurchaseOrder.id.desc()
    ).all()
    return render_template("purchase_orders/index.html",
                           po_list=po_list, status=status, q=q,
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


# ─── New — auto-cria PO e redireciona para edição ────────────────────────────

@purchase_orders_bp.route("/new", methods=["GET"])
@login_required
def new():
    cid = current_user.company_id
    order_id = request.args.get("order_id", type=int)
    linked_order = (Order.query.filter_by(id=order_id, company_id=cid).first()
                    if order_id else None)

    # Se há SO vinculada com itens, cria uma PO por item usando price_cost
    if linked_order and linked_order.items:
        created_pos = []
        for sort_idx, item in enumerate(linked_order.items):
            # Busca o preço de custo para o serviço+categoria do item
            unit_cost = 0.0
            if item.service_id and item.category_id:
                pricing = ServicePricing.query.filter_by(
                    service_id=item.service_id,
                    category_id=item.category_id,
                ).filter(ServicePricing.is_active == True).first()
                if pricing:
                    unit_cost = pricing.price_cost or 0.0

            qty   = item.quantity or 1
            total = unit_cost * qty

            data = {
                "order_id": linked_order.id,
                # copy operational defaults from SO if present
                "passenger_name":    getattr(linked_order, "passenger_name", None) or "",
                "passenger_phone":   getattr(linked_order, "passenger_phone", None) or "",
                "pickup_datetime":   getattr(linked_order, "pickup_datetime", None),
                "pickup_location":   getattr(linked_order, "pickup_location",  None) or "",
                "dropoff_location":  getattr(linked_order, "dropoff_location", None) or "",
                "flight_number":     getattr(linked_order, "flight_number",    None) or "",
                "pax_count":         qty,
            }
            po = pos.create(cid, data, current_user.id)

            # Descrição do item: nome do serviço se não tiver descrição explícita
            svc = db.session.get(Service, item.service_id) if item.service_id else None
            desc = getattr(item, "description", None) or (svc.name if svc else "")
            po_item = POItem(
                po_id       = po.id,
                service_id  = item.service_id,
                category_id = item.category_id,
                description = desc,
                quantity    = qty,
                unit_cost   = unit_cost,
                total_cost  = total,
                sort_order  = sort_idx,
            )
            db.session.add(po_item)
            created_pos.append(po)

        db.session.commit()

        if len(created_pos) == 1:
            return redirect(url_for("purchase_orders.detail", po_id=created_pos[0].id))
        # Múltiplos → lista de POs
        flash(f"{len(created_pos)} PO(s) criada(s) a partir dos itens do SO.", "success")
        return redirect(url_for("purchase_orders.index"))

    # Sem itens → PO em branco
    data = {"order_id": linked_order.id} if linked_order else {}
    po = pos.create(cid, data, current_user.id)
    db.session.commit()
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─── PDF ─────────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/pdf")
@login_required
def pdf(po_id):
    from ...services.purchase_order_pdf import generate_po_pdf
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    buf = generate_po_pdf(po)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"{po.number}.pdf",
                     as_attachment=False)


# ─── Detail ──────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>")
@login_required
def detail(po_id):
    po  = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    cid = current_user.company_id
    suppliers, services, categories, suppliers_json, services_json = _build_context(cid)
    return render_template("purchase_orders/detail.html",
                           po=po,
                           suppliers=suppliers, services=services, categories=categories,
                           suppliers_json=suppliers_json, services_json=services_json,
                           linked_order=po.order,
                           PO_STATUSES=PO_STATUSES)


# ─── Save All ────────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/save", methods=["POST"])
@login_required
def save_all(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    if po.status in ("concluido", "cancelado"):
        flash("PO não pode ser editada no status atual.", "warning")
        return redirect(url_for("purchase_orders.detail", po_id=po_id))
    data = request.form.to_dict()
    data.pop("order_id", None)   # never change linked order via save
    pd = data.pop("pickup_date", "")
    pt = data.pop("pickup_time", "")
    if pd:
        data["pickup_datetime"] = f"{pd}T{pt}" if pt else f"{pd}T00:00"
    if data.get("amount"):
        try:
            data["amount"] = float(data["amount"].replace(".", "").replace(",", "."))
        except ValueError:
            data["amount"] = 0.0
    if data.get("pax_count"):
        try:
            data["pax_count"] = int(data["pax_count"])
        except ValueError:
            data["pax_count"] = 1
    pos._apply_data(po, data)
    db.session.commit()
    flash("PO salva.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Edit (redirect to unified detail page) ─────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/edit", methods=["GET", "POST"])
@login_required
def edit(po_id):
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Transições de status ────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/send", methods=["POST"])
@login_required
def send(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.send(po, current_user.id)
        db.session.commit()
        flash(f"PO {po.number} marcada como enviada.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/approve", methods=["POST"])
@login_required
def approve(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.approve(po, current_user.id)
        db.session.commit()
        flash(f"PO {po.number} aprovada.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/start", methods=["POST"])
@login_required
def start_execution(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.start_execution(po, current_user.id)
        db.session.commit()
        flash(f"PO {po.number} em execução.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/conclude", methods=["POST"])
@login_required
def conclude(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    try:
        pos.conclude(po, current_user.id)
        db.session.commit()
        flash(f"PO {po.number} concluída.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


@purchase_orders_bp.route("/<int:po_id>/cancel", methods=["POST"])
@login_required
def cancel(po_id):
    po     = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    reason = request.form.get("reason", "")
    try:
        pos.cancel(po, current_user.id, reason)
        db.session.commit()
        flash(f"PO {po.number} cancelada.", "info")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))


# ─── Pagamentos / Parcelas ────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/generate-payments", methods=["POST"])
@login_required
def generate_payments(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    pm = request.form.get("payment_method", "").strip()
    pt = request.form.get("payment_terms", "").strip()
    if pm:
        po.payment_method = pm
    if pt:
        po.payment_terms = pt
    db.session.flush()
    custom_total = None
    raw_custom = request.form.get("custom_amount", "").strip()
    if raw_custom:
        try:
            custom_total = float(raw_custom.replace(".", "").replace(",", "."))
        except ValueError:
            pass
    pmts = pos.generate_payments(po, custom_total=custom_total)
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


@purchase_orders_bp.route("/payments/<int:pid>/update", methods=["POST"])
@login_required
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
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        total_scheduled = sum(p.amount or 0 for p in po.payments)
        a_pagar = max(po.computed_total - total_scheduled, 0)
        return jsonify({"ok": True, "a_pagar": a_pagar, "total_count": len(list(po.payments))})
    flash("Parcela removida.", "info")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/payments/<int:pid>/baixa", methods=["POST"])
@login_required
def baixa(pid):
    pmt = POPayment.query.get_or_404(pid)
    po  = pmt.purchase_order
    if po.company_id != current_user.company_id:
        flash("Não autorizado.", "warning")
        return redirect(url_for("purchase_orders.index"))
    try:
        raw         = request.form.get("paid_amount", "")
        paid_amount = float(str(raw).replace(",", ".")) if raw else (pmt.amount or 0)
        pos.baixa(pmt, paid_amount, current_user.id)
        flash("Pagamento registrado.", "success")
    except Exception as e:
        flash(str(e), "warning")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─── Items da PO ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/items/add", methods=["POST"])
@login_required
def add_item(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    pos.add_item(po, request.form.to_dict())
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
def update_item(item_id):
    item = POItem.query.get_or_404(item_id)
    po   = item.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    pos.update_item(item, request.form.to_dict())
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "total_cost": item.total_cost, "computed_total": po.computed_total})
    flash("Item atualizado.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


@purchase_orders_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = POItem.query.get_or_404(item_id)
    po   = item.purchase_order
    if po.company_id != current_user.company_id:
        return jsonify({"ok": False, "error": "Não autorizado"}), 403
    pos.delete_item(item)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "computed_total": po.computed_total})
    flash("Item removido.", "info")
    return redirect(url_for("purchase_orders.detail", po_id=po.id))


# ─── Deletar PO ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/delete", methods=["POST"])
@login_required
def delete(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id, deleted_at=None).first_or_404()
    po.soft_delete()
    db.session.commit()
    flash(f"PO {po.number} excluída.", "info")
    return redirect(url_for("purchase_orders.index"))


# ─── Observações ─────────────────────────────────────────────────────────────

@purchase_orders_bp.route("/<int:po_id>/update-obs", methods=["POST"])
@login_required
def update_obs(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, company_id=current_user.company_id).first_or_404()
    po.notes = request.form.get("notes", "").strip()
    db.session.commit()
    flash("Observações salvas.", "success")
    return redirect(url_for("purchase_orders.detail", po_id=po_id))
