"""quote_html.py — Geração do HTML público do orçamento (envio por WhatsApp/e-mail).

Orçamento formatado em HTML (identidade preto/dourado) a partir dos dados reais
do RFQ. Usado pela rota pública /q/<number>/<token> e pelo download no painel.
Não altera o RFQ — apenas o apresenta.

Traduções PT/EN: reutiliza os dicionários/funções do PDF (quote_pdf.py) para
manter consistência entre os dois formatos (fonte única de verdade).
"""
from __future__ import annotations

from urllib.parse import quote as _urlquote

from flask import current_app, url_for
from markupsafe import Markup
from ..models.quote import Quote
from ..utils import make_client_token
from ..utils.translate import translate_obs
from .quote_pdf import (
    _translate_vehicle,
    _translate_service,
    _translate_driver as _pdf_driver,
    _translate_payment_terms,
    _get_vehicle_model,
)

WHATSAPP_NUMBER = "5511989178312"

# Categoria (slug do ExecFlow) → imagem da frota do site
CATEGORY_IMAGE = {
    "motorista_free_lance":      "ShuttleVan.jpg",
    "sedan_executivo":           "SedanExecutivo_Texto.jpg",
    "sedan_premium":             "SedanPremium_Texto.jpg",
    "suv_executivo":             "SuvExecutivo_Texto.jpg",
    "suv_executivo_premium":     "SuvExecutivo_Texto.jpg",
    "minivan_executivo":         "MinivanExecutivo_Texto.jpg",
    "minivan_executivo_premium": "MinivanExecutivo_Texto.jpg",
    "van_executiva":             "VanExecutiva_Texto.jpg",
    "sedan_blindado":            "SedanExecutivo_Texto.jpg",
    "sedan_blindado_premium":    "SedanExecutivo_Texto.jpg",
    "sedan-blindado-luxo":       "SedanExecutivo_Texto.jpg",
    "suv_blindado":              "SuvExecutivo_Texto.jpg",
    "suv_blindado_premium":      "SuvExecutivo_Texto.jpg",
    "minivan_blindado":          "MinivanExecutivo_Texto.jpg",
    "minivan_blindado_premium":  "MinivanExecutivo_Texto.jpg",
    "van_blindada":              "VanExecutiva_Texto.jpg",
    "microonibus_executivo":     "MicroOnibus_Texto.jpg",
    "onibus_executivo":          "OnibusExecutivo_Texto.jpg",
}

# Método de pagamento (texto livre do RFQ) → inglês
PAYMENT_METHOD_EN = {
    "cartão de crédito":      "Credit Card",
    "cartao de credito":      "Credit Card",
    "pix":                    "Pix",
    "transferência bancária": "Wire Transfer",
    "transferencia bancaria": "Wire Transfer",
    "paypal":                 "PayPal",
    "paypal (cartão de crédito)": "PayPal (Credit Card)",
    "boleto":                 "Bank Slip",
}

CANCELLATION_POLICY = {
    "pt": [
        "72h antes do evento, cobraremos taxa de 10%.",
        "48h antes do evento, cobraremos taxa de 50%.",
        "24h antes do evento, cobraremos taxa de 100%.",
    ],
    "en": [
        "72h before the event, we will charge a 10% fee.",
        "48h before the event, we will charge a 50% fee.",
        "24h before the event, we will charge a 100% fee.",
    ],
}

VALIDITY_TEXT = {
    "pt": [
        "Esta proposta é válida por 15 dias a partir da data de emissão.",
        "Preços sujeitos a alteração sem aviso prévio.",
    ],
    "en": [
        "This quotation is valid for 15 days from the date of issue.",
        "Prices subject to change without notice.",
    ],
}


def public_token(quote_id: int) -> str:
    """Token de acesso público do orçamento (HMAC do id com a SECRET_KEY)."""
    return make_client_token(quote_id, current_app.config["SECRET_KEY"])


def driver_label(driver_name: str, lang: str) -> str:
    """Label do motorista — nomenclatura comercial do site (depois do PDF como fallback)."""
    name = (driver_name or "").strip().lower()
    if lang == "en":
        if name in ("bilíngue", "bilingue"):
            return "English Speaking Driver"
        if name in ("monolíngue", "monolingue"):
            return "Portuguese Speaking Driver"
    else:
        if name in ("bilíngue", "bilingue"):
            return "Motorista bilíngue"
        if name in ("monolíngue", "monolingue"):
            return "Motorista monolíngue"
    return _pdf_driver(driver_name, lang) or (driver_name or "")


def vehicle_label(category_name: str, lang: str) -> str:
    """Nome da categoria no idioma (usa a tradução do PDF: 'Executive SUV' etc.)."""
    if not category_name:
        return ""
    return _translate_vehicle(category_name, lang) or category_name


def vehicle_model(category_name: str, lang: str) -> str:
    """Modelo atrelado à categoria (tabela do PDF; Vito → SCUDO por decisão comercial)."""
    model = _get_vehicle_model(category_name, lang)
    return model.replace("Mercedes Vito", "SCUDO")


def payment_method_label(method: str, lang: str) -> str:
    m = (method or "").strip()
    if lang == "en":
        return PAYMENT_METHOD_EN.get(m.lower(), m)
    return m


def fleet_image_for(category) -> str:
    slug = (category.slug or "") if category else ""
    return CATEGORY_IMAGE.get(slug, "ShuttleVan.jpg")


def accept_text(lang: str, number: str) -> str:
    if lang == "en":
        return _urlquote(f"Hello, I accept quotation {number}")
    return _urlquote(f"Olá, aceito o orçamento {number}")


def ask_text(lang: str, number: str) -> str:
    if lang == "en":
        return _urlquote(f"Hello, I have a question about quotation {number}")
    return _urlquote(f"Olá, tenho uma dúvida sobre o orçamento {number}")


def money(value: float, lang: str) -> str:
    """Formata moeda para o template público — valor inteiro, sem centavos
    (PT: R$ 2.838 · EN: R$ 2,838)."""
    try:
        value = round(float(value))
    except (TypeError, ValueError):
        value = 0
    if lang == "en":
        return f"R$ {value:,.0f}"
    return f"R$ {value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(value, lang: str) -> str:
    """Número formatado com separador de milhar (PT: 1.869 · EN: 1,869)."""
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        n = 0
    s = f"{n:,}"
    if lang == "pt":
        s = s.replace(",", ".")
    return s


def money_html(value, lang: str) -> str:
    """HTML do valor em R$ — símbolo dourado e número branco."""
    return Markup(f'<span class="cur">R$</span> <span class="val">{_num(value, lang)}</span>')


def usd_html(value, lang: str) -> str:
    """HTML do valor em USD — pipe branco, símbolo dourado e número branco."""
    return Markup(f'<span class="pipe">|</span> <span class="cur">USD</span> <span class="val">{_num(value, lang)}</span>')


def _i18n_dict(ctx: dict) -> dict:
    """Dicionário PT/EN para o seletor de idioma do cliente (client-side)."""
    number = ctx["quote"].number
    items = ctx["items"]
    pt, en = {}, {}
    pt["ref"], en["ref"] = "ORÇAMENTO", "QUOTATION"
    pt["date_ref"], en["date_ref"] = ctx["emission_pt"], ctx["emission_en"]
    pt["total_label"], en["total_label"] = "PREÇO TOTAL", "TOTAL PRICE"
    pt["total_brl"], en["total_brl"] = ctx["total_brl_pt"], ctx["total_brl_en"]
    pt["total_usd_line"], en["total_usd_line"] = ctx["total_usd_pt"], ctx["total_usd_en"]
    pt["unit_label"], en["unit_label"] = "Preço Unitário", "Unit Price"
    pt["pay_title"], en["pay_title"] = "FORMA DE PAGAMENTO", "PAYMENT METHOD"
    pt["pay_bank"], en["pay_bank"] = "Transferência Bancária", "Wire Transfer"
    pt["pay_pix"], en["pay_pix"] = "PIX", "PIX"
    pt["pay_paypal"], en["pay_paypal"] = "PayPal", "PayPal"
    pt["pix_paying"], en["pix_paying"] = "Gerando QR Code...", "Generating QR Code..."
    pt["pix_err"], en["pix_err"] = "Não foi possível gerar o QR Code.", "Could not generate the QR Code."
    pt["pix_copy"], en["pix_copy"] = "Copiar", "Copy"
    pt["pix_copied"], en["pix_copied"] = "Copiado!", "Copied!"
    pt["pix_paid"], en["pix_paid"] = "✓ Pagamento confirmado!", "✓ Payment confirmed!"
    pt["pix_static_note"], en["pix_static_note"] = (
        "Pague o valor exato do orçamento. A confirmação será feita pela empresa.",
        "Please pay the exact quotation amount. Confirmation will be done by the company.",
    )
    pt["pay_ok_title"], en["pay_ok_title"] = "Pagamento efetuado com sucesso", "Payment successful"
    pt["pay_ok_sub"], en["pay_ok_sub"] = (
        "Seu pagamento foi efetuado com sucesso.",
        "You have paid successfully.",
    )
    pt["pay_ok_done"], en["pay_ok_done"] = "Concluído", "Done"
    pt["inc_title"], en["inc_title"] = "INCLUSO", "INCLUDED"
    pt["cancel_title"], en["cancel_title"] = "POLÍTICA DE CANCELAMENTO", "CANCELLATION POLICY"
    pt["obs_title"], en["obs_title"] = "OBSERVAÇÕES", "NOTES"
    pt["obs"], en["obs"] = ctx["obs_pt"], ctx["obs_en"]
    pt["accept"] = "✓   ACEITAR ORÇAMENTO"
    en["accept"] = "✓   ACCEPT QUOTATION"
    pt["ask"] = "♡   FALAR NO WHATSAPP"
    en["ask"] = "♡   ASK ON WHATSAPP"
    pt["validity1"], en["validity1"] = VALIDITY_TEXT["pt"][0], VALIDITY_TEXT["en"][0]
    pt["validity2"], en["validity2"] = VALIDITY_TEXT["pt"][1], VALIDITY_TEXT["en"][1]
    pt["company_line"] = "Executive Car SP • CNPJ 11.183.125/0001-10"
    en["company_line"] = "Executive Car SP • TAX ID 11.183.125/0001-10"
    pt["wa_accept"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={accept_text('pt', number)}"
    en["wa_accept"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={accept_text('en', number)}"
    pt["wa_ask"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={ask_text('pt', number)}"
    en["wa_ask"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={ask_text('en', number)}"
    for idx, it in enumerate(items, start=1):
        pt[f"date{idx}"] = it["dt_pt"]
        en[f"date{idx}"] = it["dt_en"]
        pt[f"svc{idx}"] = it["service_pt"]
        en[f"svc{idx}"] = it["service_en"]
        model_pt = f" ({it['model_pt']})" if it["model_pt"] else ""
        model_en = f" ({it['model_en']})" if it["model_en"] else ""
        pt[f"veh{idx}"] = f"{it['category_pt']}{model_pt}"
        en[f"veh{idx}"] = f"{it['category_en']}{model_en}"
        pt[f"driver{idx}"] = it["driver_pt"]
        en[f"driver{idx}"] = it["driver_en"]
        pt[f"price{idx}"] = money_html(it["unit"], "pt")
        en[f"price{idx}"] = money_html(it["unit"], "en")
        pt[f"usd{idx}"] = usd_html(it["unit_usd"], "pt") if it["unit_usd"] is not None else ""
        en[f"usd{idx}"] = usd_html(it["unit_usd"], "en") if it["unit_usd"] is not None else ""
    for idx, inc in enumerate(ctx["inclusions"], start=1):
        pt[f"inc{idx}"] = "• " + inc.text_pt
        en[f"inc{idx}"] = "• " + (inc.text_en or inc.text_pt)
    for idx, line in enumerate(CANCELLATION_POLICY["pt"], start=1):
        pt[f"cancel{idx}"] = "• " + line
    for idx, line in enumerate(CANCELLATION_POLICY["en"], start=1):
        en[f"cancel{idx}"] = "• " + line
    return {"pt": pt, "en": en}


def build_context(quote: Quote) -> dict:
    """Contexto completo para o template público do orçamento."""
    rate = quote.usd_rate or 0.0
    items = []
    for it in sorted(quote.items, key=lambda x: x.sort_order or 0):
        cat_name = it.category.name if it.category else ""
        d = it.service_date
        t = it.service_time
        date_pt = f"{d.day:02d}/{d.month:02d}/{d.year}" if d else ""
        date_en = f"{d.month:02d}/{d.day:02d}/{d.year}" if d else ""
        time_pt = f"{t.hour:02d}:{t.minute:02d}h" if t else ""
        time_en = f"{t.hour:02d}:{t.minute:02d}" if t else ""
        # linha de data/hora — separador "às"/"at" só quando há data
        dt_pt = " às ".join(x for x in (date_pt, time_pt) if x)
        dt_en = " at ".join(x for x in (date_en, time_en) if x)
        items.append({
            "service_pt": _translate_service(it.description or "", "pt"),
            "service_en": _translate_service(it.description or "", "en"),
            "dt_pt": dt_pt,
            "dt_en": dt_en,
            "category_pt": vehicle_label(cat_name, "pt"),
            "category_en": vehicle_label(cat_name, "en"),
            "model_pt": vehicle_model(cat_name, "pt"),
            "model_en": vehicle_model(cat_name, "en"),
            "driver_pt": driver_label(it.driver_name, "pt"),
            "driver_en": driver_label(it.driver_name, "en"),
            "image": fleet_image_for(it.category),
            "unit": it.total_price or 0.0,
            "unit_usd": round((it.total_price or 0.0) / rate) if rate else None,
        })
    inclusions = [inc for inc in sorted(quote.inclusions, key=lambda x: x.sort_order or 0) if inc.included]
    hero_image = items[0]["image"] if items else "ShuttleVan.jpg"
    created = quote.created_at

    total = quote.total_amount or 0.0
    total_usd = round(total / rate) if rate else None
    # observações: original + tradução automática para o seletor EN (com cache)
    obs_pt = quote.obs or ""
    obs_en = translate_obs(obs_pt, "en")
    ctx = {
        "quote": quote,
        "items": items,
        "inclusions": inclusions,
        "total": total,
        "total_brl_pt": money_html(total, "pt"),
        "total_brl_en": money_html(total, "en"),
        "total_usd_pt": usd_html(total_usd, "pt") if total_usd is not None else "",
        "total_usd_en": usd_html(total_usd, "en") if total_usd is not None else "",
        "total_usd": total_usd,
        "rate": rate,
        "hero_image": hero_image,
        "whatsapp": WHATSAPP_NUMBER,
        "cancellation": CANCELLATION_POLICY,
        "validity": VALIDITY_TEXT,
        "lang": quote.language or "pt",
        "payment_method_pt": (quote.payment_method or "").strip().title(),
        "payment_method_en": payment_method_label(quote.payment_method or "", "en"),
        "payment_terms_pt": _translate_payment_terms(quote.payment_terms or "", "pt") or "",
        "payment_terms_en": _translate_payment_terms(quote.payment_terms or "", "en") or "",
        "emission_pt": f"{created.day:02d}/{created.month:02d}/{created.year}" if created else "",
        "emission_en": f"{created.month:02d}/{created.day:02d}/{created.year}" if created else "",
        "obs_pt": obs_pt,
        "obs_en": obs_en,
        "paypal_url": url_for("public_quotes.paypal", number=quote.number, token=public_token(quote.id)),
        # client id público (o SDK do PayPal exige expor no HTML; o segredo fica só no servidor)
        "paypal_client_id": current_app.config.get("PAYPAL_CLIENT_ID", ""),
    }
    ctx["i18n"] = _i18n_dict(ctx)
    return ctx
