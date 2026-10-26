"""quote_html.py — Geração do HTML público do orçamento (envio por WhatsApp/e-mail).

Orçamento formatado em HTML (identidade preto/dourado) a partir dos dados reais
do RFQ. Usado pela rota pública /q/<number>/<token> e pelo download no painel.
Não altera o RFQ — apenas o apresenta.
"""
from __future__ import annotations

from urllib.parse import quote as _urlquote

from flask import current_app
from ..models.quote import Quote
from ..utils import make_client_token

WHATSAPP_NUMBER = "5511989178312"

# Categoria (slug do ExecFlow) → (modelo da frota, imagem da frota do site)
CATEGORY_FLEET = {
    "motorista_free_lance":      ("",                          "ShuttleVan.jpg"),
    "sedan_executivo":           ("Toyota Corolla | Similar",  "SedanExecutivo_Texto.jpg"),
    "sedan_premium":             ("Mercedes E & S Class | Similar", "SedanPremium_Texto.jpg"),
    "suv_executivo":             ("Jeep Commander, Tiggo 8 | Similar", "SuvExecutivo_Texto.jpg"),
    "suv_executivo_premium":     ("BMW X5, Volvo XC 90 | Similar", "SuvExecutivo_Texto.jpg"),
    "minivan_executivo":         ("Kia Carnival, SCUDO | Similar", "MinivanExecutivo_Texto.jpg"),
    "minivan_executivo_premium": ("Kia Carnival, SCUDO | Similar", "MinivanExecutivo_Texto.jpg"),
    "van_executiva":             ("Mercedes Sprinter | Similar", "VanExecutiva_Texto.jpg"),
    "sedan_blindado":            ("Toyota Corolla | Similar",  "SedanExecutivo_Texto.jpg"),
    "sedan_blindado_premium":    ("Toyota Corolla | Similar",  "SedanExecutivo_Texto.jpg"),
    "sedan-blindado-luxo":       ("Lexus LS300H",              "SedanExecutivo_Texto.jpg"),
    "suv_blindado":              ("Jeep Commander, Tiggo 8 | Similar", "SuvExecutivo_Texto.jpg"),
    "suv_blindado_premium":      ("BMW X5, Volvo XC 90 | Similar", "SuvExecutivo_Texto.jpg"),
    "minivan_blindado":          ("Kia Carnival, SCUDO | Similar", "MinivanExecutivo_Texto.jpg"),
    "minivan_blindado_premium":  ("Kia Carnival, SCUDO | Similar", "MinivanExecutivo_Texto.jpg"),
    "van_blindada":              ("Mercedes Sprinter | Similar", "VanExecutiva_Texto.jpg"),
    "microonibus_executivo":     ("", "MicroOnibus_Texto.jpg"),
    "onibus_executivo":          ("", "OnibusExecutivo_Texto.jpg"),
}

# Categoria → nome em inglês (para o modo EN da página)
CATEGORY_EN = {
    "sedan": "Sedan", "suv": "SUV", "minivan": "Minivan", "van": "Van",
    "microonibus": "Minibus", "onibus": "Bus", "blindado": "Bulletproof",
    "blindada": "Bulletproof", "executivo": "Executive", "premium": "Premium",
    "luxo": "Luxury",
}

CANCELLATION_POLICY = {
    "pt": [
        "72 horas antes do evento, será cobrada uma taxa de 10%.",
        "48 horas antes do evento, será cobrada uma taxa de 50%.",
        "24 horas antes do evento, será cobrada uma taxa de 100%.",
    ],
    "en": [
        "72 hours before the event, a 10% fee will be charged.",
        "48 hours before the event, a 50% fee will be charged.",
        "24 hours before the event, a 100% fee will be charged.",
    ],
}

VALIDITY_TEXT = {
    "pt": "Esta proposta é válida por 15 dias a partir da data de emissão. Preços sujeitos a alteração sem aviso prévio.",
    "en": "This quotation is valid for 15 days from the date of issue. Prices subject to change without notice.",
}


def public_token(quote_id: int) -> str:
    """Token de acesso público do orçamento (HMAC do id com a SECRET_KEY)."""
    return make_client_token(quote_id, current_app.config["SECRET_KEY"])


def category_label_pt(name: str) -> str:
    return name or ""


def category_label_en(name: str) -> str:
    """Traduz o nome da categoria para EN (ex.: Minivan Blindado → Bulletproof Minivan)."""
    if not name:
        return ""
    parts = [p.strip() for p in name.split(" ") if p.strip()]
    out = []
    for i, p in enumerate(parts):
        key = p.lower()
        if key == "blindado":
            out.append("Bulletproof")
        elif key == "executivo":
            out.append("Executive")
        elif key == "premium":
            out.append("Premium")
        elif key == "luxo":
            out.append("Luxury")
        elif key == "minivan":
            out.append("Minivan")
        elif key == "sedan":
            out.append("Sedan")
        elif key == "suv":
            out.append("SUV")
        elif key == "van":
            out.append("Van")
        elif key == "microônibus":
            out.append("Minibus")
        elif key == "ônibus":
            out.append("Bus")
        else:
            out.append(p)
    # Bulletproof antes do tipo de veículo (inglês): Minivan Blindado → Bulletproof Minivan
    if "Bulletproof" in out:
        out.remove("Bulletproof")
        out.insert(0, "Bulletproof")
    return " ".join(out)


def driver_label(driver_name: str, lang: str) -> str:
    """Label do motorista por idioma (Bilíngue/Monolíngue)."""
    name = (driver_name or "").strip().lower()
    if lang == "en":
        if name in ("bilíngue", "bilingue"):
            return "English Speaking Driver"
        if name in ("monolíngue", "monolingue"):
            return "Portuguese Speaking Driver"
        return driver_name or ""
    if name in ("bilíngue", "bilingue"):
        return "Motorista bilíngue"
    if name in ("monolíngue", "monolingue"):
        return "Motorista monolíngue"
    return driver_name or ""


def fleet_for(category) -> tuple[str, str]:
    """(modelo, imagem) da frota para uma VehicleCategory."""
    slug = (category.slug or "") if category else ""
    model, image = CATEGORY_FLEET.get(slug, ("", "ShuttleVan.jpg"))
    return category.description or model or "", image


def accept_text(lang: str, number: str) -> str:
    if lang == "en":
        return _urlquote(f"Hello, I accept quotation {number}")
    return _urlquote(f"Olá, aceito o orçamento {number}")


def ask_text(lang: str, number: str) -> str:
    if lang == "en":
        return _urlquote(f"Hello, I have a question about quotation {number}")
    return _urlquote(f"Olá, tenho uma dúvida sobre o orçamento {number}")


def _fmt_brl(value: float, lang: str) -> str:
    if lang == "en":
        return f"R$ {value:,.2f}"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def money(value: float, lang: str) -> str:
    """Formata moeda para o template público (PT: 2.838,22 · EN: 2,838.22)."""
    try:
        return _fmt_brl(float(value), lang)
    except (TypeError, ValueError):
        return _fmt_brl(0.0, lang)


def _i18n_dict(ctx: dict) -> dict:
    """Dicionário PT/EN para o seletor de idioma do cliente (client-side)."""
    number = ctx["quote"].number
    items = ctx["items"]
    pt, en = {}, {}
    pt["ref"], en["ref"] = "ORÇAMENTO", "QUOTATION"
    pt["date_ref"], en["date_ref"] = ctx["emission_pt"], ctx["emission_en"]
    pt["total_label"], en["total_label"] = "PREÇO TOTAL", "TOTAL PRICE"
    pt["pay_title"], en["pay_title"] = "FORMA DE PAGAMENTO", "PAYMENT METHOD"
    pt["pay1"] = "• " + ctx["payment_method"] if ctx["payment_method"] else ""
    en["pay1"] = pt["pay1"]
    pt["pay2"] = "• " + ctx["payment_terms"] if ctx["payment_terms"] else ""
    en["pay2"] = pt["pay2"]
    pt["inc_title"], en["inc_title"] = "INCLUSO", "INCLUDED"
    pt["cancel_title"], en["cancel_title"] = "POLÍTICA DE CANCELAMENTO", "CANCELLATION POLICY"
    pt["obs_title"], en["obs_title"] = "OBSERVAÇÕES", "NOTES"
    pt["accept"] = "✓   ACEITAR ORÇAMENTO"
    en["accept"] = "✓   ACCEPT QUOTATION"
    pt["ask"] = "♡   FALAR NO WHATSAPP"
    en["ask"] = "♡   ASK ON WHATSAPP"
    pt["validity"], en["validity"] = VALIDITY_TEXT["pt"], VALIDITY_TEXT["en"]
    pt["wa_accept"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={accept_text('pt', number)}"
    en["wa_accept"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={accept_text('en', number)}"
    pt["wa_ask"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={ask_text('pt', number)}"
    en["wa_ask"] = f"https://wa.me/{WHATSAPP_NUMBER}?text={ask_text('en', number)}"
    for idx, it in enumerate(items, start=1):
        pt[f"date{idx}"] = f"{it['date_pt']} às {it['time_pt']}"
        en[f"date{idx}"] = f"{it['date_en']} at {it['time_en']}"
        model = f" ({it['model']})" if it["model"] else ""
        pt[f"veh{idx}"] = f"{it['category_pt']}{model}"
        en[f"veh{idx}"] = f"{it['category_en']}{model}"
        pt[f"driver{idx}"] = driver_label(it["driver"], "pt")
        en[f"driver{idx}"] = driver_label(it["driver"], "en")
        pt[f"price{idx}"] = _fmt_brl(it["unit"], "pt")
        en[f"price{idx}"] = _fmt_brl(it["unit"], "en")
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
        model, image = fleet_for(it.category)
        cat_pt = it.category.name if it.category else ""
        d = it.service_date
        t = it.service_time
        items.append({
            "description": it.description or "",
            "date_pt": f"{d.day:02d}/{d.month:02d}/{d.year}" if d else "",
            "date_en": f"{d.month:02d}/{d.day:02d}/{d.year}" if d else "",
            "time_pt": f"{t.hour:02d}:{t.minute:02d}h" if t else "",
            "time_en": f"{t.hour:02d}:{t.minute:02d}" if t else "",
            "driver": it.driver_name or "",
            "category_pt": cat_pt,
            "category_en": category_label_en(cat_pt),
            "model": model,
            "image": image,
            "unit": it.total_price or 0.0,
            "unit_usd": round((it.total_price or 0.0) / rate) if rate else None,
        })
    inclusions = [inc for inc in sorted(quote.inclusions, key=lambda x: x.sort_order or 0) if inc.included]
    hero_image = items[0]["image"] if items else "ShuttleVan.jpg"
    created = quote.created_at

    ctx = {
        "quote": quote,
        "items": items,
        "inclusions": inclusions,
        "total": quote.total_amount or 0.0,
        "total_usd": round((quote.total_amount or 0.0) / rate) if rate else None,
        "rate": rate,
        "hero_image": hero_image,
        "whatsapp": WHATSAPP_NUMBER,
        "cancellation": CANCELLATION_POLICY,
        "validity": VALIDITY_TEXT,
        "lang": quote.language or "pt",
        "payment_method": (quote.payment_method or "").strip().title(),
        "payment_terms": (quote.payment_terms or "").strip(),
        "emission_pt": f"{created.day:02d}/{created.month:02d}/{created.year}" if created else "",
        "emission_en": f"{created.month:02d}/{created.day:02d}/{created.year}" if created else "",
    }
    ctx["i18n"] = _i18n_dict(ctx)
    return ctx
