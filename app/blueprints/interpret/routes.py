"""Tela pública de teste — interpretar mensagem de WhatsApp/e-mail (sem login).

Fase de teste: rotas abertas SEM token (token será implantado após validação).
Interpreta o texto, o operador ajusta os campos na tela e cria o RFQ
(pendente, empresa padrão, sem preço) — a tela devolve o link público do
orçamento HTML pronto para enviar ao cliente.
"""
import unicodedata
from datetime import date as _date
from datetime import time as _time

from flask import current_app, jsonify, make_response, render_template, request, url_for

from . import interpret_bp
from ...extensions import csrf, db
from ...models.company import Company
from ...models.quote import Quote, QuoteInclusion, QuoteItem, DEFAULT_INCLUSIONS
from ...models.vehicle import VehicleCategory
from ...services.message_interpret import interpret_message
from ...services.numbering_service import next_rfq
from ...services.quote_html import public_token
from ...utils.audit import log_activity
from ...utils.helpers import parse_brl


@interpret_bp.route("/interpretar")
def page():
    resp = make_response(render_template("interpret/interpret.html"))
    # evita que o navegador sirva versão velha da tela (JS/HTML em cache)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
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


# ── Criação do RFQ a partir dos campos ajustados na tela ────────────────────

def _norm(s: str) -> str:
    """Normaliza para comparação: sem acentos, minúsculas, espaços colapsados."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return " ".join(s.split())


_CAT_MAP = None


def _categories() -> dict:
    """Mapa nome normalizado → id da categoria.

    Guarda apenas os IDs (nunca os objetos ORM): instâncias ficam
    desanexadas da sessão ao fim da requisição (DetachedInstanceError).
    """
    global _CAT_MAP
    if _CAT_MAP is None:
        _CAT_MAP = {_norm(c.name): c.id for c in VehicleCategory.query.all()}
    return _CAT_MAP


def _parse_date(v):
    if not v:
        return None
    try:
        return _date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def _parse_time(v):
    if not v:
        return None
    try:
        h, m = str(v).strip()[:5].split(":")
        return _time(int(h), int(m))
    except (ValueError, TypeError):
        return None


@interpret_bp.route("/criar-rfq", methods=["POST"])
@csrf.exempt
def criar_rfq():
    """Cria o RFQ (pendente, empresa padrão, sem preço) e devolve o link público."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "erro": "Payload inválido."}), 400
    company = Company.query.order_by(Company.id.asc()).first()
    if company is None:
        return jsonify({"ok": False, "erro": "Nenhuma empresa cadastrada."}), 500
    idioma = data.get("idioma") if data.get("idioma") in ("pt", "en") else "pt"
    quote = Quote(
        company_id=company.id,
        number=next_rfq(company.id),
        status="pendente",
        client_name=(data.get("cliente_nome") or "").strip() or None,
        contact_name=(data.get("contato_nome") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        phone=(data.get("telefone") or "").strip() or None,
        language=idioma,
        obs=(data.get("observacoes") or "").strip() or None,
        total_amount=0.0,
    )
    db.session.add(quote)
    db.session.flush()

    cats = _categories()
    for idx, it in enumerate(data.get("itens") or []):
        if not isinstance(it, dict):
            continue
        desc = (it.get("descricao") or "").strip()
        extras = []
        origem = (it.get("origem") or "").strip()
        destino = (it.get("destino") or "").strip()
        desc_low = desc.lower()
        if origem and origem.lower() not in desc_low:
            extras.append(f"Origem: {origem}")
        if destino and destino.lower() not in desc_low:
            extras.append(f"Destino: {destino}")
        pax = it.get("passageiros")
        if pax:
            try:
                n = int(pax)
                if n > 0 and "passageiro" not in desc_low and " pax" not in desc_low:
                    extras.append(f"{n} passageiro(s)")
            except (TypeError, ValueError):
                pass
        if extras:
            desc = (desc + " — " + " / ".join(extras)).strip(" —")
        cat_name = (it.get("categoria_veiculo") or "").strip()
        cat_id = cats.get(_norm(cat_name)) if cat_name else None
        try:
            qty = int(it.get("quantidade") or 1) or 1
        except (TypeError, ValueError):
            qty = 1
        # Preço: só entra se o operador anexou um valor (parse_brl tolera formatos)
        unit = parse_brl(it.get("preco_unitario"))
        if unit < 0:
            unit = 0.0
        item = QuoteItem(
            quote_id=quote.id,
            description=desc or None,
            vehicle_description=(cat_name if cat_name and not cat_id else None),
            category_id=cat_id,
            driver_name=(it.get("motorista") or "").strip() or None,
            service_date=_parse_date(it.get("data")),
            service_time=_parse_time(it.get("hora")),
            quantity=qty,
            unit_price=unit,
            total_price=round(unit * qty, 2),
            sort_order=idx,
        )
        db.session.add(item)

    # Inclusões padrão (o painel INCLUSO do link público precisa delas)
    for i, d in enumerate(DEFAULT_INCLUSIONS):
        if d.get("group") != "incluso":
            continue
        db.session.add(QuoteInclusion(
            quote_id=quote.id,
            text_pt=d["text_pt"],
            text_en=d.get("text_en") or "",
            included=True,
            sort_order=i,
        ))

    quote.recalculate_total()

    log_activity("quote", quote.id, company.id, "Criado pela tela de interpretação", None)
    db.session.commit()

    token = public_token(quote.id)
    base = current_app.config.get("PUBLIC_QUOTE_BASE", "").rstrip("/")
    if base:
        url = f"{base}/{quote.number}/{token}"
    else:
        url = (request.host_url.rstrip("/")
               + url_for("public_quotes.view", number=quote.number, token=token))
    return jsonify({"ok": True, "number": quote.number, "url": url})
