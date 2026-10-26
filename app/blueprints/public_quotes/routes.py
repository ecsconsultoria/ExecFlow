"""Rotas públicas do orçamento — acesso do CLIENTE sem login, protegido por token HMAC.

O cliente só acessa o orçamento cujo link (número + token) foi compartilhado;
qualquer outro par retorna 404. Sem listagem pública, sem dados de outras empresas.
"""
import hmac

from flask import abort, current_app, make_response, render_template

from . import public_quotes_bp
from ...models.quote import Quote
from ...services.quote_html import build_context, public_token


@public_quotes_bp.route("/<number>/<token>")
def view(number, token):
    quote = Quote.query.filter_by(number=number, deleted_at=None).first()
    if quote is None:
        abort(404)
    expected = public_token(quote.id)
    if not hmac.compare_digest(token, expected):
        abort(404)
    ctx = build_context(quote)
    resp = make_response(render_template("quotes/public_quote.html", **ctx))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp
