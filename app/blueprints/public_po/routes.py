"""Agenda pública da PO — link tokenizado SEM preços, com dados operacionais.

Renderiza o MESMO template da agenda do SO (public_so/agenda.html) com o
contexto da PO: itens op_* com fallback nos campos globais da PO.
"""
import hmac

from flask import abort, make_response, render_template

from . import public_po_bp
from ...models.purchase_order import PurchaseOrder
from ...services.po_agenda import build_agenda_context, po_token


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
