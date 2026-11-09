"""Agenda pública da PO — link tokenizado SEM preços, com dados operacionais.

Renderiza o MESMO template da agenda do SO (public_so/agenda.html) com o
contexto da PO: itens op_* com fallback nos campos globais da PO.
Inclui o check-in do motorista (status da viagem + revert) via POST.
"""
import hmac

from flask import abort, make_response, redirect, render_template, request, url_for

from . import public_po_bp
from ...extensions import csrf
from ...models.purchase_order import POItem, PurchaseOrder
from ...services import checkin_service
from ...services.po_agenda import build_agenda_context, po_token


def _get_po_item(po_id: int, token: str) -> POItem:
    po = PurchaseOrder.query.filter_by(id=po_id, deleted_at=None).first()
    if po is None:
        abort(404)
    if not hmac.compare_digest(token, po_token(po.id)):
        abort(404)
    item = POItem.query.filter_by(
        id=request.form.get("item_id", type=int), po_id=po_id).first()
    if item is None:
        abort(404)
    return item


@public_po_bp.route("/<int:po_id>/<token>")
def agenda(po_id, token):
    po = PurchaseOrder.query.filter_by(id=po_id, deleted_at=None).first()
    if po is None:
        abort(404)
    if not hmac.compare_digest(token, po_token(po.id)):
        abort(404)
    ctx = build_agenda_context(po)
    resp = make_response(render_template("public_so/agenda.html", **ctx))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@public_po_bp.route("/<int:po_id>/<token>/status", methods=["POST"])
@csrf.exempt
def set_status(po_id, token):
    """Check-in do motorista: aplica um novo status ao item."""
    item = _get_po_item(po_id, token)
    try:
        checkin_service.apply_status(item, (request.form.get("status") or "").strip())
    except ValueError:
        abort(400)
    return redirect(url_for("public_po.agenda", po_id=po_id, token=token))


@public_po_bp.route("/<int:po_id>/<token>/revert", methods=["POST"])
@csrf.exempt
def revert(po_id, token):
    """Check-in do motorista: volta ao status anterior."""
    item = _get_po_item(po_id, token)
    checkin_service.revert_status(item)
    return redirect(url_for("public_po.agenda", po_id=po_id, token=token))
