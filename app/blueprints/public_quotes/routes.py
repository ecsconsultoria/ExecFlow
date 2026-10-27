"""Rotas públicas do orçamento — acesso do CLIENTE sem login, protegido por token HMAC.

O cliente só acessa o orçamento cujo link (número + token) foi compartilhado;
qualquer outro par retorna 404. Sem listagem pública, sem dados de outras empresas.
"""
import hmac

from flask import abort, current_app, jsonify, make_response, redirect, render_template, url_for

from . import public_quotes_bp
from ...extensions import csrf
from ...models.quote import Quote
from ...services.quote_html import build_context, public_token
from ...services.paypal_service import paypal_approve_url
from ...services.inter_pix_service import create_pix, check_pix
from ...services.static_pix_service import build_static_pix


def _get_quote_or_404(number, token):
    quote = Quote.query.filter_by(number=number, deleted_at=None).first()
    if quote is None:
        abort(404)
    expected = public_token(quote.id)
    if not hmac.compare_digest(token, expected):
        abort(404)
    return quote


@public_quotes_bp.route("/<number>/<token>")
def view(number, token):
    quote = _get_quote_or_404(number, token)
    ctx = build_context(quote)
    resp = make_response(render_template("quotes/public_quote.html", **ctx))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@public_quotes_bp.route("/<number>/<token>/paypal")
def paypal(number, token):
    """Abre o checkout do PayPal já com o valor do orçamento (link do texto PayPal)."""
    quote = _get_quote_or_404(number, token)
    amount = quote.total_amount or 0.0
    if amount <= 0:
        return _paypal_error(f"Orçamento {quote.number} sem valor para pagamento."), 400
    page_url = url_for("public_quotes.view", number=number, token=token, _external=True)
    approve, erro = paypal_approve_url(amount, quote.number, return_url=page_url, cancel_url=page_url)
    if erro:
        return _paypal_error(erro), 503
    return redirect(approve)


@public_quotes_bp.route("/<number>/<token>/pix", methods=["POST"])
@csrf.exempt
def pix_create(number, token):
    """Gera a cobrança Pix (QR Code) — Banco Inter ou estático como fallback."""
    quote = _get_quote_or_404(number, token)
    amount = quote.total_amount or 0.0
    if amount <= 0:
        return jsonify({"ok": False, "erro": f"Orçamento {quote.number} sem valor para pagamento."}), 400
    # Integração Banco Inter ativa? senão usa o QR estático com o valor injetado
    if not current_app.config.get("INTER_PIX_KEY", ""):
        try:
            data = build_static_pix(amount)
            return jsonify({"ok": True, **data})
        except ValueError as exc:
            return jsonify({"ok": False, "erro": f"Falha no PIX: {str(exc)[:200]}"}), 502
    try:
        data = create_pix(amount, quote.number)
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return jsonify({"ok": False, "erro": f"Falha no PIX: {str(exc)[:200]}"}), 502


@public_quotes_bp.route("/<number>/<token>/pix/<txid>/status")
def pix_status(number, token, txid):
    """Status da cobrança Pix (pago/pendente) — usado pelo polling do QR Code."""
    _get_quote_or_404(number, token)
    return jsonify({"ok": True, "status": check_pix(txid)})


def _paypal_error(msg: str):
    """Página simples de erro no mesmo tema escuro da página pública."""
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<title>PayPal — Executive Car SP</title></head>"
        "<body style='margin:0;background:#080807;color:#f7f7f5;font-family:Arial,sans-serif;"
        "display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center'>"
        "<div><p style='color:#d9ad56;font-weight:700'>EXECUTIVE CAR SP</p>"
        f"<p style='max-width:420px'>{msg}</p>"
        "<p><a href='javascript:history.back()' style='color:#f6d17d'>Voltar ao orçamento</a></p>"
        "</div></body></html>"
    )
