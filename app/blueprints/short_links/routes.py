"""Rotas de link curto — /l/<code> redireciona para a agenda pública (PO)."""
from flask import abort, redirect, url_for

from . import short_links_bp
from ...models.purchase_order import PurchaseOrder
from ...services.po_agenda import po_token
from ...services.short_link import decode


@short_links_bp.route("/l/<code>")
def go(code):
    po_id = decode(code)
    if po_id is None:
        abort(404)
    po = PurchaseOrder.query.filter_by(id=po_id, deleted_at=None).first()
    if po is None:
        abort(404)
    return redirect(url_for("public_po.agenda", po_id=po.id,
                            token=po_token(po.id), _external=True))
