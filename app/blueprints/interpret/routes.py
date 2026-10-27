"""Tela pública de teste — interpretar mensagem de WhatsApp/e-mail (sem login).

Fase de teste: rota aberta SEM token (token será implantado após validação).
A tela apenas interpreta o texto e mostra os campos extraídos — não cria RFQ.
"""
from flask import jsonify, render_template, request

from . import interpret_bp
from ...extensions import csrf
from ...services.message_interpret import interpret_message


@interpret_bp.route("/interpretar")
def page():
    resp = render_template("interpret/interpret.html")
    return resp


@interpret_bp.route("/interpretar", methods=["POST"])
@csrf.exempt
def interpret():
    data = request.get_json(silent=True) or {}
    text = (data.get("texto") or "").strip()
    if not text:
        return jsonify({"ok": False, "erro": "Mensagem vazia."}), 400
    try:
        resultado = interpret_message(text)
        return jsonify({"ok": True, "resultado": resultado})
    except Exception as e:
        return jsonify({"ok": False, "erro": f"Falha na interpretação: {str(e)[:200]}"}), 502
