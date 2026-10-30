"""Agenda pública do SO — link tokenizado SEM preços, com dados operacionais.

Mesmo visual do link público do RFQ, mas: nenhum valor monetário e os dados
preenchidos em "Dados Operacionais" do SO (motorista, rota, passageiro, voo).
"""
import hmac

from flask import abort, make_response, render_template

from . import public_so_bp
from ...models.order import Order
from ...services.so_agenda import build_agenda_context, so_token


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
