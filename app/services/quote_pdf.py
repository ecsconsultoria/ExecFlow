"""PDF generator for quotes — Portuguese and English versions, V2 style."""
from __future__ import annotations

import io
import os
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Brand colours (V2 style)
# ---------------------------------------------------------------------------
BRAND_DARK   = colors.HexColor("#0b0b0b")   # preto Executive (V2)
BRAND_GOLD   = colors.HexColor("#b88b2d")   # dourado Executive (V2)
BRAND_LIGHT  = colors.HexColor("#F4F6F9")   # cinza claro (V2)
BRAND_GREEN  = colors.HexColor("#2e7d32")
BRAND_RED    = colors.HexColor("#c62828")
BRAND_BLUE   = colors.HexColor("#1565c0")

_STATUS_COLORS = {
    "pendente":           (colors.HexColor("#F4F6F9"), colors.HexColor("#0b0b0b")),
    "aprovado":           (colors.HexColor("#2E7D32"), colors.white),
    "reprovado":          (colors.HexColor("#C62828"), colors.white),
    "reserva_confirmada": (colors.HexColor("#b88b2d"), colors.white),
    "pago":               (colors.HexColor("#1565C0"), colors.white),
    "pago_parcial":       (colors.HexColor("#E65100"), colors.white),
    "cancelado":          (colors.HexColor("#757575"), colors.white),
}

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
_T: dict[str, dict[str, str]] = {
    "title":            {"pt": "PROPOSTA COMERCIAL",       "en": "QUOTATION"},
    "company_col":      {"pt": "EMPRESA",                  "en": "COMPANY"},
    "contact_col":      {"pt": "NOME DO CONTATO",          "en": "CONTACT NAME"},
    "email_col":        {"pt": "E-MAIL",                   "en": "EMAIL ADDRESS"},
    "mobile_col":       {"pt": "CELULAR",                  "en": "MOBILE"},
    "status_col":       {"pt": "STATUS",                   "en": "STATUS"},
    "hash_col":         {"pt": "#",                        "en": "#"},
    "service_col":      {"pt": "SERVIÇO",                  "en": "SERVICE"},
    "qty_col":          {"pt": "QTD.",                     "en": "QTY."},
    "unit_col":         {"pt": "UNIT.",                    "en": "UNIT."},
    "overtime_col":     {"pt": "HORA EXTRA",               "en": "OVERTIME"},
    "total_col":        {"pt": "TOTAL",                    "en": "TOTAL"},
    "payment_col":      {"pt": "FORMA DE PAGAMENTO",       "en": "PAYMENT METHOD"},
    "included_col":     {"pt": "FATURAMENTO FISCAL",        "en": "INVOICE"},
    "prazo_col":        {"pt": "PRAZO DE PAGAMENTO",        "en": "PAYMENT TERMS"},
    "total_price_col":  {"pt": "VALOR TOTAL",              "en": "TOTAL PRICE"},
    "incluso_hdr":      {"pt": "Serviços Inclusos",        "en": "Included Services"},
    "info_hdr":         {"pt": "Informações Importantes",  "en": "Important Information"},
    "add_info":         {"pt": "INFORMAÇÕES ADICIONAIS",   "en": "ADDITIONAL INFORMATION"},
    "cancel_policy":    {"pt": "POLÍTICA DE CANCELAMENTO", "en": "CANCELLATION POLICY"},
    "cancel_intro":     {"pt": "Em caso de cancelamento da reserva:",
                         "en": "In case of booking cancellation:"},
    "cancel_72":        {"pt": "72 horas antes do evento, será cobrada uma taxa de 10%.",
                         "en": "72 hours before the event, a fee of 10% will be charged."},
    "cancel_48":        {"pt": "48 horas antes do evento, será cobrada uma taxa de 50%.",
                         "en": "48 hours before the event, a fee of 50% will be charged."},
    "cancel_24":        {"pt": "24 horas antes do evento, será cobrada uma taxa de 100%.",
                         "en": "24 hours before the event, a fee of 100% will be charged."},
    "validity":         {"pt": "Esta proposta é válida por 15 dias a partir da data de emissão. Preços sujeitos a alteração sem aviso prévio.",
                         "en": "This quotation is valid for 15 days from the date of issue. Prices subject to change without notice."},
    "approve":          {"pt": "[ Aprovar ]",              "en": "[ Approve ]"},
    "questions":        {"pt": "[ Perguntas ]",            "en": "[ Questions ]"},
    "decline":          {"pt": "[ Recusar ]",              "en": "[ Decline ]"},
    "generated":        {"pt": "Gerado em",                "en": "Generated on"},
    "tax_id":           {"pt": "CNPJ",                     "en": "Tax ID"},
    "vehicle_lbl":      {"pt": "Veículo:",                 "en": "Vehicle:"},
    "status_pendente":  {"pt": "Proposta",                 "en": "Quotation"},
    "status_aprovado":  {"pt": "Aprovado",                 "en": "Approved"},
    "status_reprovado": {"pt": "Reprovado",                "en": "Declined"},
    "status_pago":      {"pt": "Pago",                     "en": "Paid"},
    "billing_recibo":       {"pt": "Recibo",               "en": "Receipt"},
    "billing_nf":           {"pt": "Nota Fiscal",          "en": "Invoice (NF)"},
    "billing_cartao":       {"pt": "Cartão de Crédito",    "en": "Credit Card"},
    "billing_nf_cartao":    {"pt": "Nota Fiscal + Cartão", "en": "Invoice + Card"},
    "fee_recibo":           {"pt": "–",                    "en": "–"},
    "fee_nf":               {"pt": "Taxa NF incluída",     "en": "NF Fee Included"},
    "fee_cartao":           {"pt": "Taxa Cartão incluída", "en": "Credit Card Fee"},
    "fee_nf_cartao":        {"pt": "Taxa NF + Cartão",     "en": "NF + Card Fee"},
    "pay_PIX":              {"pt": "PIX",                  "en": "PIX"},
    "pay_DINHEIRO":         {"pt": "Dinheiro",             "en": "Cash"},
    "pay_TRANSFER\u00caNCI\u00c1":    {"pt": "Transfer\u00eancia",        "en": "Wire Transfer"},
    "pay_TRANSFER\u00caNCIA":    {"pt": "Transfer\u00eancia",        "en": "Wire Transfer"},
    "pay_BOLETO":           {"pt": "Boleto",               "en": "Bank Slip"},
    "pay_CART\u00c3O DE CR\u00c9DITO": {"pt": "Cart\u00e3o de Cr\u00e9dito",    "en": "Credit Card"},
    "pay_PAYPAL":           {"pt": "PayPal",               "en": "PayPal"},
}

# Fixed inclusions — always shown in PDF
_INCLUSO = {
    "pt": [
        "Meet & Greet",
        "1 Hora de Espera após o pouso do vôo.",
        "Serviço de Bordo",
        "Pedágios e Combustível",
    ],
    "en": [
        "Meet & Greet",
        "1 Hour of Wait after flight landing.",
        "On-board Service",
        "Tolls and Fuel",
    ],
}

_INFO_ADICIONAL = {
    "pt": [
        "Hora Extra: 10% sobre o valor total da diária, a partir de 30 minutos de despera.",
    ],
    "en": [
        "Overtime: 10% of the total daily rate, after 30 minutes of waiting.",
    ],
}


def _t(key: str, lang: str) -> str:
    return _T.get(key, {}).get(lang, _T.get(key, {}).get("pt", key))


def _billing_label(billing_type: str, lang: str) -> str:
    return _t(f"billing_{billing_type}", lang)


def _fee_label(billing_type: str, lang: str) -> str:
    return _t(f"fee_{billing_type}", lang)


def _fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Translation helpers for English PDF (V2-style)
# ---------------------------------------------------------------------------
_VEHICLE_EN: dict[str, str] = {
    "sedan executivo":           "Executive Sedan",
    "sedan premium":             "Premium Sedan",
    "sedan blindado":            "Bulletproof Sedan",
    "sedan blindado premium":    "Bulletproof Premium Sedan",
    "suv executivo":             "Executive SUV",
    "suv executivo premium":     "Executive Premium SUV",
    "suv premium":               "Premium SUV",
    "suv blindado":              "Bulletproof SUV",
    "suv blindado premium":      "Bulletproof Premium SUV",
    "minivan executiva":          "Executive Minivan",
    "minivan executivo":          "Executive Minivan",
    "minivan executiva premium":  "Executive Premium Minivan",
    "minivan executivo premium":  "Executive Premium Minivan",
    "minivan premium":            "Premium Minivan",
    "minivan blindada":           "Bulletproof Minivan",
    "minivan blindado":           "Bulletproof Minivan",
    "minivan blindada premium":   "Bulletproof Premium Minivan",
    "minivan blindado premium":   "Bulletproof Premium Minivan",
    "van executiva":             "Executive Van",
    "van executivo":             "Executive Van",
    "van premium":               "Premium Van",
    "van blindada":              "Bulletproof Van",
    "van blindado":              "Bulletproof Van",
    "microônibus executivo":     "Executive Mini-Bus",
    "microonibus executivo":     "Executive Mini-Bus",
    "ônibus executivo":          "Executive Bus",
    "onibus executivo":          "Executive Bus",
    "motorista free lance":      "Freelance Driver",
}

_DRIVER_EN: dict[str, str] = {
    "bilíngue":             "Bilingual Driver",
    "bilingue":              "Bilingual Driver",
    "mono":                  "Monolingual Driver",
    "monolíngue":            "Monolingual Driver",
    "motorista bilíngue":    "Bilingual Driver",
    "motorista monolíngue":  "Monolingual Driver",
}

_DRIVER_PT: dict[str, str] = {
    "bilíngue":              "Motorista Bilíngue",
    "bilingue":               "Motorista Bilíngue",
    "mono":                   "Motorista Monolíngue",
    "monolíngue":             "Motorista Monolíngue",
    "motorista bilíngue":     "Motorista Bilíngue",
    "motorista monolíngue":   "Motorista Monolíngue",
}

_PAYMENT_TERMS_EN: dict[str, str] = {
    "à vista":               "Full Payment",
    "à vista + 1 parcela":   "Split into 2 payments",
    "5 dias":                "5 Days",
    "10 dias":               "10 Days",
    "15 dias":               "15 Days",
    "25 dias":               "25 Days",
    "30 dias":               "30 Days",
}

_VEHICLE_MODEL_PT: dict[str, str] = {
    "sedan executivo":           "Toyota Corolla ou Similar",
    "sedan blindado":            "Toyota Corolla ou Similar",
    "sedan premium":             "Mercedes Classe E ou Similar",
    "sedan blindado premium":    "Mercedes Classe E ou Similar",
    "suv executivo":             "Jeep Commander ou Similar",
    "suv executivo premium":     "Volvo XC 90 ou Similar",
    "suv premium":               "Volvo XC 90 ou Similar",
    "suv blindado":              "Jeep Commander ou Similar",
    "suv blindado premium":      "Volvo XC 90 ou Similar",
    "minivan executiva":          "Kia Carnival ou Similar",
    "minivan executivo":          "Kia Carnival ou Similar",
    "minivan executiva premium":  "Mercedes Vito ou Similar",
    "minivan executivo premium":  "Mercedes Vito ou Similar",
    "minivan premium":            "Mercedes Vito ou Similar",
    "minivan blindada":           "Kia Carnival ou Similar",
    "minivan blindado":           "Kia Carnival ou Similar",
    "minivan blindada premium":   "Mercedes Vito ou Similar",
    "minivan blindado premium":   "Mercedes Vito ou Similar",
    "van executiva":             "Mercedes Sprinter ou Similar",
    "van executivo":             "Mercedes Sprinter ou Similar",
    "van premium":               "Mercedes Sprinter ou Similar",
    "van blindada":              "Mercedes Sprinter ou Similar",
    "van blindado":              "Mercedes Sprinter ou Similar",
    "microônibus executivo":     "Micro Ônibus Executivo 30L",
    "microonibus executivo":     "Micro Ônibus Executivo 30L",
    "ônibus executivo":          "Ônibus Executivo 46L",
    "onibus executivo":          "Ônibus Executivo 46L",
}

_VEHICLE_MODEL_EN: dict[str, str] = {
    "sedan executivo":           "Toyota Corolla or Similar",
    "sedan blindado":            "Toyota Corolla or Similar",
    "sedan premium":             "Mercedes E Class or Similar",
    "sedan blindado premium":    "Mercedes E Class or Similar",
    "suv executivo":             "Jeep Commander or Similar",
    "suv executivo premium":     "Volvo XC 90 or Similar",
    "suv premium":               "Volvo XC 90 or Similar",
    "suv blindado":              "Jeep Commander or Similar",
    "suv blindado premium":      "Volvo XC 90 or Similar",
    "minivan executiva":          "Kia Carnival or Similar",
    "minivan executivo":          "Kia Carnival or Similar",
    "minivan executiva premium":  "Mercedes Vito or Similar",
    "minivan executivo premium":  "Mercedes Vito or Similar",
    "minivan premium":            "Mercedes Vito or Similar",
    "minivan blindada":           "Kia Carnival or Similar",
    "minivan blindado":           "Kia Carnival or Similar",
    "minivan blindada premium":   "Mercedes Vito or Similar",
    "minivan blindado premium":   "Mercedes Vito or Similar",
    "van executiva":             "Mercedes Sprinter or Similar",
    "van executivo":             "Mercedes Sprinter or Similar",
    "van premium":               "Mercedes Sprinter or Similar",
    "van blindada":              "Mercedes Sprinter or Similar",
    "van blindado":              "Mercedes Sprinter or Similar",
    "microônibus executivo":     "Executive Mini-Bus 30L",
    "microonibus executivo":     "Executive Mini-Bus 30L",
    "ônibus executivo":          "Executive Bus 46L",
    "onibus executivo":          "Executive Bus 46L",
}


def _swap_gender(k: str) -> str:
    """Swap gendered adjective suffix (o↔a) for fallback dict lookup."""
    _MAP = {
        "blindado": "blindada", "blindada": "blindado",
        "executivo": "executiva", "executiva": "executivo",
    }
    words = k.split()
    for i in range(len(words) - 1, -1, -1):
        if words[i] in _MAP:
            alt = words[:]
            alt[i] = _MAP[words[i]]
            return " ".join(alt)
    return k


def _get_vehicle_model(cat_name: str, lang: str) -> str:
    k = cat_name.strip().lower()
    d = _VEHICLE_MODEL_EN if lang == "en" else _VEHICLE_MODEL_PT
    return d.get(k) or d.get(_swap_gender(k), "")


def _translate_vehicle(name: str, lang: str) -> str:
    if lang == "pt" or not name:
        return name
    k = name.strip().lower()
    return _VEHICLE_EN.get(k) or _VEHICLE_EN.get(_swap_gender(k), name)


def _title_case(s: str) -> str:
    """Title-case: first letter of each word upper, rest lower."""
    return " ".join(w.capitalize() for w in s.split()) if s else s


def _translate_payment_terms(terms: str, lang: str) -> str:
    if lang == "pt" or not terms or terms == "–":
        return terms
    return _PAYMENT_TERMS_EN.get(terms.strip().lower(), terms)


def _translate_driver(driver_type: str, lang: str) -> str:
    if not driver_type:
        return driver_type
    key = driver_type.strip().lower()
    if lang == "pt":
        return _DRIVER_PT.get(key, driver_type)
    return _DRIVER_EN.get(key, driver_type)


def _translate_service(name: str, lang: str, vehicle: str = "") -> str:
    """Translate service name to English using V2-style regex transforms."""
    if lang == "pt" or not name:
        return name
    is_freelance = "free lance" in vehicle.lower() if vehicle else False
    v = re.sub(r"\bTransfer(?:\s+Airport)?\b", "Airport Transfer", name)
    if not is_freelance:
        v = re.sub(
            r"Di[aá]ria\s+0?5h\b(?:\s*\+\s*(\d+)\s*[Kk][Mm]\s*Franquia)?",
            lambda m: f"Disposal 5 Hours + {m.group(1) or '50'} Km Included",
            v, flags=re.IGNORECASE)
        v = re.sub(
            r"Di[aá]ria\s+10h\b(?:\s*\+\s*(\d+)\s*[Kk][Mm]\s*Franquia)?",
            lambda m: f"Disposal 10 Hours + {m.group(1) or '100'} Km Included",
            v, flags=re.IGNORECASE)
    v = re.sub(r"\s*\+\s*\d+\s*[Kk][Mm]\s*Franquia", "", v, flags=re.IGNORECASE)
    v = re.sub(r"\bDi[aá]ria\b", "Disposal", v)
    return v


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate_quote_pdf(quote, lang: str = "pt") -> io.BytesIO:
    """Return a BytesIO containing the PDF for the given quote."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"Orçamento {quote.number}",
    )

    W = A4[0] - 30 * mm   # usable width

    # ── Styles ────────────────────────────────────────────────────────────
    title_st  = ParagraphStyle("ts", fontSize=13, fontName="Helvetica-Bold",
                                textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=1)
    sub_st    = ParagraphStyle("ss", fontSize=9, fontName="Helvetica-Bold",
                                textColor=BRAND_GOLD, alignment=TA_CENTER, spaceAfter=6)
    normal    = ParagraphStyle("ns", fontSize=9,  textColor=BRAND_DARK, leading=13)
    small     = ParagraphStyle("sm", fontSize=8,  textColor=colors.HexColor("#666"), leading=11)
    italic_sm = ParagraphStyle("is", fontSize=7.5, fontName="Helvetica-Oblique",
                                textColor=colors.HexColor("#666"), leading=10)
    sec_hdr   = ParagraphStyle("sh", fontSize=9, fontName="Helvetica-Bold",
                                textColor=BRAND_DARK, leading=12, spaceBefore=3, spaceAfter=3)
    bullet_st = ParagraphStyle("bs", fontSize=8, textColor=BRAND_DARK, leading=12, leftIndent=8)
    ctr_sm    = ParagraphStyle("cs", fontSize=8, textColor=colors.HexColor("#666"),
                                alignment=TA_CENTER, leading=12)
    footer_st = ParagraphStyle("fs", fontSize=7.5, textColor=colors.HexColor("#666"),
                                alignment=TA_CENTER, leading=11)
    cell_hdr  = ParagraphStyle("ch", fontSize=8, fontName="Helvetica-Bold",
                                textColor=colors.white, leading=10, alignment=TA_CENTER)
    cell_hdr_l = ParagraphStyle("chl", parent=cell_hdr, alignment=TA_LEFT)
    cell_body  = ParagraphStyle("cb", fontSize=8, textColor=BRAND_DARK, leading=11)
    cell_body_c = ParagraphStyle("cbc", parent=cell_body, alignment=TA_CENTER)
    cell_body_r = ParagraphStyle("cbr", parent=cell_body, alignment=TA_RIGHT)
    cell_bold_r = ParagraphStyle("cbr2", fontSize=9, fontName="Helvetica-Bold",
                                  textColor=BRAND_DARK, alignment=TA_RIGHT, leading=11)

    story = []

    # ── Company header: logo centered (V2 style — no dark bar) ──────────────
    company      = getattr(quote, "company", None)
    company_name = (company.name if company else None) or "Executive Car SP"
    company_doc  = (company.document if company else None) or ""

    # Try to load company logo
    logo_url  = (company.logo_url if company else None) if company else None
    logo_img  = None
    if logo_url:
        try:
            from reportlab.platypus import Image as RLImage
            from flask import current_app
            logo_path = logo_url
            if logo_url.startswith("/uploads/"):
                logo_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    logo_url[len("/uploads/"):].lstrip("/")
                )
            elif logo_url.startswith("/static/"):
                logo_path = os.path.join(
                    current_app.root_path, "static",
                    logo_url[len("/static/"):].lstrip("/")
                )
            if os.path.isfile(logo_path):
                logo_img = RLImage(logo_path, width=9 * mm * 10, height=4.5 * mm * 10,
                                   kind="proportional")
        except Exception:
            logo_img = None

    if logo_img:
        hdr_tbl = Table([[logo_img]], colWidths=[W])
        hdr_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
    else:
        hdr_tbl = Table([[Paragraph(
            f"<b>{company_name.upper()}</b>",
            ParagraphStyle("hc", fontSize=18, fontName="Helvetica-Bold",
                           textColor=BRAND_DARK, alignment=TA_CENTER),
        )]], colWidths=[W])
        hdr_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Title + number ────────────────────────────────────────────────────
    story.append(Paragraph(_t("title", lang), title_st))
    story.append(Paragraph(f"No. {quote.number}", sub_st))
    story.append(Spacer(1, 4 * mm))

    # ── Client table ──────────────────────────────────────────────────────
    client_name  = (quote.client.name if quote.client else None) or quote.client_name or "–"
    contact_name = quote.contact_name or "–"
    email_str    = quote.email or (quote.client.email if quote.client else None) or "–"
    _cphn        = (quote.client.phone or getattr(quote.client, 'whatsapp', None)) if quote.client else None
    phone_str    = quote.phone or _cphn or "–"
    c_col_w = [W * 0.22, W * 0.20, W * 0.27, W * 0.17, W * 0.14]

    status_key = quote.status or "pendente"
    _status_bg, _status_fg = _STATUS_COLORS.get(status_key, _STATUS_COLORS["pendente"])
    client_status_style = ParagraphStyle("css", parent=cell_body_c,
                                          textColor=_status_fg, fontName="Helvetica-Bold")
    # Replace last cell in data row with correctly coloured text
    client_tbl_data = [
        [Paragraph(_t("company_col",  lang), cell_hdr),
         Paragraph(_t("contact_col",  lang), cell_hdr),
         Paragraph(_t("email_col",    lang), cell_hdr),
         Paragraph(_t("mobile_col",   lang), cell_hdr),
         Paragraph(_t("status_col",   lang), cell_hdr)],
        [Paragraph(_title_case(client_name),  cell_body_c),
         Paragraph(_title_case(contact_name), cell_body_c),
         Paragraph(email_str,    cell_body_c),
         Paragraph(phone_str,    cell_body_c),
         Paragraph(_t(f"status_{status_key}", lang), client_status_style)],
    ]
    client_tbl = Table(client_tbl_data, colWidths=c_col_w)
    client_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_DARK),
        ("BACKGROUND",    (0, 1), (-1, 1),  BRAND_LIGHT),
        ("BACKGROUND",    (4, 1), (4, 1),   _status_bg),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1),  "CENTER"),
    ]))
    story.append(client_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Items table ───────────────────────────────────────────────────────
    i_col_w = [W * 0.05, W * 0.51, W * 0.08, W * 0.17, W * 0.19]
    items_rows = [[
        Paragraph(_t("hash_col",     lang), cell_hdr_l),
        Paragraph(_t("service_col",  lang), cell_hdr),
        Paragraph(_t("qty_col",      lang), cell_hdr),
        Paragraph(_t("unit_col",     lang), cell_hdr),
        Paragraph(_t("total_col",    lang), cell_hdr),
    ]]

    grand_total = 0.0
    for idx, it in enumerate(sorted(quote.items, key=lambda x: x.sort_order or 0), 1):
        # --- Resolve names ---------------------------------------------------
        service_name_raw = (it.service.name if it.service else None) or it.description or "–"
        driver_type_raw  = it.driver_name or ""  # stored as Bilíngue/Monolíngue
        vehicle_desc     = it.vehicle_description or ""
        ref_note         = it.ref_note or ""

        # Resolve category name via relationship (with fallback)
        cat_obj  = getattr(it, "category", None)
        if cat_obj is None and it.category_id:
            try:
                from ..models.vehicle import VehicleCategory as _VC
                cat_obj = _VC.query.get(it.category_id)
            except Exception:
                cat_obj = None
        cat_name_raw = (cat_obj.name if cat_obj else "") or ""

        # Apply English translations
        service_name_disp = _translate_service(service_name_raw, lang, cat_name_raw)
        cat_name_disp     = _translate_vehicle(cat_name_raw,  lang)
        driver_disp       = _translate_driver(driver_type_raw, lang)

        # Build service cell
        # Line 1 (bold): ref_note + service name
        main_parts = []
        if ref_note:
            main_parts.append(ref_note)
        main_parts.append(service_name_disp)
        main_label = " – ".join(main_parts)

        # Line 2: category + driver (smaller, dark)
        sub_parts = []
        if cat_name_disp:
            sub_parts.append(cat_name_disp)
        if driver_disp:
            sub_parts.append(driver_disp)
        sub_label = " – ".join(sub_parts)

        # Line 3: vehicle model from mapping, fallback to vehicle_desc
        vehicle_model = _get_vehicle_model(cat_name_raw, lang) or vehicle_desc

        svc_lines = [f'<b>{main_label}</b>']
        if sub_label:
            svc_lines.append(f'<font color="#334155" size="7.5">{sub_label}</font>')
        if vehicle_model:
            svc_lines.append(f'<font color="#888888" size="7"><i>{vehicle_model}</i></font>')
        svc_para = Paragraph("<br/>".join(svc_lines), cell_body)

        qty     = it.quantity or 1
        price   = it.unit_price or 0
        total    = it.total_price or round(price * qty, 2)
        grand_total += total

        items_rows.append([
            Paragraph(str(idx),                  cell_body_c),
            svc_para,
            Paragraph(str(qty),                  cell_body_c),
            Paragraph(_fmt_brl(price),           cell_body_r),
            Paragraph(_fmt_brl(total),           cell_body_r),
        ])

    items_tbl = Table(items_rows, colWidths=i_col_w, repeatRows=1)
    items_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_DARK),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        # All cells: MIDDLE + CENTER
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        # Service column (1): TOP + LEFT for data rows
        ("VALIGN",        (1, 1), (1, -1),  "TOP"),
        ("ALIGN",         (1, 0), (1, -1),  "LEFT"),
    ])
    for row_idx in range(1, len(items_rows)):
        bg = BRAND_LIGHT if row_idx % 2 == 1 else colors.white
        items_style.add("BACKGROUND", (0, row_idx), (-1, row_idx), bg)
    items_tbl.setStyle(items_style)
    story.append(items_tbl)

    # ── Summary row: payment method | fiscal billing | total ─────────────────
    billing_label = _billing_label(quote.billing_type or "recibo", lang)
    # Show payment method (PIX / DINHEIRO / etc.) if available
    pay_method       = (quote.payment_method or "").strip()
    pay_method_upper = pay_method.upper()
    pay_method_lbl   = _t(f"pay_{pay_method_upper}", lang) if pay_method_upper else ""
    # If no translation found, fall back to the raw value
    if pay_method_lbl == f"pay_{pay_method_upper}":
        pay_method_lbl = pay_method or "–"
    # Fiscal billing: just the label (Recibo / Nota Fiscal) — no fee text
    fiscal_cell_text  = billing_label
    payment_cell_text = pay_method_lbl if pay_method_lbl else "–"
    prazo_cell_text   = _translate_payment_terms((quote.payment_terms or "–").strip(), lang)
    summary_tbl = Table(
        [
            [Paragraph(_t("payment_col",     lang), cell_hdr),
             Paragraph(_t("included_col",    lang), cell_hdr),
             Paragraph(_t("prazo_col",       lang), cell_hdr),
             Paragraph(_t("total_price_col", lang), cell_hdr)],
            [Paragraph(_title_case(payment_cell_text), cell_body_c),
             Paragraph(_title_case(fiscal_cell_text),   cell_body_c),
             Paragraph(_title_case(prazo_cell_text),    cell_body_c),
             Paragraph(_fmt_brl(grand_total), cell_bold_r)],
        ],
        colWidths=[W * 0.27, W * 0.27, W * 0.24, W * 0.22],
    )
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_DARK),
        ("BACKGROUND",    (0, 1), (-1, 1),  BRAND_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 5 * mm))

    # ── Two-column: Included Services | Important Information ─────────────
    incluso_list = _INCLUSO.get(lang, _INCLUSO["pt"])
    info_list    = list(_INFO_ADICIONAL.get(lang, _INFO_ADICIONAL["pt"]))

    def _make_col(header: str, items: list) -> list:
        col = [Paragraph(f"<b>{header}</b>", sec_hdr)]
        for item in items:
            col.append(Paragraph(f"• {item}", bullet_st))
        return col

    left_col  = _make_col(_t("incluso_hdr", lang), incluso_list)
    right_col = _make_col(_t("info_hdr",    lang), info_list)

    # Pad to equal row count
    max_rows = max(len(left_col), len(right_col))
    while len(left_col)  < max_rows: left_col.append(Spacer(1, 1))
    while len(right_col) < max_rows: right_col.append(Spacer(1, 1))

    two_col_rows = [[left_col[i], right_col[i]] for i in range(max_rows)]
    two_col_tbl = Table(two_col_rows,
                        colWidths=[W * 0.5 - 2 * mm, W * 0.5 - 2 * mm],
                        style=TableStyle([
                            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING",   (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING",(0, 0), (-1, -1), 1),
                            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ]))
    story.append(two_col_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Additional info (obs) ─────────────────────────────────────────────
    story.append(Paragraph(f"<b>{_t('add_info', lang)}:</b>", sec_hdr))
    obs = quote.obs or getattr(quote, "notes", None)
    if obs:
        for line in obs.splitlines():
            story.append(Paragraph(line if line.strip() else "&nbsp;", normal))
    else:
        story.append(Spacer(1, 3 * mm))

    # ── Cancellation policy ────────────────────────────────────────
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width=W, thickness=0.5,
                             color=colors.HexColor("#cccccc"), spaceAfter=3 * mm))
    story.append(Paragraph(f"<b>{_t('cancel_policy', lang)}</b>", sec_hdr))
    story.append(Paragraph(_t("cancel_intro", lang), normal))
    for k in ("cancel_72", "cancel_48", "cancel_24"):
        story.append(Paragraph(f"  • {_t(k, lang)}", bullet_st))
    story.append(Spacer(1, 4 * mm))

    # ── Approve / Questions / Decline ─────────────────────────────────────
    act_tbl = Table([[
        Paragraph(f'<font color="#2e7d32"><b>{_t("approve",    lang)}</b></font>',
                  ParagraphStyle("a1", fontSize=11, alignment=TA_CENTER, leading=14)),
        Paragraph(f'<font color="#1565c0"><b>{_t("questions",  lang)}</b></font>',
                  ParagraphStyle("a2", fontSize=11, alignment=TA_CENTER, leading=14)),
        Paragraph(f'<font color="#c62828"><b>{_t("decline",    lang)}</b></font>',
                  ParagraphStyle("a3", fontSize=11, alignment=TA_CENTER, leading=14)),
    ]], colWidths=[W / 3, W / 3, W / 3])
    act_tbl.setStyle(TableStyle([
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(act_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Validity (below action buttons) ─────────────────────────────────────
    story.append(Paragraph(_t("validity", lang), ctr_sm))

    # ── Footer as page callback (always at physical bottom) ───────────────
    now_str  = datetime.now().strftime("%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
    tax_part = f"{company_name} \u2022 {_t('tax_id', lang)} {company_doc}" if company_doc else company_name
    _footer_line = f"{_t('generated', lang)} {now_str}   \u2022   {tax_part}"
    _lm, _rm, _pw = 15 * mm, A4[0] - 15 * mm, A4[0]

    def _draw_footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cccccc"))
        canvas.setLineWidth(0.5)
        canvas.line(_lm, 14 * mm, _rm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(_pw / 2, 9 * mm, _footer_line)
        canvas.restoreState()

    # ── Build PDF ─────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer
