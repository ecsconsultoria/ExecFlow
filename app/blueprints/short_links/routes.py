"""Rotas de link curto.

Legado (base62, case-sensitive — links antigos continuam funcionando):
  /l/<code>      → agenda pública da PO (check-in do motorista)
  /l/so/<code>   → agenda pública do SO

Novos links (base36 minúscula — imunes a lowercasing de WhatsApp/Excel):
  /l/p/<code>    → agenda pública da PO
  /l/s/<code>    → agenda pública do SO
"""
from flask import abort, redirect, url_for

from . import short_links_bp
from ...models.order import Order
from ...models.purchase_order import PurchaseOrder
from ...services.po_agenda import po_token
from ...services.short_link import decode, decode_lower
from ...services.so_agenda import so_token


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


@short_links_bp.route("/l/so/<code>")
def go_so(code):
    """Link curto da agenda do SO (legado, base62)."""
    order_id = decode(code)
    if order_id is None:
        abort(404)
    order = Order.query.filter_by(id=order_id, deleted_at=None).first()
    if order is None:
        abort(404)
    return redirect(url_for("public_so.agenda", order_id=order.id,
                            token=so_token(order.id), _external=True))


@short_links_bp.route("/l/p/<code>")
def go_po_lower(code):
    """Link curto da PO em base36 minúscula — imune a lowercasing."""
    po_id = decode_lower(code)
    if po_id is None:
        abort(404)
    po = PurchaseOrder.query.filter_by(id=po_id, deleted_at=None).first()
    if po is None:
        abort(404)
    return redirect(url_for("public_po.agenda", po_id=po.id,
                            token=po_token(po.id), _external=True))


@short_links_bp.route("/l/s/<code>")
def go_so_lower(code):
    """Link curto da agenda do SO em base36 minúscula — imune a lowercasing."""
    order_id = decode_lower(code)
    if order_id is None:
        abort(404)
    order = Order.query.filter_by(id=order_id, deleted_at=None).first()
    if order is None:
        abort(404)
    return redirect(url_for("public_so.agenda", order_id=order.id,
                            token=so_token(order.id), _external=True))
