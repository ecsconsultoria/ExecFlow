"""receipt_pdf.py — PDF generator for Payment Receipts (Recibos de Pagamento).

Same visual identity as the Sales Order PDF (order_pdf.py): preto/branco/dourado,
cabeçalhos escuros, bordas douradas, ReportLab platypus. Documento financeiro
mais enxuto — somente leitura, não gera nenhum lançamento.

- build_receipt_context() — função pura que monta o snapshot de dados (testável)
- generate_receipt_pdf()   — monta o PDF em 1 página A4 (PT/EN)
"""
from __future__ import annotations

import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Re-use brand constants and helpers from quote_pdf (mesma família visual do SO)
from .quote_pdf import (
    BRAND_DARK,
    BRAND_GOLD,
    BRAND_LIGHT,
    BRAND_GREEN,
    BRAND_RED,
    BRAND_BLUE,
    _T as _QT,
    _fmt_brl,
    _fmt_usd_raw,
    _fmt_phone_link,
    _translate_service,
    _translate_vehicle,
    _translate_driver,
    _get_vehicle_model,
)
from .order_pdf import _fmt_date, _fmt_datetime
from ..utils import now_br

# Extra receipt-specific translations merged into a local dict
_T: dict[str, dict[str, str]] = {
    **_QT,
    "receipt_title":      {"pt": "RECIBO DE PAGAMENTO",      "en": "PAYMENT RECEIPT"},
    "receipt_no":         {"pt": "Nº RECIBO",                "en": "RECEIPT NO."},
    "issue_date":         {"pt": "DATA DE EMISSÃO",          "en": "ISSUE DATE"},
    "sales_order":        {"pt": "PEDIDO DE VENDA",          "en": "SALES ORDER"},
    "order_date":         {"pt": "DATA DO PEDIDO",           "en": "ORDER DATE"},
    "customer_hdr":       {"pt": "DADOS DO CLIENTE",         "en": "CUSTOMER INFORMATION"},
    "payment_info_hdr":   {"pt": "DADOS DO PAGAMENTO",       "en": "PAYMENT INFORMATION"},
    "installment_word":   {"pt": "Parcela",                  "en": "Installment"},
    "reference_lbl":      {"pt": "REFERÊNCIA",               "en": "PAYMENT REFERENCE"},
    "paid_on_lbl":        {"pt": "DATA DO PAGAMENTO",        "en": "PAYMENT DATE"},
    "method_lbl":         {"pt": "FORMA DE PAGAMENTO",       "en": "PAYMENT METHOD"},
    "payment_type_lbl":   {"pt": "TIPO DE PAGAMENTO",        "en": "PAYMENT TYPE"},
    "amount_paid_lbl":    {"pt": "VALOR PAGO",               "en": "AMOUNT PAID"},
    "type_final":         {"pt": "Pagamento Final",          "en": "Final Payment"},
    "type_full":          {"pt": "Pagamento Único",          "en": "Full Payment"},
    "service_hdr":        {"pt": "DADOS DO SERVIÇO",         "en": "SERVICE INFORMATION"},
    "service_lbl":        {"pt": "SERVIÇO",                  "en": "SERVICE"},
    "vehicle_lbl":        {"pt": "VEÍCULO",                  "en": "VEHICLE"},
    "driver_lbl":         {"pt": "MOTORISTA",                "en": "DRIVER"},
    "service_date_lbl":   {"pt": "DATA DO SERVIÇO",          "en": "SERVICE DATE"},
    "summary_hdr":        {"pt": "RESUMO DO PAGAMENTO",      "en": "PAYMENT SUMMARY"},
    "total_amount":       {"pt": "VALOR TOTAL DO CONTRATO",  "en": "TOTAL CONTRACT VALUE"},
    "previously_paid":    {"pt": "VALOR JÁ PAGO",            "en": "PREVIOUSLY PAID"},
    "received":           {"pt": "PAGAMENTO RECEBIDO",       "en": "PAYMENT RECEIVED"},
    "outstanding":        {"pt": "SALDO PENDENTE",           "en": "OUTSTANDING BALANCE"},
    "status_hdr":         {"pt": "STATUS DO PAGAMENTO",      "en": "PAYMENT STATUS"},
    "status_paid_short":  {"pt": "PAGO",                     "en": "PAID"},
    "status_paid_full":   {"pt": "PAGO INTEGRALMENTE",       "en": "PAID IN FULL"},
    "confirmation":       {"pt": "Este recibo confirma que o pagamento descrito acima "
                                  "foi recebido pela Executive Car SP.",
                           "en": "This receipt confirms that the payment described above "
                                 "has been received by Executive Car SP."},
    "company_hdr":        {"pt": "EXECUTIVE CAR SP",         "en": "EXECUTIVE CAR SP"},
    "tagline":            {"pt": "Transporte Executivo",     "en": "Executive Transportation"},
    "website_lbl":        {"pt": "SITE",                     "en": "WEBSITE"},
    "office_lbl":         {"pt": "TELEFONE",                 "en": "OFFICE"},
    "whatsapp_lbl":       {"pt": "WHATSAPP",                 "en": "WHATSAPP"},
    "generated":          {"pt": "GERADO EM",                "en": "GENERATED ON"},
}


def _t(key: str, lang: str) -> str:
    entry = _T.get(key, {})
    return entry.get(lang) or entry.get("pt") or key


def _fmt_whatsapp(raw: str) -> str:
    """Formata o número do WhatsApp da config (ex: 5511989178312 → +55 (11) 9.8917-8312)."""
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if len(digits) == 13 and digits.startswith("55"):
        return f"+{digits[0:2]} ({digits[2:4]}) {digits[4]}.{digits[5:9]}-{digits[9:]}"
    return raw or "–"


def _amount_cell(brl_value: float, usd_rate, color, bold: bool = True,
                 align=TA_RIGHT) -> Paragraph:
    """Célula de valor: R$ em negrito + USD em cinza quando há cotação (padrão do SO)."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    st = ParagraphStyle(
        "amt_cell", fontSize=9, fontName=font, textColor=color,
        alignment=align, leading=11,
    )
    base = _fmt_brl(brl_value)
    if usd_rate and usd_rate > 0:
        usd_val = brl_value / usd_rate
        return Paragraph(
            f"{base}<br/><font color='#888888' size='7'>USD {_fmt_usd_raw(usd_val)}</font>", st
        )
    return Paragraph(base, st)


def _esc(text: str) -> str:
    """Escapa texto vindo do banco para uso em marcação de parágrafo."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lv_cell(label: str, value: str, style: ParagraphStyle) -> Paragraph:
    """Célula label/valor em duas linhas — valores alinhados à esquerda em grid."""
    return Paragraph(
        f"<font size='7' color='#64748b'><b>{_esc(label)}</b></font><br/>{value}",
        style,
    )


def build_receipt_context(order, payment, lang: str = "pt") -> dict:
    """Snapshot puro dos dados do recibo — sem ReportLab, testável.

    Fonte de verdade: OrderPayment (paid_amount/paid_at) + espelho Financeiro
    (FinancialRecord com reference="order_payment:{id}"). Nada é recalculado
    historicamente; USD deriva de order.usd_rate (convenção do SO).
    """
    from ..models.financial import FinancialRecord

    total_inst = len(order.payments)
    fr = (FinancialRecord.query
          .filter_by(company_id=order.company_id, reference=f"order_payment:{payment.id}")
          .filter(FinancialRecord.deleted_at.is_(None))
          .first())
    method  = (fr.payment_method if fr and fr.payment_method else (order.payment_method or ""))
    paid_on = payment.paid_at or (fr.paid_date if fr else None)

    total       = round(order.computed_total or 0, 2)
    received    = round(payment.paid_amount or 0, 2)
    # "Valor já pago" = parcelas pagas ANTES desta (posição por installment_no).
    # Saldo = posição do contrato APÓS este pagamento — recibo da 1ª parcela
    # mostra o saldo restante mesmo que o SO já esteja 100% quitado.
    inst_no     = payment.installment_no or 0
    previously  = round(sum((p.paid_amount or 0) for p in order.payments
                            if (p.installment_no or 0) < inst_no), 2)
    outstanding = round(total - previously - received, 2)
    is_final    = outstanding <= 0
    usd_rate    = getattr(order, "usd_rate", None)

    # Tipo de pagamento
    if is_final and total_inst == 1:
        ptype = _t("type_full", lang)
    elif is_final:
        ptype = _t("type_final", lang)
    else:
        sep = " de " if lang == "pt" else " of "
        ptype = f"{_t('installment_word', lang)} {payment.installment_no}{sep}{total_inst}"

    items = sorted(order.items, key=lambda it: (it.sort_order or 0, it.id))
    first = items[0] if items else None

    service_parts = []
    for it in items:
        cat = (it.category.name if it.category else "") or ""
        service_parts.append(_translate_service(it.description or "–", lang, cat))
    service_summary = "<br/>".join(service_parts) or "–"

    inst_sep = " de " if lang == "pt" else " of "
    reference = (f"{order.number} / {_t('installment_word', lang)} "
                 f"{payment.installment_no}{inst_sep}{total_inst}")

    # Veículo: orders.vehicle_model → vehicle_description do 1º item →
    # modelo derivado da categoria (mesma regra do PDF do SO)
    vehicle_raw = (order.vehicle_model
                   or (first.vehicle_description if first else "")
                   or "").strip()
    first_cat = (first.category.name if first and first.category else "") or ""
    vehicle_disp = (vehicle_raw
                    or (_get_vehicle_model(first_cat, lang) if first_cat else "")
                    or (_translate_vehicle(first_cat, lang) if first_cat else "")
                    or "–")

    # Motorista: orders.driver_name → driver_name do item, traduzido (PT/EN)
    driver_raw = ((order.driver_name or "").strip()
                  or next(((it.driver_name or "").strip() for it in items
                           if (it.driver_name or "").strip()), ""))
    driver_disp = _translate_driver(driver_raw, lang) if driver_raw else "–"

    cli = order.client
    return {
        "lang": lang,
        "receipt_number": "",   # preenchido por generate_receipt_pdf
        "issued_at": None,      # preenchido por generate_receipt_pdf
        "customer": {
            "name":    ((cli.name if cli and cli.name else order.client_name)) or "–",
            "contact": ((cli.contact if cli and cli.contact else order.contact_name)) or "–",
            "email":   ((cli.email if cli and cli.email else order.email)) or "–",
            "phone":   ((cli.whatsapp if cli and cli.whatsapp else
                         ((cli.phone if cli else None) or getattr(order, "celular", None)
                          or order.phone))) or "–",
        },
        "payment": {
            "installment_no":    payment.installment_no,
            "total_installments": total_inst,
            "reference":         reference,
            "due_date":          payment.due_date,
            "paid_on":           paid_on,
            "method":            method or "–",
            "payment_type":      ptype,
            "amount":            received,
        },
        "service": {
            "order_number": order.number,
            "order_date":   order.emission_date,
            "summary":      service_summary,
            "vehicle":      vehicle_disp,
            "driver":       driver_disp,
            "service_date": (first.service_date if first else None),
        },
        "summary": {
            "total":       total,
            "previously":  previously,
            "received":    received,
            "outstanding": outstanding,
            "is_final":    is_final,
            "usd_rate":    usd_rate,
        },
        "status": {
            "key":   "paid_in_full" if is_final else "paid",
            "label": _t("status_paid_full" if is_final else "status_paid_short", lang),
        },
        "company": {
            "name":     (order.company.name if order.company else None) or "Executive Car SP",
            "document": (order.company.document if order.company else None) or "",
            "email":    (order.company.email if order.company else None) or "–",
            "phone":    (order.company.phone if order.company else None) or "–",
        },
    }


def generate_receipt_pdf(order, payment, receipt_number: str, lang: str = "pt",
                         canvasmaker=None) -> io.BytesIO:
    """Return a BytesIO containing the Payment Receipt PDF (1 página A4)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"{_t('receipt_title', lang)} {receipt_number}",
    )

    W = A4[0] - 30 * mm

    # ── Styles (mesma família do SO) ────────────────────────────────────────
    title_st    = ParagraphStyle("ts", fontSize=13, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=1)
    normal      = ParagraphStyle("ns", fontSize=9, textColor=BRAND_DARK, leading=13)
    small       = ParagraphStyle("sm", fontSize=8, textColor=colors.HexColor("#666"), leading=11)
    sec_hdr     = ParagraphStyle("sh", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, leading=12, spaceBefore=3, spaceAfter=3)
    cell_hdr    = ParagraphStyle("ch", fontSize=7, fontName="Helvetica-Bold",
                                 textColor=colors.white, leading=10, alignment=TA_CENTER)
    cell_body   = ParagraphStyle("cb", fontSize=8, textColor=BRAND_DARK, leading=11)
    cell_body_c = ParagraphStyle("cbc", parent=cell_body, alignment=TA_CENTER)
    cell_body_r = ParagraphStyle("cbr", parent=cell_body, alignment=TA_RIGHT)
    cell_bold_r = ParagraphStyle("cbr2", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, alignment=TA_RIGHT, leading=11)
    lbl_st      = ParagraphStyle("lbl", fontSize=8, fontName="Helvetica-Bold",
                                 textColor=colors.HexColor("#64748b"), leading=11)
    val_st      = ParagraphStyle("val", fontSize=8, textColor=BRAND_DARK, leading=11)
    status_st   = ParagraphStyle("sst", fontSize=11, fontName="Helvetica-Bold",
                                 textColor=colors.white, alignment=TA_CENTER, leading=14)
    conf_st     = ParagraphStyle("cfs", fontSize=8, textColor=BRAND_GREEN,
                                 alignment=TA_CENTER, leading=11)

    ctx = build_receipt_context(order, payment, lang)
    ctx["receipt_number"] = receipt_number
    ctx["issued_at"] = now_br()  # data de emissão = data/hora real da geração

    # Dados públicos da empresa (config) — sem inventar dados do cliente
    from flask import current_app
    try:
        ctx["company"]["website"]  = current_app.config.get("COMPANY_WEBSITE", "www.executivecarsp.com")
        ctx["company"]["whatsapp"] = _fmt_whatsapp(current_app.config.get("WPP_NUMBER", ""))
    except RuntimeError:
        ctx["company"]["website"]  = "www.executivecarsp.com"
        ctx["company"]["whatsapp"] = "–"

    story = []

    # ── Header: logo left + title/number right (padrão do SO) ───────────────
    company      = getattr(order, "company", None)
    company_name = ctx["company"]["name"]
    company_doc  = ctx["company"]["document"]

    logo_img = None
    if company and company.logo_url:
        try:
            from reportlab.platypus import Image as RLImage
            logo_path = company.logo_url
            if logo_path.startswith("/uploads/"):
                logo_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    logo_path[len("/uploads/"):].lstrip("/")
                )
            elif logo_path.startswith("/static/"):
                logo_path = os.path.join(
                    current_app.root_path, "static",
                    logo_path[len("/static/"):].lstrip("/")
                )
            if os.path.isfile(logo_path):
                logo_img = RLImage(logo_path, width=100 * mm, height=20 * mm, kind="proportional")
        except Exception:
            logo_img = None

    left_cell = logo_img if logo_img else Paragraph(
        f"<b>{company_name.upper()}</b>",
        ParagraphStyle("hc", fontSize=12, fontName="Helvetica-Bold",
                       textColor=BRAND_DARK, alignment=TA_LEFT))
    right_cell = Paragraph(
        f"<b>{_t('receipt_title', lang)}</b><br/>"
        f"<font color='#b88b2d' size='9'><b>No. {receipt_number}</b></font>",
        ParagraphStyle("hr", fontSize=13, fontName="Helvetica-Bold",
                       textColor=BRAND_DARK, alignment=TA_RIGHT, leading=18))

    hdr_tbl = Table([[left_cell, right_cell]], colWidths=[W * 0.55, W * 0.45])
    hdr_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Meta do recibo (dark header + gold borders) ─────────────────────────
    status_hex = "#2e7d32" if ctx["status"]["key"] == "paid_in_full" else "#1565c0"
    meta_labels = [
        _t("receipt_no", lang),
        _t("issue_date", lang),
        _t("sales_order", lang),
        _t("order_date", lang),
        _t("status_hdr", lang),
    ]
    meta_values = [
        ctx["receipt_number"],
        _fmt_date(ctx["issued_at"], lang),
        order.number,
        _fmt_date(order.emission_date, lang),
        f'<font color="{status_hex}"><b>{ctx["status"]["label"]}</b></font>',
    ]
    meta_tbl = Table(
        [[Paragraph(h, cell_hdr) for h in meta_labels],
         [Paragraph(v, cell_body_c) for v in meta_values]],
        colWidths=[W * 0.18, W * 0.17, W * 0.20, W * 0.17, W * 0.28],
    )
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("BACKGROUND",    (0, 1), (-1, 1), BRAND_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── CUSTOMER INFORMATION (mesma tabela de cliente do SO) ────────────────
    story.append(Paragraph(_t("customer_hdr", lang), sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    client_tbl = Table(
        [[Paragraph(_t("company_col", lang), cell_hdr),
          Paragraph(_t("contact_col", lang), cell_hdr),
          Paragraph(_t("email_col",   lang), cell_hdr),
          Paragraph(_t("mobile_col",  lang), cell_hdr)],
         [Paragraph(ctx["customer"]["name"].replace('\xa0', ' '),    cell_body_c),
          Paragraph(ctx["customer"]["contact"].replace('\xa0', ' '), cell_body_c),
          Paragraph(ctx["customer"]["email"].replace('\xa0', ' '),   cell_body_c),
          Paragraph(ctx["customer"]["phone"].replace('\xa0', ' '),   cell_body_c)]],
        colWidths=[W * 0.28, W * 0.24, W * 0.30, W * 0.18],
    )
    client_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("BACKGROUND",    (0, 1), (-1, 1), BRAND_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(client_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── PAYMENT INFORMATION (label/valor) ───────────────────────────────────
    story.append(Paragraph(_t("payment_info_hdr", lang), sec_hdr))

    method_raw = (ctx["payment"]["method"] or "").strip()
    method_key = method_raw.upper()
    method_lbl = _t(f"pay_{method_key}", lang)
    if method_lbl == f"pay_{method_key}":
        method_lbl = method_raw or "–"

    paid_on_val = _fmt_datetime(ctx["payment"]["paid_on"], lang)
    pay_rows = [
        (_t("reference_lbl",    lang), _esc(ctx["payment"]["reference"])),
        (_t("paid_on_lbl",      lang), paid_on_val),
        (_t("method_lbl",       lang), _esc(method_lbl)),
        (_t("payment_type_lbl", lang), _esc(ctx["payment"]["payment_type"])),
    ]
    pay_tbl_data = [
        [Paragraph(f"<b>{lbl}:</b>", lbl_st), Paragraph(val, val_st)]
        for lbl, val in pay_rows
    ]
    # Valor pago alinhado à esquerda como os demais campos (não à direita)
    pay_tbl_data.append(
        [Paragraph(f"<b>{_t('amount_paid_lbl', lang)}:</b>", lbl_st),
         _amount_cell(ctx["payment"]["amount"], ctx["summary"]["usd_rate"],
                      BRAND_DARK, align=TA_LEFT)])
    pay_tbl = Table(pay_tbl_data, colWidths=[W * 0.32, W * 0.68])
    pay_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (0, -1), "LEFT"),
    ]))
    story.append(pay_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── SERVICE INFORMATION (compacto, 4 colunas label: valor) ──────────────
    story.append(Paragraph(_t("service_hdr", lang), sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    svc = ctx["service"]
    svc_cells = [
        _lv_cell(_t("sales_order", lang), _esc(svc["order_number"]), val_st),
        _lv_cell(_t("service_lbl", lang), svc["summary"], val_st),
        _lv_cell(_t("vehicle_lbl", lang), _esc(svc["vehicle"]), val_st),
        _lv_cell(_t("driver_lbl", lang), _esc(svc["driver"]), val_st),
        _lv_cell(_t("service_date_lbl", lang),
                 _fmt_date(svc["service_date"], lang), val_st),
    ]
    while len(svc_cells) % 4 != 0:
        svc_cells.append(Paragraph("", val_st))
    svc_rows = [svc_cells[i:i + 4] for i in range(0, len(svc_cells), 4)]
    svc_tbl = Table(svc_rows, colWidths=[W / 4] * 4)
    svc_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(svc_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── PAYMENT SUMMARY (destaque) ──────────────────────────────────────────
    story.append(Paragraph(_t("summary_hdr", lang), sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    s = ctx["summary"]
    outstanding_color = BRAND_GREEN if s["outstanding"] <= 0 else BRAND_RED
    sum_tbl = Table(
        [
            [Paragraph(_t("total_amount",    lang), cell_hdr),
             Paragraph(_t("previously_paid", lang), cell_hdr),
             Paragraph(_t("received",        lang), cell_hdr),
             Paragraph(_t("outstanding",     lang), cell_hdr)],
            [_amount_cell(s["total"], s["usd_rate"], BRAND_DARK),
             _amount_cell(s["previously"], s["usd_rate"], BRAND_DARK, bold=False),
             _amount_cell(s["received"], s["usd_rate"], BRAND_GOLD),
             _amount_cell(s["outstanding"], s["usd_rate"], outstanding_color)],
        ],
        colWidths=[W * 0.27, W * 0.23, W * 0.25, W * 0.25],
    )
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("BACKGROUND",    (0, 1), (-1, 1), BRAND_LIGHT),
        ("BACKGROUND",    (2, 1), (2, 1), colors.HexColor("#fff8e1")),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── PAYMENT STATUS (faixa de destaque) ──────────────────────────────────
    status_tbl = Table([[Paragraph(ctx["status"]["label"], status_st)]], colWidths=[W])
    status_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(status_tbl)
    if s["is_final"]:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(_t("confirmation", lang), conf_st))
    story.append(Spacer(1, 4 * mm))

    # ── Dados da empresa ────────────────────────────────────────────────────
    comp = ctx["company"]
    comp_rows = [
        [
            _lv_cell(_t("tax_id", lang),      _esc(comp["document"] or "–"), val_st),
            _lv_cell(_t("website_lbl", lang), _esc(comp["website"]),         val_st),
            _lv_cell(_t("email_col", lang),   _esc(comp["email"]),           val_st),
            _lv_cell(_t("office_lbl", lang),  _esc(comp["phone"]),           val_st),
        ],
        [
            _lv_cell(_t("whatsapp_lbl", lang), _esc(comp["whatsapp"]), val_st),
            Paragraph("", val_st), Paragraph("", val_st), Paragraph("", val_st),
        ],
    ]
    comp_tbl = Table(comp_rows, colWidths=[W / 4] * 4)
    comp_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(comp_tbl)

    # ── Footer as page callback (padrão do SO, em 2 linhas curtas) ───────────
    cnpj_lbl_footer = "CNPJ" if lang == "pt" else "TAX ID"
    now_str = now_br().strftime("%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
    tagline = _t("tagline", lang)
    # Linha 1: nome da empresa em negrito + tagline + CNPJ (sem repetir o nome)
    _footer_tail = f" • {tagline}"
    if company_doc:
        _footer_tail += f" • {cnpj_lbl_footer} {company_doc}"
    _footer_parts = [
        (company_name.upper(), "Helvetica-Bold", 7.5),
        (_footer_tail, "Helvetica", 7.5),
    ]
    _footer_line2 = f"{_t('generated', lang)} {now_str}"
    _lm, _rm, _pw = 15 * mm, A4[0] - 15 * mm, A4[0]

    from reportlab.pdfbase.pdfmetrics import stringWidth

    def _draw_footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cccccc"))
        canvas.setLineWidth(0.5)
        canvas.line(_lm, 14 * mm, _rm, 14 * mm)
        canvas.setFillColor(colors.HexColor("#666666"))
        # Linha 1 centralizada com o nome da empresa em negrito
        total_w = sum(stringWidth(t, f, s) for t, f, s in _footer_parts)
        x = (_pw - total_w) / 2
        for text, font, size in _footer_parts:
            canvas.setFont(font, size)
            canvas.drawString(x, 10.5 * mm, text)
            x += stringWidth(text, font, size)
        # Linha 2
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(_pw / 2, 6.5 * mm, _footer_line2)
        canvas.restoreState()

    # ReportLab 4.x: canvasmaker é parâmetro do build(), não do SimpleDocTemplate
    build_kwargs = {"onFirstPage": _draw_footer, "onLaterPages": _draw_footer}
    if canvasmaker is not None:
        build_kwargs["canvasmaker"] = canvasmaker
    doc.build(story, **build_kwargs)
    buffer.seek(0)
    return buffer
