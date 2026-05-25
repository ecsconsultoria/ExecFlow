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
    _T as _QT,
    _billing_label,
    _fmt_brl,
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
    "emission":         {"pt": "Data de Emissão",          "en": "Issue Date"},
    "delivery":         {"pt": "Data de Entrega",          "en": "Delivery Date"},
    "subtotal":         {"pt": "Subtotal",                 "en": "Subtotal"},
    "discount":         {"pt": "Desconto",                 "en": "Discount"},
    "freight":          {"pt": "Frete",                    "en": "Freight"},
    "other_costs":      {"pt": "Custos Extras",            "en": "Extra Costs"},
    "final_total":      {"pt": "TOTAL FINAL",              "en": "TOTAL AMOUNT"},
    "payment_hdr":      {"pt": "Pagamento",                "en": "Payment"},
    "installment_no":   {"pt": "Parcela",                  "en": "Installment"},
    "due_date":         {"pt": "Vencimento",               "en": "Due Date"},
    "amount_col":       {"pt": "Valor (R$)",               "en": "Amount (R$)"},
    "payment_status":   {"pt": "PAGAMENTO",               "en": "PAYMENT"},
    "status_paid":      {"pt": "PAGO",                     "en": "PAID"},
    "status_open":      {"pt": "PENDENTE",                 "en": "PENDING"},
    "obs_hdr":          {"pt": "Observações",              "en": "Notes"},
    "vendor_lbl":       {"pt": "Vendedor",                 "en": "Sales Rep."},
    "billing_lbl":      {"pt": "Faturamento",              "en": "Billing"},
    "prazo_lbl":        {"pt": "Prazo",                    "en": "Terms"},
    "page_lbl":         {"pt": "Página",                   "en": "Page"},
    "generated":        {"pt": "Gerado em",                "en": "Generated on"},
    # Operational data
    "op_hdr":           {"pt": "DADOS OPERACIONAIS",       "en": "OPERATIONAL DATA"},
    "op_driver":        {"pt": "Motorista",                "en": "Driver"},
    "op_driver_phone":  {"pt": "Fone",                     "en": "Phone"},
    "op_modelo":        {"pt": "Modelo",                   "en": "Model"},
    "op_plate":         {"pt": "Placa",                    "en": "Plate"},
    "op_pickup":        {"pt": "Data / Hora Pickup",        "en": "Pickup Date/Time"},
    "op_from":          {"pt": "Local de Embarque",          "en": "Pickup Location"},
    "op_to":            {"pt": "Local de Desembarque",       "en": "Dropoff Location"},
    "op_passenger":     {"pt": "Passageiro",               "en": "Passenger"},
    "op_pax_phone":     {"pt": "Fone Passageiro",          "en": "Pax Phone"},
    "op_flight":        {"pt": "Nº Voo",                  "en": "Flight No."},
    "op_obs":           {"pt": "Observações",              "en": "Notes"},
}


def _t(key: str, lang: str) -> str:
    entry = _T.get(key, {})
    return entry.get(lang) or entry.get("pt") or key


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
        fmt = "%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M"
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
    cell_hdr   = ParagraphStyle("ch", fontSize=8, fontName="Helvetica-Bold",
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

    # ── Company header: Logo (smaller) + company info ─────────────────────
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
            # Smaller logo: max 30 mm height, proportional
            if os.path.isfile(logo_path):
                logo_img = RLImage(logo_path, width=60 * mm, height=30 * mm, kind="proportional")
        except Exception:
            logo_img = None

    info_st = ParagraphStyle("inf", fontSize=8.5, textColor=BRAND_DARK,
                              alignment=TA_RIGHT, leading=13)
    company_info_lines = []
    if company_doc:
        cnpj_lbl = "CNPJ" if lang == "pt" else "TAX ID"
        company_info_lines.append(f"<b>{cnpj_lbl}:</b> {company_doc}")
    if company and getattr(company, "phone", None):
        phone_lbl = "Telefone" if lang == "pt" else "Phone"
        company_info_lines.append(f"<b>{phone_lbl}:</b> {company.phone}")
    if company and getattr(company, "email", None):
        company_info_lines.append(f"<b>E-mail:</b> {company.email}")
    if company and getattr(company, "address", None):
        addr_lbl = "Endereço" if lang == "pt" else "Address"
        company_info_lines.append(f"<b>{addr_lbl}:</b> {company.address}")

    if logo_img:
        info_para = Paragraph(
            "<br/>".join(company_info_lines) if company_info_lines else "",
            info_st,
        )
        hdr_tbl = Table([[logo_img, info_para]], colWidths=[W * 0.40, W * 0.60])
        hdr_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (0, 0), "LEFT"),
            ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
    else:
        hdr_tbl = Table([[
            Paragraph(f"<b>{company_name.upper()}</b>",
                      ParagraphStyle("hc", fontSize=18, fontName="Helvetica-Bold",
                                     textColor=BRAND_DARK, alignment=TA_LEFT)),
            Paragraph("<br/>".join(company_info_lines) if company_info_lines else "",
                      info_st),
        ]], colWidths=[W * 0.50, W * 0.50])
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))

    story.append(hdr_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Title + Order Number (same style as quote PDF) ────────────────────
    story.append(Paragraph(_t("order_title", lang), title_st))
    story.append(Paragraph(f"No. {order.number}", sub_st))
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

    order_col_labels = [
        _t("emission",    lang),
        _t("delivery",    lang),
        _t("billing_lbl", lang),
        _t("vendor_lbl",  lang),
        "STATUS",
    ]
    order_col_values = [
        _fmt_date(order.emission_date, lang),
        _fmt_datetime(order.delivery_datetime, lang),
        _billing_label(order.billing_type or "recibo", lang),
        vendor_name or "–",
        status_val,
    ]
    order_meta_tbl = Table(
        [[Paragraph(h, cell_hdr) for h in order_col_labels],
         [Paragraph(v, cell_body_c) for v in order_col_values]],
        colWidths=[W * 0.16, W * 0.27, W * 0.21, W * 0.22, W * 0.14],
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
        [Paragraph(order.client_name  or "–", cell_body_c),
         Paragraph(order.contact_name or "–", cell_body_c),
         Paragraph(order.email        or "–", cell_body_c),
         Paragraph(getattr(order, "celular", None) or order.phone or "–", cell_body_c)],
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
        Paragraph(_t("service_col", lang), cell_hdr_l),
        Paragraph(_t("qty_col",     lang), cell_hdr),
        Paragraph(_t("unit_col",    lang), cell_hdr),
        Paragraph(_t("total_col",   lang), cell_hdr),
    ]]
    grand_total = 0.0
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
        if cat_name_disp:
            sub_parts.append(cat_name_disp)
        if driver_disp:
            sub_parts.append(driver_disp)
        sub_label = " – ".join(sub_parts)

        vehicle_model = _get_vehicle_model(cat_name_raw, lang) or vehicle_desc

        svc_lines = [f"<b>{main_label}</b>"]
        if sub_label:
            svc_lines.append(f'<font color="#334155" size="7.5">{sub_label}</font>')
        if vehicle_model:
            svc_lines.append(f'<font color="#888888" size="7"><i>{vehicle_model}</i></font>')
        svc_para = Paragraph("<br/>".join(svc_lines), cell_body)

        total = item.total_price or round((item.unit_price or 0) * (item.quantity or 1), 2)
        grand_total += total

        items_rows.append([
            Paragraph(str(idx),                       cell_body_c),
            svc_para,
            Paragraph(str(item.quantity or 1),        cell_body_c),
            Paragraph(_fmt_brl(item.unit_price or 0), cell_body_r),
            Paragraph(_fmt_brl(total),                cell_body_r),
        ])

    # Track where item rows end (before adjustment rows)
    item_data_end = len(items_rows)

    # Append discount row if applicable
    _adj_style_cmds: list = []
    if disc_amt:
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

    cell_total_gold = ParagraphStyle("ctg", fontSize=10, fontName="Helvetica-Bold",
                                      textColor=BRAND_GOLD, alignment=TA_CENTER, leading=12)
    pay_sum_tbl = Table(
        [
            [Paragraph(_t("payment_col",     lang), cell_hdr),
             Paragraph(_t("included_col",    lang), cell_hdr),
             Paragraph(_t("prazo_col",       lang), cell_hdr),
             Paragraph(_t("total_price_col", lang), cell_hdr)],
            [Paragraph(pay_method_lbl or "–", cell_body_c),
             Paragraph(billing_lbl,            cell_body_c),
             Paragraph(pay_terms_lbl,          cell_body_c),
             Paragraph(f"<b>{_fmt_brl(computed)}</b>", cell_total_gold)],
        ],
        colWidths=[W * 0.28, W * 0.26, W * 0.22, W * 0.24],
    )
    pay_sum_tbl.setStyle(TableStyle([
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
    story.append(pay_sum_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Installments table (dark header + gold borders) ───────────────────
    if order.payments:
        sorted_pmts = sorted(order.payments, key=lambda p: p.installment_no)
        total_pmts  = len(sorted_pmts)
        inst_rows   = [[
            Paragraph(_t("installment_no", lang), cell_hdr),
            Paragraph(_t("due_date",        lang), cell_hdr),
            Paragraph(_t("amount_col",      lang), cell_hdr),
            Paragraph(_t("payment_status", lang),  cell_hdr),
        ]]
        for pmt in sorted_pmts:
            is_paid      = pmt.is_paid
            status_label = _t("status_paid", lang) if is_paid else _t("status_open", lang)
            st_fg        = colors.white
            st_p = ParagraphStyle("sp", fontSize=8, fontName="Helvetica-Bold",
                                   textColor=st_fg, alignment=TA_CENTER, leading=10)
            inst_rows.append([
                Paragraph(f"{pmt.installment_no}/{total_pmts}", cell_body_c),
                Paragraph(_fmt_date(pmt.due_date, lang),        cell_body_c),
                Paragraph(_fmt_brl(pmt.amount or 0),            cell_body_r),
                Paragraph(status_label, st_p),
            ])

        inst_col_w = [W * 0.14, W * 0.27, W * 0.31, W * 0.28]
        inst_tbl   = Table(inst_rows, colWidths=inst_col_w, repeatRows=1)
        inst_style = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
            ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, BRAND_GOLD),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ])
        for row_idx, pmt in enumerate(sorted_pmts, 1):
            row_bg = BRAND_LIGHT if row_idx % 2 == 1 else colors.white
            inst_style.add("BACKGROUND", (0, row_idx), (2, row_idx), row_bg)
            st_bg = colors.HexColor("#2E7D32") if pmt.is_paid else colors.HexColor("#E65100")
            inst_style.add("BACKGROUND", (3, row_idx), (3, row_idx), st_bg)
        inst_tbl.setStyle(inst_style)
        story.append(inst_tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Observations ──────────────────────────────────────────────────────
    obs_hdr_label = "OBSERVAÇÕES" if lang == "pt" else "NOTES"
    story.append(Paragraph(obs_hdr_label, sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    bullet_st = ParagraphStyle("obs_bullet", parent=normal, leftIndent=12, firstLineIndent=-8)
    hora_extra_txt = (
        "Hora Extra: 10% sobre o valor total da diária, a partir de 30 minutos de despera."
        if lang == "pt" else
        "Overtime: 10% of the total daily rate, after 30 minutes of waiting."
    )
    story.append(Paragraph(f"• {hora_extra_txt}", bullet_st))
    if order.obs:
        for line in order.obs.splitlines():
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if not safe.strip():
                story.append(Spacer(1, 3))
            elif safe.lstrip().startswith("- ") or safe.lstrip().startswith("* "):
                text = safe.lstrip()[2:]
                story.append(Paragraph(f"\u2022 {text}", bullet_st))
            else:
                story.append(Paragraph(safe, normal))
    story.append(Spacer(1, 4 * mm))
    op_driver  = getattr(order, "driver_name",         None) or ""
    op_dphone  = getattr(order, "driver_phone",        None) or ""
    op_modelo  = getattr(order, "vehicle_model",       None) or ""
    op_obs_val = getattr(order, "vehicle_description", None) or ""
    op_plate   = getattr(order, "vehicle_plate",       None) or ""
    op_pickup  = _fmt_datetime(getattr(order, "delivery_datetime", None), lang)
    op_from    = getattr(order, "pickup_location",     None) or ""
    op_to      = getattr(order, "dropoff_location",    None) or ""
    op_pax     = getattr(order, "passenger_name",      None) or ""
    op_pphone  = getattr(order, "passenger_phone",     None) or ""
    op_flight  = getattr(order, "flight_number",       None) or ""
    op_pax_cnt = getattr(order, "pax_count",           None)

    _op_has_data = any([op_driver, op_modelo, op_plate, op_from, op_to,
                        op_pax, op_flight, op_pax_cnt])

    if _op_has_data:
        story.append(Spacer(1, 6 * mm))

        lbl_st_op = ParagraphStyle(
            "op_lbl", fontName="Helvetica-Bold", fontSize=7,
            textColor=colors.HexColor("#64748b"), spaceAfter=1,
        )
        val_st_op = ParagraphStyle(
            "op_val", fontName="Helvetica-Bold", fontSize=9.5,
            textColor=BRAND_DARK, spaceAfter=0,
        )
        hdr_st_op = ParagraphStyle(
            "op_hdr_st", fontName="Helvetica-Bold", fontSize=10,
            textColor=colors.white, alignment=TA_CENTER,
        )

        hdr_cell = Paragraph(_t("op_hdr", lang), hdr_st_op)
        hdr_tbl  = Table([[hdr_cell]], colWidths=[W])
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(hdr_tbl)

        _op_pickup_str = op_pickup if op_pickup != "\u2013" else "\u2013"
        if op_pax_cnt:
            _op_pickup_str = (_op_pickup_str + f"  \u2022  {op_pax_cnt} PAX").strip(" \u2022 ")

        op_rows_raw = [
            ("op_driver",    op_driver,      "op_driver_phone", op_dphone),
            ("op_modelo",    op_modelo,      "op_plate",        op_plate),
            ("op_pickup",    _op_pickup_str, "op_flight",       op_flight),
            ("op_from",      op_from,        "op_to",           op_to),
            ("op_passenger", op_pax,         "op_pax_phone",    op_pphone),
            ("op_obs",       op_obs_val,     "",                ""),
        ]

        CL = W * 0.18
        CV = W * 0.32

        grid_rows = []
        span_rows = []
        for lk1, v1, lk2, v2 in op_rows_raw:
            if not v1 and not v2:
                continue
            if not lk2:
                span_rows.append(len(grid_rows))
                grid_rows.append([
                    Paragraph(_t(lk1, lang).upper(), lbl_st_op),
                    Paragraph(v1 or "\u2013", val_st_op),
                    Paragraph("", lbl_st_op),
                    Paragraph("", val_st_op),
                ])
            else:
                grid_rows.append([
                    Paragraph(_t(lk1, lang).upper(), lbl_st_op),
                    Paragraph(v1 or "\u2013", val_st_op),
                    Paragraph(_t(lk2, lang).upper(), lbl_st_op),
                    Paragraph(v2 or "\u2013", val_st_op),
                ])

        if grid_rows:
            span_cmds = [("SPAN", (1, r), (3, r)) for r in span_rows]
            grid_tbl = Table(grid_rows, colWidths=[CL, CV, CL, CV])
            grid_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("TOPPADDING",    (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",           (0, 0), (-1, -1), 1.5, BRAND_GOLD),
                ("BACKGROUND",    (0, 0), (0, -1),  colors.HexColor("#f1f5f9")),
                ("BACKGROUND",    (2, 0), (2, -1),  colors.HexColor("#f1f5f9")),
                *span_cmds,
            ]))
            story.append(grid_tbl)

        story.append(Spacer(1, 5 * mm))

    # ── Footer as page callback (like quote PDF) ───────────────────────────
    from datetime import datetime as _dt
    cnpj_lbl_footer = "CNPJ" if lang == "pt" else "TAX ID"
    tax_part     = (f"{company_name} \u2022 {cnpj_lbl_footer} {company_doc}" if company_doc else company_name)
    now_str      = _dt.now().strftime("%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
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

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer
