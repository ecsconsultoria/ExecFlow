"""PDF generator for Orders (Pedidos) — Portuguese and English versions."""
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
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Re-use brand constants from quote_pdf
from .quote_pdf import (
    BRAND_DARK,
    BRAND_GOLD,
    BRAND_LIGHT,
    SITE_URL,
    SITE_ICON,
    _app_base_url,
    _register_web_font,
    _T as _QT,
    _billing_label,
    _fmt_brl,
    _fmt_phone_link,
    _fmt_time_12h,
    _fmt_usd_raw,
    _sanitize_phone,
    _total_cell_text,
    _total_cell_aligned,
    _PAYMENT_TERMS_EN,
    _translate_payment_terms,
    _translate_service,
    _translate_vehicle,
    _translate_driver,
    _get_vehicle_model,
)

# Extra order-specific translations merged into a local dict
_T: dict[str, dict[str, str]] = {
    **_QT,
    "order_title":      {"pt": "PEDIDO DE VENDA",          "en": "SALES ORDER"},
    "order_no":         {"pt": "Nº Pedido",                "en": "Order No."},
    "emission":         {"pt": "DATA DE EMISSÃO",          "en": "ISSUE DATE"},
    "delivery":         {"pt": "DATA DE ENTREGA",          "en": "DELIVERY DATE"},
    "subtotal":         {"pt": "SUBTOTAL",                 "en": "SUBTOTAL"},
    "discount":         {"pt": "DESCONTO",                 "en": "DISCOUNT"},
    "freight":          {"pt": "FRETE",                    "en": "FREIGHT"},
    "other_costs":      {"pt": "CUSTOS EXTRAS",            "en": "EXTRA COSTS"},
    "final_total":      {"pt": "TOTAL FINAL",              "en": "TOTAL AMOUNT"},
    "payment_hdr":      {"pt": "PAGAMENTO",                "en": "PAYMENT"},
    "installment_no":   {"pt": "PARCELA",                  "en": "INSTALLMENT"},
    "due_date":         {"pt": "VENCIMENTO",               "en": "DUE DATE"},
    "amount_col":       {"pt": "VALOR PARCELA",             "en": "AMOUNT"},
    "subtotal_col":     {"pt": "SUBTOTAL",                 "en": "SUBTOTAL"},
    # Sobrescreve os rotulos do quote_pdf para a tabela unica de pagamento
    "included_col":     {"pt": "FATURAMENTO",              "en": "INVOICE"},
    "prazo_col":        {"pt": "PRAZO PAGAMENTO",          "en": "PAYMENT TERMS"},
    "grand_total_lbl":  {"pt": "PREÇO TOTAL",              "en": "TOTAL PRICE"},
    "payment_status":   {"pt": "PAGAMENTO",               "en": "PAYMENT"},
    "status_paid":      {"pt": "Finalizado",               "en": "PAID"},
    "status_open":      {"pt": "PENDENTE",                 "en": "PENDING"},
    "obs_hdr":          {"pt": "OBSERVAÇÕES",              "en": "NOTES"},
    "vendor_lbl":       {"pt": "VENDEDOR",                 "en": "SALES REP."},
    "po_destino":       {"pt": "PO DESTINO",               "en": "DESTINATION PO"},
    "billing_lbl":      {"pt": "FATURAMENTO",              "en": "BILLING"},
    "prazo_lbl":        {"pt": "PRAZO",                    "en": "TERMS"},
    "page_lbl":         {"pt": "PÁGINA",                   "en": "PAGE"},
    "generated":        {"pt": "GERADO EM",                "en": "GENERATED ON"},
    # Operational data
    # Título da página de dados operacionais (aparece uma vez, no topo da página)
    "op_page_title":    {"pt": "DETALHES DA AGENDA",       "en": "SCHEDULE DETAILS"},
    "op_driver":        {"pt": "MOTORISTA",                "en": "DRIVER NAME"},
    "op_driver_phone":  {"pt": "FONE",                     "en": "MOBILE"},
    "op_modelo":        {"pt": "MODELO",                   "en": "VEHICLE MODEL"},
    "op_plate":         {"pt": "PLACA",                    "en": "LICENSE PLATE"},
    "op_pickup":        {"pt": "DATA / HORA PICKUP",        "en": "PICKUP DATE/TIME"},
    "op_pickup_date":   {"pt": "DATA EMBARQUE",             "en": "PICKUP DATE"},
    "op_pickup_time":   {"pt": "HORA EMBARQUE",             "en": "PICKUP TIME"},
    "op_from":          {"pt": "EMBARQUE",                  "en": "PICKUP LOCATION"},
    "op_to":            {"pt": "DESEMBARQUE",               "en": "DROP-OFF LOCATION"},
    "op_passenger":     {"pt": "PASSAGEIRO",               "en": "PASSENGER"},
    "op_pax_phone":     {"pt": "FONE PAX",                 "en": "PAX PHONE"},
    "op_flight":        {"pt": "Nº VOO",                  "en": "FLIGHT NO."},
    "op_obs":           {"pt": "OBSERVAÇÕES",              "en": "NOTES"},
}


def _t(key: str, lang: str) -> str:
    entry = _T.get(key, {})
    return entry.get(lang) or entry.get("pt") or key


def _price_brl_usd(brl: float, style, usd_rate):
    """Preço em R$ e, com cotação USD, o valor em USD ABAIXO, em fonte menor
    e sem barra."""
    base = _fmt_brl(brl)
    if usd_rate and usd_rate > 0:
        usd_val = brl / usd_rate
        return Paragraph(
            f"{base}<br/><font size='6' color='#888888'>USD {_fmt_usd_raw(usd_val)}</font>",
            style)
    return Paragraph(base, style)


def _fmt_date(d, lang: str = "pt") -> str:
    if d is None:
        return "–"
    try:
        fmt = "%m/%d/%Y" if lang == "en" else "%d/%m/%Y"
        return d.strftime(fmt)
    except Exception:
        return str(d)


def _fmt_datetime(dt, lang: str = "pt") -> str:
    if dt is None:
        return "–"
    try:
        fmt = "%m/%d/%Y %I:%M%p" if lang == "en" else "%d/%m/%Y %I:%M%p"
        return dt.strftime(fmt)
    except Exception:
        return str(dt)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate_order_pdf(order, lang: str = "pt") -> io.BytesIO:
    """Return a BytesIO containing the PDF for the given order."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"{_t('order_title', lang)} {order.number}",
    )

    W = A4[0] - 30 * mm

    # ── Styles ────────────────────────────────────────────────────────────
    title_st   = ParagraphStyle("ts", fontSize=13, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=1)
    sub_st     = ParagraphStyle("ss", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=BRAND_GOLD, alignment=TA_CENTER, spaceAfter=6)
    normal     = ParagraphStyle("ns", fontSize=9, textColor=BRAND_DARK, leading=13)
    small      = ParagraphStyle("sm", fontSize=8, textColor=colors.HexColor("#666"), leading=11)
    sec_hdr    = ParagraphStyle("sh", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, leading=12, spaceBefore=3, spaceAfter=3)
    footer_st  = ParagraphStyle("fs", fontSize=7.5, textColor=colors.HexColor("#666"),
                                 alignment=TA_CENTER, leading=11)
    cell_hdr   = ParagraphStyle("ch", fontSize=7, fontName="Helvetica-Bold",
                                 textColor=colors.white, leading=10, alignment=TA_CENTER)
    cell_hdr_l = ParagraphStyle("chl", parent=cell_hdr, alignment=TA_LEFT)
    cell_body  = ParagraphStyle("cb", fontSize=8, textColor=BRAND_DARK, leading=11)
    cell_body_c = ParagraphStyle("cbc", parent=cell_body, alignment=TA_CENTER)
    cell_body_r = ParagraphStyle("cbr", parent=cell_body, alignment=TA_RIGHT)
    cell_bold_r = ParagraphStyle("cbr2", fontSize=9, fontName="Helvetica-Bold",
                                  textColor=BRAND_DARK, alignment=TA_RIGHT, leading=11)
    cell_bold_total = ParagraphStyle("cbt", fontSize=10, fontName="Helvetica-Bold",
                                      textColor=colors.HexColor("#0d9488"),
                                      alignment=TA_RIGHT, leading=12)

    story = []

    # ── Header: logo left + title/number right ──────────────────────────────
    company      = getattr(order, "company", None)
    company_name = (company.name if company else None) or "Executive Car SP"
    company_doc  = (company.document if company else None) or ""

    from ..utils import now_br
    vendor_name = ""
    if order.created_by:
        try:
            from ..models.user import User
            u = User.query.get(order.created_by)
            vendor_name = u.name if u else ""
        except Exception:
            pass

    # Load company logo
    logo_url = (company.logo_url if company else None)
    logo_img = None
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
                logo_img = RLImage(logo_path, width=100 * mm, height=20 * mm, kind="proportional")
        except Exception:
            logo_img = None

    left_cell  = logo_img if logo_img else Paragraph(f"<b>{company_name.upper()}</b>",
                ParagraphStyle("hc", fontSize=12, fontName="Helvetica-Bold",
                               textColor=BRAND_DARK, alignment=TA_LEFT))
    right_cell = Paragraph(
        f"<b>{_t('order_title', lang)}</b><br/><font color='#b88b2d' size='9'><b>No. {order.number}</b></font>",
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

    # ── Order data table (dark header + gold borders) ─────────────────────
    _STATUS_LABELS_ORD: dict[str, dict[str, str]] = {
        "novo":      {"pt": "Novo",        "en": "New"},
        "aberto":    {"pt": "Aberto",      "en": "Open"},
        "faturado":  {"pt": "Faturado",    "en": "Invoiced"},
        "concluido": {"pt": "Conclu\u00eddo",  "en": "Completed"},
        "fechado":   {"pt": "Conclu\u00eddo",  "en": "Completed"},
        "cancelado": {"pt": "Cancelado",   "en": "Cancelled"},
    }
    status_val = _STATUS_LABELS_ORD.get(order.status or "novo", {}).get(lang, order.status or "–")

    # POs de destino desta SO (hiperlinks p/ abrir cada PO)
    pos_destino = [p for p in getattr(order, "purchase_orders", [])
                   if getattr(p, "deleted_at", None) is None]
    if len(pos_destino) > 1:
        po_link_st = ParagraphStyle("pol", parent=cell_body_c, fontSize=6.5, leading=9)
    else:
        po_link_st = cell_body_c
    po_links = [f'<a href="{_app_base_url()}/po/{p.id}" color="#1565c0">{p.number}</a>'
                for p in pos_destino]
    po_cell = ", ".join(po_links) if po_links else "–"

    order_col_labels = [
        _t("emission",    lang),
        _t("delivery",    lang),
        _t("vendor_lbl",  lang),
        _t("po_destino",  lang),
        "STATUS",
    ]
    order_col_values = [
        _fmt_date(order.emission_date, lang),
        _fmt_date(order.delivery_datetime, lang),
        vendor_name or "–",
        po_cell,
        status_val,
    ]
    order_meta_tbl = Table(
        [[Paragraph(h, cell_hdr) for h in order_col_labels],
         [Paragraph(order_col_values[0], cell_body_c),
          Paragraph(order_col_values[1], cell_body_c),
          Paragraph(order_col_values[2], cell_body_c),
          Paragraph(po_cell, po_link_st),
          Paragraph(status_val, cell_body_c)]],
        colWidths=[W * 0.15, W * 0.19, W * 0.20, W * 0.22, W * 0.24],
    )
    order_meta_tbl.setStyle(TableStyle([
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
    story.append(order_meta_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Client table (dark header + gold borders, same as quote PDF) ──────
    client_tbl_data = [
        [Paragraph(_t("company_col", lang), cell_hdr),
         Paragraph(_t("contact_col", lang), cell_hdr),
         Paragraph(_t("email_col",   lang), cell_hdr),
         Paragraph(_t("mobile_col",  lang), cell_hdr)],
        [Paragraph((order.client.name if order.client and order.client.name else order.client_name) or "–", cell_body_c),
         Paragraph((order.client.contact if order.client and order.client.contact else order.contact_name) or "–", cell_body_c),
         Paragraph((order.client.email if order.client and order.client.email else order.email) or "–", cell_body_c),
         Paragraph(_sanitize_phone((order.client.whatsapp if order.client and order.client.whatsapp else (order.client.phone if order.client else None)) or getattr(order, "celular", None) or order.phone or "–"), cell_body_c)],
    ]
    client_tbl = Table(client_tbl_data,
                       colWidths=[W * 0.28, W * 0.24, W * 0.30, W * 0.18])
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

    # ── Compute adjustments (needed before building the items table) ─────────
    subtotal           = order.total_amount or 0
    discount_v         = order.discount_value or 0
    discount_type      = order.discount_type or "R$"
    other_costs        = order.other_costs_amount or 0
    other_costs_lbl_v  = getattr(order, "other_costs_label", "") or ""
    computed           = order.computed_total

    if discount_type == "%":
        disc_amt = subtotal * (discount_v / 100)
        disc_row_lbl = f"{_t('discount', lang)} ({discount_v:.2f}%)"
    else:
        disc_amt = discount_v
        disc_row_lbl = f"{_t('discount', lang)} ({_fmt_brl(discount_v)})" if discount_v else ""

    # ── Items table (same style as quote PDF) ─────────────────────────────
    i_col_w = [W * 0.05, W * 0.52, W * 0.07, W * 0.17, W * 0.19]
    items_rows = [[
        Paragraph(_t("hash_col",    lang), cell_hdr),
        Paragraph(_t("service_col", lang), cell_hdr),
        Paragraph(_t("qty_col",     lang), cell_hdr),
        Paragraph(_t("unit_col",    lang), cell_hdr),
        Paragraph(_t("subtotal_col", lang), cell_hdr),
    ]]
    grand_total = 0.0
    usd_rate = getattr(order, 'usd_rate', None)
    for idx, item in enumerate(sorted(order.items, key=lambda x: x.sort_order or 0), 1):
        service_name_raw  = item.description or "–"
        driver_type_raw   = item.driver_name or ""
        vehicle_desc      = item.vehicle_description or ""
        ref_note_val      = item.ref_note or ""
        cat_name_raw      = (item.category.name if item.category else "") or ""

        service_name_disp = _translate_service(service_name_raw, lang, cat_name_raw)
        cat_name_disp     = _translate_vehicle(cat_name_raw, lang)
        driver_disp       = _translate_driver(driver_type_raw, lang)

        main_parts = []
        if ref_note_val:
            main_parts.append(ref_note_val)
        main_parts.append(service_name_disp)
        main_label = " – ".join(main_parts)

        sub_parts = []
        if driver_disp:
            sub_parts.append(driver_disp)
        if cat_name_disp:
            sub_parts.append(cat_name_disp)
        sub_label = " – ".join(sub_parts)

        vehicle_model = _get_vehicle_model(cat_name_raw, lang) or vehicle_desc
        if vehicle_model and sub_label:
            sub_label = f'{sub_label} ({vehicle_model})'

        date_prefix = ''
        if item.service_date:
            if lang == 'en':
                date_prefix = item.service_date.strftime('%m/%d')
            else:
                date_prefix = item.service_date.strftime('%d/%m')
            if item.service_time:
                h = item.service_time.hour
                m = item.service_time.minute
                ampm = 'AM' if h < 12 else 'PM'
                h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
                date_prefix += f' {h12}:{m:02d}{ampm}'
        if date_prefix:
            main_label = f'{date_prefix} – {main_label}'

        svc_lines = [f"<b>{main_label}</b>"]
        if sub_label:
            svc_lines.append(f'<font color="#334155" size="7.5">{sub_label}</font>')
        svc_para = Paragraph("<br/>".join(svc_lines), cell_body)

        total = item.total_price or round((item.unit_price or 0) * (item.quantity or 1), 2)
        grand_total += total

        items_rows.append([
            Paragraph(str(idx),                       cell_body_c),
            svc_para,
            Paragraph(str(item.quantity or 1),        cell_body_c),
            _price_brl_usd(item.unit_price or 0, cell_body_r, usd_rate),
            _price_brl_usd(total,                cell_body_r, usd_rate),
        ])

    # Track where item rows end (before adjustment rows)
    item_data_end = len(items_rows)

    # Linha do total dos servicos: rotulo "PREÇO TOTAL" sob a coluna UNIT. e
    # o valor (soma dos servicos) sob a coluna SUBTOTAL
    items_rows.append([
        Paragraph("", cell_body),
        Paragraph("", cell_body),
        Paragraph("", cell_body),
        Paragraph(f"<b>{_t('grand_total_lbl', lang)}</b>", cell_bold_r),
        _price_brl_usd(grand_total, cell_bold_r, usd_rate),
    ])

    # Append discount row if applicable
    # As celulas vazias da linha do total nao devem existir: junta as 3 primeiras
    _adj_style_cmds: list = [("SPAN", (0, item_data_end), (2, item_data_end))]
    if disc_amt:
        # Discount row
        r = len(items_rows)
        items_rows.append([
            Paragraph(f"<i>{disc_row_lbl}:</i>", cell_body_r),
            "", "", "",
            Paragraph(f'<font color="#c62828">- {_fmt_brl(disc_amt)}</font>', cell_body_r),
        ])
        _adj_style_cmds += [
            ("SPAN",          (0, r), (3, r)),
            ("BACKGROUND",    (0, r), (-1, r), colors.HexColor("#fff8e1")),
            ("ALIGN",         (0, r), (-1, r), "RIGHT"),
            ("TOPPADDING",    (0, r), (-1, r), 4),
            ("BOTTOMPADDING", (0, r), (-1, r), 4),
        ]

    # Append outros custos row if applicable
    if other_costs:
        r = len(items_rows)
        cost_lbl = other_costs_lbl_v or _t("other_costs", lang)
        items_rows.append([
            Paragraph(f"<i>{cost_lbl}:</i>", cell_body_r),
            "", "", "",
            Paragraph(_fmt_brl(other_costs), cell_body_r),
        ])
        _adj_style_cmds += [
            ("SPAN",          (0, r), (3, r)),
            ("BACKGROUND",    (0, r), (-1, r), colors.HexColor("#fff8e1")),
            ("ALIGN",         (0, r), (-1, r), "RIGHT"),
            ("TOPPADDING",    (0, r), (-1, r), 4),
            ("BOTTOMPADDING", (0, r), (-1, r), 4),
        ]

    items_tbl = Table(items_rows, colWidths=i_col_w, repeatRows=1)
    items_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_DARK),
        ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (1, 1), (1, -1),  "TOP"),
        ("ALIGN",         (1, 0), (1, -1),  "LEFT"),
    ])
    # Alternating background for item rows only (not adjustment rows)
    for row_idx in range(1, item_data_end):
        bg = BRAND_LIGHT if row_idx % 2 == 1 else colors.white
        items_style.add("BACKGROUND", (0, row_idx), (-1, row_idx), bg)
    # Apply adjustment row styles
    for cmd in _adj_style_cmds:
        items_style.add(*cmd)
    items_tbl.setStyle(items_style)
    story.append(items_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── Payment summary table (dark header + gold borders) ────────────────
    pay_method_raw = (order.payment_method or "").strip()
    pay_method_key = pay_method_raw.upper()
    pay_method_lbl = _t(f"pay_{pay_method_key}", lang)
    if pay_method_lbl == f"pay_{pay_method_key}":
        pay_method_lbl = pay_method_raw or "–"
    pay_terms_lbl = _translate_payment_terms((order.payment_terms or "–").strip(), lang)
    billing_lbl   = _billing_label(order.billing_type or "recibo", lang)

    # ── Tabela única de pagamento: Faturamento | Forma de Pagamento |
    #    Prazo Pagamento | Parcela | Vencimento | Valor | Pagamento ──────
    cell_total_gold = ParagraphStyle("ctg", fontSize=10, fontName="Helvetica-Bold",
                                      textColor=BRAND_GOLD, alignment=TA_CENTER, leading=12)
    # Cabecalho compacto: os 7 rotulos cabem numa linha unica
    cell_hdr_sm = ParagraphStyle("chs", parent=cell_hdr, fontSize=6, leading=7)
    pay_rows = [[
        Paragraph(_t("included_col",    lang), cell_hdr_sm),
        Paragraph(_t("payment_col",     lang), cell_hdr_sm),
        Paragraph(_t("prazo_col",       lang), cell_hdr_sm),
        Paragraph(_t("installment_no",  lang), cell_hdr_sm),
        Paragraph(_t("due_date",        lang), cell_hdr_sm),
        Paragraph(_t("amount_col",      lang), cell_hdr_sm),
        Paragraph(_t("payment_status",  lang), cell_hdr_sm),
    ]]
    sorted_pmts = sorted(order.payments, key=lambda p: p.installment_no) if order.payments else []
    total_pmts = len(sorted_pmts)

    def _pmt_cells(pmt):
        is_paid      = pmt.is_paid
        status_label = _t("status_paid", lang) if is_paid else _t("status_open", lang)
        # mesmo tamanho de fonte das demais celulas (8pt), texto BRANCO
        # (igual ao PO) sobre o sombreado do status
        st_p = ParagraphStyle("sp", fontSize=8, fontName="Helvetica-Bold",
                               textColor=colors.white, alignment=TA_CENTER, leading=10)
        return [
            Paragraph(f"{pmt.installment_no}/{total_pmts}", cell_body_c),
            Paragraph(_fmt_date(pmt.due_date, lang),        cell_body_c),
            _price_brl_usd(pmt.amount or 0, cell_body_r, usd_rate),
            Paragraph(status_label, st_p),
        ]

    # primeira linha de dados: faturamento/forma/prazo + a PRIMEIRA parcela
    primeira = _pmt_cells(sorted_pmts[0]) if sorted_pmts else [Paragraph("", cell_body_c)] * 4
    pay_rows.append([
        Paragraph(billing_lbl,            cell_body_c),
        Paragraph(pay_method_lbl or "–", cell_body_c),
        Paragraph(pay_terms_lbl,          cell_body_c),
        *primeira,
    ])
    for pmt in sorted_pmts[1:]:
        pay_rows.append([
            Paragraph("", cell_body_c),
            Paragraph("", cell_body_c),
            Paragraph("", cell_body_c),
            *_pmt_cells(pmt),
        ])

    pay_tbl = Table(pay_rows, colWidths=[W * 0.12, W * 0.16, W * 0.19,
                                         W * 0.12, W * 0.11, W * 0.14, W * 0.16],
                    repeatRows=1)
    pay_style = TableStyle([
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
        ("ALIGN",         (5, 0), (5, -1), "RIGHT"),
    ])
    for idx, pmt in enumerate(sorted_pmts):
        row_idx = idx + 1   # a primeira parcela esta na linha 1
        if row_idx >= 2:
            row_bg = BRAND_LIGHT if row_idx % 2 == 0 else colors.white
            pay_style.add("BACKGROUND", (0, row_idx), (2, row_idx), row_bg)
        # sombreados um pouco mais claros para todos os status
        st_bg = colors.HexColor("#388E3C") if pmt.is_paid else colors.HexColor("#F57C00")
        pay_style.add("BACKGROUND", (6, row_idx), (6, row_idx), st_bg)
    # Com mais de uma parcela, Faturamento/Forma de Pagamento/Prazo Pagamento
    # fazem merge vertical entre as linhas (uma unica celula alta)
    if len(sorted_pmts) > 1:
        last_row = len(pay_rows) - 1
        for col in (0, 1, 2):
            pay_style.add("SPAN", (col, 1), (col, last_row))
        pay_style.add("VALIGN", (0, 1), (2, last_row), "MIDDLE")
    pay_tbl.setStyle(pay_style)
    story.append(pay_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Observations ──────────────────────────────────────────────────────
    obs_hdr_label = "OBSERVAÇÕES" if lang == "pt" else "NOTES"
    story.append(Paragraph(obs_hdr_label, sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    bullet_st = ParagraphStyle("obs_bullet", parent=normal, leftIndent=12, firstLineIndent=-8)
    # Frase de overtime removida definitivamente do PDF de SO (todos os idiomas).
    if order.obs:
        from ..utils.translate import translate_obs
        obs_text = translate_obs(order.obs, lang) if lang != "pt" else order.obs
        for line in obs_text.splitlines():
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if not safe.strip():
                story.append(Spacer(1, 3))
            elif safe.lstrip().startswith("- ") or safe.lstrip().startswith("* "):
                text = safe.lstrip()[2:]
                story.append(Paragraph(f"\u2022 {text}", bullet_st))
            else:
                story.append(Paragraph(safe, normal))
    story.append(Spacer(1, 4 * mm))

    # ── Dados operacionais por item — formato compacto, agrupados ──────────
    # Omitidos no PDF após faturamento (dados operacionais são do despacho,
    # não pertencem ao documento fiscal).
    op_label_st = ParagraphStyle(
        "op_label_c", fontName="Helvetica-Bold", fontSize=7,
        textColor=colors.HexColor("#64748b"), leading=9, spaceAfter=0,
    )
    op_value_st = ParagraphStyle(
        "op_value_c", fontName="Helvetica", fontSize=7.5,
        textColor=BRAND_DARK, leading=10, spaceAfter=0,
    )
    op_title_st = ParagraphStyle(
        "op_title_c", fontName="Helvetica-Bold", fontSize=11,
        textColor=colors.white, alignment=TA_LEFT, leading=14,
    )
    # Título da página de dados operacionais — centralizado (16pt)
    op_page_title_st = ParagraphStyle(
        "op_page_title_c", fontName="Helvetica-Bold", fontSize=16,
        textColor=BRAND_DARK, alignment=TA_CENTER, leading=20, spaceAfter=10,
    )

    items_sorted = sorted(order.items, key=lambda it: (it.sort_order or 0, it.id))
    item_index = {it.id: i + 1 for i, it in enumerate(items_sorted)}

    # Dados operacionais omitidos no PDF pós-faturamento
    op_groups: list[tuple[tuple, list]] = []  # [(key_tuple, [items])]
    if order.status != "faturado":
        for it in items_sorted:
            op_pickup_dt = getattr(it, "op_pickup_datetime", None)
            key = (
                (getattr(it, "op_driver_name", "") or "").strip(),
                (getattr(it, "op_driver_phone", "") or "").strip(),
                (getattr(it, "op_vehicle_model", "") or "").strip(),
                (getattr(it, "op_vehicle_plate", "") or "").strip(),
                op_pickup_dt.isoformat() if op_pickup_dt else "",
                (getattr(it, "op_pickup_location", "") or "").strip(),
                (getattr(it, "op_dropoff_location", "") or "").strip(),
                (getattr(it, "op_passenger_name", "") or "").strip(),
                (getattr(it, "op_passenger_phone", "") or "").strip(),
                (getattr(it, "op_flight_number", "") or "").strip(),
                (getattr(it, "op_notes", "") or "").strip(),
            )
            if not any(key):
                continue
            matched = False
            for k, lst in op_groups:
                if k == key:
                    lst.append(it)
                    matched = True
                    break
            if not matched:
                op_groups.append((key, [it]))

    total_items = len(items_sorted)

    if op_groups:
        story.append(PageBreak())
        # Logotipo centralizado no cabeçalho (mesmo da página principal)
        if logo_img:
            logo_hdr = Table([[logo_img]], colWidths=[W])
            logo_hdr.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(logo_hdr)
        # Título da página de dados operacionais (uma vez, antes dos blocos)
        story.append(Paragraph(_t("op_page_title", lang), op_page_title_st))

    for key, items in op_groups:
        sample = items[0]
        pickup_dt = getattr(sample, "op_pickup_datetime", None)
        pickup_date_str = _fmt_date(pickup_dt.date() if pickup_dt else None, lang) if pickup_dt else ""
        if pickup_date_str == "\u2013":
            pickup_date_str = ""
        pickup_time_str = _fmt_time_12h(pickup_dt, lang) if pickup_dt else ""

        fields = [
            ("op_driver",       key[0]),
            ("op_driver_phone", key[1]),
            ("op_modelo",       key[2]),
            ("op_plate",        key[3]),
            ("op_from",         key[5]),
            ("op_to",           key[6]),
            ("op_flight",       key[9]),
            ("op_passenger",    key[7]),
            ("op_pax_phone",    key[8]),
            ("op_obs",          key[10]),
        ]
        filled = [(lk, v) for lk, v in fields if v]
        if not filled and not pickup_dt:
            continue

        # Header com subtítulo (quais itens)
        if len(items) == total_items and total_items > 1:
            sub = "Todos os itens" if lang == "pt" else "All items"
        else:
            nums = ", ".join(f"#{item_index[it.id]}" for it in items)
            sub = (f"Item {nums}" if len(items) == 1 else
                   (f"Itens {nums}" if lang == "pt" else f"Items {nums}"))
        # Tarja do bloco: item(ns) + data/hora de embarque (quando preenchidos).
        # O rotulo "DADOS OPERACIONAIS" / "OPERATIONAL DATA" saiu - o titulo da
        # pagina ja identifica a secao.
        hdr_text = sub
        if pickup_dt:
            when = " ".join(x for x in (pickup_date_str, pickup_time_str) if x).strip()
            if when:
                hdr_text = f"{sub} — {when}"

        hdr_tbl = Table(
            [[Paragraph(hdr_text, op_title_st)]],
            colWidths=[W],
        )
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(hdr_tbl)

        # Tabela compacta — 4 colunas (label: valor) por linha
        COLS = 4
        cells = []
        for lk, v in filled:
            label = _t(lk, lang)
            if lk in ("op_driver_phone", "op_pax_phone") and v and any(c.isdigit() for c in v):
                add_55 = (lk == "op_driver_phone")
                safe = _fmt_phone_link(v, add_country=add_55)
            else:
                safe = (v or "").replace('\xa0', ' ').replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            cells.append(Paragraph(f"<b>{label}</b><br/>{safe}", op_value_st))

        # Preenche para múltiplo de COLS
        while len(cells) % COLS != 0:
            cells.append(Paragraph("", op_value_st))
        rows = [cells[i:i + COLS] for i in range(0, len(cells), COLS)]

        if cells:
            cw = W / COLS
            info_tbl = Table(rows, colWidths=[cw] * COLS)
            info_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(info_tbl)
        story.append(Spacer(1, 2 * mm))

    if op_groups:
        story.append(Spacer(1, 2 * mm))
    # ── Fim do bloco de dados operacionais ──────────────────────────────────

    # ── Footer as page callback (like quote PDF) ───────────────────────────
    from datetime import datetime as _dt
    cnpj_lbl_footer = "CNPJ" if lang == "pt" else "TAX ID"
    tax_part     = (f"{company_name} \u2022 {cnpj_lbl_footer} {company_doc}" if company_doc else company_name)
    now_str      = _dt.now().strftime("%m/%d/%Y %I:%M%p" if lang == "en" else "%d/%m/%Y %I:%M%p")
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
        # Site com ícone + hiperlink, centralizado, abaixo do "Gerado"
        from reportlab.pdfbase.pdfmetrics import stringWidth
        _register_web_font()
        try:
            icon_w = stringWidth(SITE_ICON, "FontAwesome", 7.5)
        except Exception:
            icon_w = 0.0
        url_w = stringWidth(SITE_URL, "Helvetica", 7.5)
        gap = 2
        x0 = (_pw - (icon_w + gap + url_w)) / 2
        y_site = 4.5 * mm
        if icon_w:
            canvas.setFont("FontAwesome", 7.5)
            canvas.setFillColor(colors.HexColor("#1565c0"))
            canvas.drawString(x0, y_site, SITE_ICON)
        x_url = x0 + icon_w + gap
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#1565c0"))
        canvas.drawString(x_url, y_site, SITE_URL)
        canvas.linkURL(SITE_URL, (x_url, y_site - 1, x_url + url_w, y_site + 3),
                       relative=1)
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer
