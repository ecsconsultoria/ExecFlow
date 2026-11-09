"""Agenda pública do SO — link tokenizado SEM preços, com dados operacionais.

Mesmo visual do link público do RFQ, mas: nenhum valor monetário e os dados
preenchidos em "Dados Operacionais" do SO (motorista, rota, passageiro, voo).
Inclui o check-in do motorista (status da viagem + revert) via POST.
"""
import hmac

from flask import abort, make_response, redirect, render_template, request, url_for

from . import public_so_bp
from ...extensions import csrf
from ...models.order import Order, OrderItem
from ...services import checkin_service
from ...services.so_agenda import build_agenda_context, so_token


def _get_order_item(order_id: int, token: str) -> OrderItem:
    order = Order.query.filter_by(id=order_id, deleted_at=None).first()
    if order is None:
        abort(404)
    if not hmac.compare_digest(token, so_token(order.id)):
        abort(404)
    item = OrderItem.query.filter_by(
        id=request.form.get("item_id", type=int), order_id=order_id).first()
    if item is None:
        abort(404)
    return item


@public_so_bp.route("/<int:order_id>/<token>")
def agenda(order_id, token):
    order = Order.query.filter_by(id=order_id, deleted_at=None).first()
    if order is None:
        abort(404)
    if not hmac.compare_digest(token, so_token(order.id)):
        abort(404)
    ctx = build_agenda_context(order)
    resp = make_response(render_template("public_so/agenda.html", **ctx))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@public_so_bp.route("/<int:order_id>/<token>/status", methods=["POST"])
@csrf.exempt
def set_status(order_id, token):
    """Check-in do motorista: aplica um novo status ao item."""
    item = _get_order_item(order_id, token)
    try:
        checkin_service.apply_status(item, (request.form.get("status") or "").strip())
    except ValueError:
        abort(400)
    return redirect(url_for("public_so.agenda", order_id=order_id, token=token))


@public_so_bp.route("/<int:order_id>/<token>/revert", methods=["POST"])
@csrf.exempt
def revert(order_id, token):
    """Check-in do motorista: volta ao status anterior."""
    item = _get_order_item(order_id, token)
    checkin_service.revert_status(item)
    return redirect(url_for("public_so.agenda", order_id=order_id, token=token))
