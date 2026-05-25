"""PDF generator for Purchase Orders (PO) — same style as SO PDF."""
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
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Re-use brand constants + helpers from quote_pdf
from .quote_pdf import BRAND_DARK, BRAND_GOLD, BRAND_LIGHT, _fmt_brl


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_date(d, lang: str = "pt") -> str:
    if d is None:
        return "–"
    try:
        return d.strftime("%m/%d/%Y" if lang == "en" else "%d/%m/%Y")
    except Exception:
        return str(d)


def _fmt_datetime(d, lang: str = "pt") -> str:
    if d is None:
        return "–"
    try:
        return d.strftime("%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
    except Exception:
        return str(d)


# ─── i18n ─────────────────────────────────────────────────────────────────────

_LABELS: dict[str, dict[str, str]] = {
    "doc_title":       {"pt": "PEDIDO DE COMPRA",          "en": "PURCHASE ORDER"},
    "po_no":           {"pt": "Nº PC/PO",                  "en": "PO No."},
    "linked_so":       {"pt": "SO Vinculado",               "en": "Linked SO"},
    "payment":         {"pt": "Forma Pagto.",               "en": "Payment"},
    "supplier_lbl":    {"pt": "Fornecedor",                 "en": "Supplier"},
    "supplier_hdr":    {"pt": "FORNECEDOR",                 "en": "SUPPLIER"},
    "service_col":     {"pt": "Serviço / Descrição",        "en": "Service / Description"},
    "hash_col":        {"pt": "#",                          "en": "#"},
    "qty_col":         {"pt": "Qtd",                        "en": "Qty"},
    "unit_col":        {"pt": "Unit. R$",                   "en": "Unit R$"},
    "total_col":       {"pt": "Total R$",                   "en": "Total R$"},
    "discount":        {"pt": "Desconto",                   "en": "Discount"},
    "freight":         {"pt": "Frete",                      "en": "Freight"},
    "other_costs":     {"pt": "Custos Extras",              "en": "Extra Costs"},
    "payment_col":     {"pt": "Forma de Pagamento",         "en": "Payment Method"},
    "prazo_col":       {"pt": "Prazo",                      "en": "Terms"},
    "total_price_col": {"pt": "Total Final",                "en": "Final Total"},
    "installment_no":  {"pt": "Parcela",                    "en": "Installment"},
    "due_date":        {"pt": "Vencimento",                 "en": "Due Date"},
    "amount_col":      {"pt": "Valor (R$)",                 "en": "Amount (R$)"},
    "payment_status":  {"pt": "PAGAMENTO",                  "en": "PAYMENT"},
    "status_paid":     {"pt": "PAGO",                       "en": "PAID"},
    "status_open":     {"pt": "PENDENTE",                   "en": "PENDING"},
    "notes_hdr":       {"pt": "OBSERVAÇÕES",                "en": "NOTES"},
    "approved_by":     {"pt": "Aprovado por",               "en": "Approved by"},
    "supplier_sig":    {"pt": "Fornecedor",                 "en": "Supplier"},
    "date_sig":        {"pt": "Data",                       "en": "Date"},
    "emission":        {"pt": "Data de Emissão",            "en": "Issue Date"},
    "delivery":        {"pt": "Data Pickup",                "en": "Pickup Date"},
    "vendor_lbl":      {"pt": "Comprador",                  "en": "Buyer"},
    "generated":       {"pt": "Gerado em",                  "en": "Generated on"},
    # Operational
    "op_hdr":          {"pt": "DADOS OPERACIONAIS",           "en": "OPERATIONAL DATA"},
    "op_driver":       {"pt": "Motorista",                    "en": "Driver"},
    "op_driver_phone": {"pt": "Fone",                          "en": "Phone"},
    "op_modelo":       {"pt": "Modelo",                        "en": "Model"},
    "op_plate":        {"pt": "Placa",                        "en": "Plate"},
    "op_pickup":       {"pt": "Data / Hora Pickup",            "en": "Pickup Date/Time"},
    "op_from":         {"pt": "Local de Embarque",             "en": "Pickup Location"},
    "op_to":           {"pt": "Local de Desembarque",          "en": "Dropoff Location"},
    "op_passenger":    {"pt": "Passageiro",                   "en": "Passenger"},
    "op_pax_phone":    {"pt": "Fone do Passageiro",            "en": "Passenger Phone"},
    "op_flight":       {"pt": "Nº Voo",                       "en": "Flight No."},
    "op_pax":          {"pt": "PAX",                          "en": "PAX"},
    "op_obs":          {"pt": "Observações",                  "en": "Notes"},
}


def _t(key: str, lang: str) -> str:
    entry = _LABELS.get(key, {})
    return entry.get(lang) or entry.get("pt") or key


# ─── Generator ───────────────────────────────────────────────────────────────

def generate_po_pdf(po, lang: str = "pt") -> io.BytesIO:
    """Return a BytesIO containing the PO PDF (same visual style as SO PDF)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"{_t('doc_title', lang)} {po.number}",
    )

    W = A4[0] - 30 * mm

    # ── Styles ────────────────────────────────────────────────────────────────
    title_st        = ParagraphStyle("ts",  fontSize=13, fontName="Helvetica-Bold",
                                     textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=1)
    sub_st          = ParagraphStyle("ss",  fontSize=9,  fontName="Helvetica-Bold",
                                     textColor=BRAND_GOLD, alignment=TA_CENTER, spaceAfter=6)
    normal          = ParagraphStyle("ns",  fontSize=9,  textColor=BRAND_DARK, leading=13)
    sec_hdr         = ParagraphStyle("sh",  fontSize=9,  fontName="Helvetica-Bold",
                                     textColor=BRAND_DARK, leading=12, spaceBefore=3, spaceAfter=3)
    cell_hdr        = ParagraphStyle("ch",  fontSize=8,  fontName="Helvetica-Bold",
                                     textColor=colors.white, leading=10, alignment=TA_CENTER)
    cell_hdr_l      = ParagraphStyle("chl", parent=cell_hdr, alignment=TA_LEFT)
    cell_body       = ParagraphStyle("cb",  fontSize=8,  textColor=BRAND_DARK, leading=11)
    cell_body_c     = ParagraphStyle("cbc", parent=cell_body, alignment=TA_CENTER)
    cell_body_r     = ParagraphStyle("cbr", parent=cell_body, alignment=TA_RIGHT)

    story = []

    # ── Company header: Logo + company info ──────────────────────────────────
    company      = getattr(po, "company", None)
    company_name = (company.name if company else None) or "Executive Car SP"
    company_doc  = (company.document if company else None) or ""

    buyer_name = ""
    if getattr(po, "created_by", None):
        try:
            from ..models.user import User  # noqa: PLC0415
            u = User.query.get(po.created_by)
            buyer_name = u.name if u else ""
        except Exception:
            pass

    logo_url  = getattr(company, "logo_url", None) if company else None
    logo_img  = None
    if logo_url:
        try:
            from flask import current_app  # noqa: PLC0415
            logo_path = logo_url
            if logo_url.startswith("/uploads/"):
                logo_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    logo_url[len("/uploads/"):].lstrip("/"),
                )
            elif logo_url.startswith("/static/"):
                logo_path = os.path.join(
                    current_app.root_path, "static",
                    logo_url[len("/static/"):].lstrip("/"),
                )
            if os.path.isfile(logo_path):
                logo_img = RLImage(logo_path, width=60 * mm, height=30 * mm, kind="proportional")
        except Exception:
            logo_img = None

    info_st = ParagraphStyle("inf", fontSize=8.5, textColor=BRAND_DARK,
                             alignment=TA_RIGHT, leading=13)
    company_info_lines: list[str] = []
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
        info_para = Paragraph("<br/>".join(company_info_lines) if company_info_lines else "", info_st)
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
            Paragraph("<br/>".join(company_info_lines) if company_info_lines else "", info_st),
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

    # ── Title + PO Number ────────────────────────────────────────────────────
    story.append(Paragraph(_t("doc_title", lang), title_st))
    story.append(Paragraph(f"No. {po.number}", sub_st))
    story.append(Spacer(1, 4 * mm))

    # ── PO meta table ────────────────────────────────────────────────────────
    _STATUS_LABELS: dict[str, dict[str, str]] = {
        "rascunho":    {"pt": "Rascunho",    "en": "Draft"},
        "enviado":     {"pt": "Enviado",      "en": "Sent"},
        "aprovado":    {"pt": "Aprovado",     "en": "Approved"},
        "em_execucao": {"pt": "Em Execução",  "en": "In Execution"},
        "concluido":   {"pt": "Concluído",    "en": "Concluded"},
        "cancelado":   {"pt": "Cancelado",    "en": "Cancelled"},
    }
    status_val = _STATUS_LABELS.get(po.status or "rascunho", {}).get(lang, po.status or "–")

    pickup_str = "–"
    if getattr(po, "pickup_datetime", None):
        pickup_str = _fmt_datetime(po.pickup_datetime, lang)

    linked_so_num = ""
    if getattr(po, "order", None):
        linked_so_num = po.order.number
    elif getattr(po, "service_order", None):
        linked_so_num = po.service_order.number

    meta_tbl = Table(
        [[Paragraph(h, cell_hdr) for h in [
            _t("emission", lang), _t("delivery", lang),
            _t("linked_so", lang), _t("vendor_lbl", lang), "STATUS"]],
         [Paragraph(v, cell_body_c) for v in [
            _fmt_date(po.created_at, lang) if getattr(po, "created_at", None) else "–",
            pickup_str, linked_so_num or "–", buyer_name or "–", status_val]]],
        colWidths=[W * 0.16, W * 0.27, W * 0.21, W * 0.22, W * 0.14],
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

    # ── Supplier table ───────────────────────────────────────────────────────
    supplier    = getattr(po, "supplier", None)
    sup_name    = getattr(supplier, "name",     None) or "–"
    sup_contact = getattr(supplier, "contact",  None) or "–"
    sup_email   = getattr(supplier, "email",    None) or "–"
    sup_phone   = getattr(supplier, "phone",    None) or "–"
    sup_doc     = getattr(supplier, "document", None) or "–"

    sup_tbl = Table(
        [[Paragraph(h, cell_hdr) for h in [
            _t("supplier_lbl", lang),
            "Contato" if lang == "pt" else "Contact",
            "Email",
            "Telefone" if lang == "pt" else "Phone",
            "CNPJ/CPF" if lang == "pt" else "Tax ID"]],
         [Paragraph(v, cell_body_c) for v in [
            sup_name, sup_contact, sup_email, sup_phone, sup_doc]]],
        colWidths=[W * 0.28, W * 0.18, W * 0.24, W * 0.16, W * 0.14],
    )
    sup_tbl.setStyle(TableStyle([
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
    story.append(sup_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Compute adjustments ──────────────────────────────────────────────────
    if getattr(po, "items", None):
        subtotal = sum(i.total_cost or 0 for i in po.items)
    else:
        subtotal = getattr(po, "amount", None) or 0.0

    discount_v    = getattr(po, "discount_value",     None) or 0
    discount_type = getattr(po, "discount_type",      None) or "R$"
    other_costs   = getattr(po, "other_costs_amount", None) or 0
    other_lbl_v   = getattr(po, "other_costs_label",  None) or ""
    freight_v     = getattr(po, "freight_amount",     None) or 0
    computed      = po.computed_total

    if discount_type == "%":
        disc_amt     = subtotal * (discount_v / 100)
        disc_row_lbl = f"{_t('discount', lang)} ({discount_v:.2f}%)"
    else:
        disc_amt     = discount_v
        disc_row_lbl = f"{_t('discount', lang)} ({_fmt_brl(discount_v)})" if discount_v else ""

    # ── Items table ──────────────────────────────────────────────────────────
    i_col_w   = [W * 0.05, W * 0.52, W * 0.07, W * 0.17, W * 0.19]
    items_rows = [[
        Paragraph(_t("hash_col",    lang), cell_hdr),
        Paragraph(_t("service_col", lang), cell_hdr_l),
        Paragraph(_t("qty_col",     lang), cell_hdr),
        Paragraph(_t("unit_col",    lang), cell_hdr),
        Paragraph(_t("total_col",   lang), cell_hdr),
    ]]

    if getattr(po, "items", None):
        for idx, item in enumerate(sorted(po.items, key=lambda x: getattr(x, "sort_order", 0) or 0), 1):
            desc = item.description or (item.service.name if getattr(item, "service", None) else "–")
            cat_name = (item.category.name if getattr(item, "category", None) else "") or ""
            svc_lines = [f"<b>{desc}</b>"]
            if cat_name:
                svc_lines.append(f'<font color="#334155" size="7.5">{cat_name}</font>')
            total = item.total_cost or round((item.unit_cost or 0) * (item.quantity or 1), 2)
            items_rows.append([
                Paragraph(str(idx),                                    cell_body_c),
                Paragraph("<br/>".join(svc_lines),                     cell_body),
                Paragraph(str(item.quantity or 1),                     cell_body_c),
                Paragraph(_fmt_brl(item.unit_cost or 0),               cell_body_r),
                Paragraph(_fmt_brl(total),                             cell_body_r),
            ])
    else:
        service  = getattr(po, "service", None)
        svc_name = service.name if service else "–"
        items_rows.append([
            Paragraph("1",                                             cell_body_c),
            Paragraph(f"<b>{svc_name}</b>",                            cell_body),
            Paragraph(str(getattr(po, "pax_count", None) or 1),        cell_body_c),
            Paragraph(_fmt_brl(getattr(po, "amount", None) or 0),      cell_body_r),
            Paragraph(_fmt_brl(subtotal),                              cell_body_r),
        ])

    item_data_end      = len(items_rows)
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

    if freight_v:
        r = len(items_rows)
        items_rows.append([
            Paragraph(f"<i>{_t('freight', lang)}:</i>", cell_body_r),
            "", "", "",
            Paragraph(_fmt_brl(freight_v), cell_body_r),
        ])
        _adj_style_cmds += [
            ("SPAN",          (0, r), (3, r)),
            ("BACKGROUND",    (0, r), (-1, r), colors.HexColor("#fff8e1")),
            ("ALIGN",         (0, r), (-1, r), "RIGHT"),
            ("TOPPADDING",    (0, r), (-1, r), 4),
            ("BOTTOMPADDING", (0, r), (-1, r), 4),
        ]

    if other_costs:
        r = len(items_rows)
        cost_lbl = other_lbl_v or _t("other_costs", lang)
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
    for row_idx in range(1, item_data_end):
        bg = BRAND_LIGHT if row_idx % 2 == 1 else colors.white
        items_style.add("BACKGROUND", (0, row_idx), (-1, row_idx), bg)
    for cmd in _adj_style_cmds:
        items_style.add(*cmd)
    items_tbl.setStyle(items_style)
    story.append(items_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── Payment summary table ────────────────────────────────────────────────
    pay_method_raw = (getattr(po, "payment_method", None) or "").strip()
    pay_terms_raw  = (getattr(po, "payment_terms",  None) or "–").strip()

    pay_sum_tbl = Table(
        [[Paragraph(_t("payment_col",    lang),  cell_hdr),
          Paragraph(_t("prazo_col",       lang),  cell_hdr),
          Paragraph(_t("total_price_col", lang),  cell_hdr)],
         [Paragraph(pay_method_raw or "–",        cell_body_c),
          Paragraph(pay_terms_raw,                 cell_body_c),
          Paragraph(f"<b>{_fmt_brl(computed)}</b>",
                    ParagraphStyle("ctg2", fontSize=10, fontName="Helvetica-Bold",
                                   textColor=BRAND_GOLD, alignment=TA_CENTER, leading=12))]],
        colWidths=[W * 0.36, W * 0.28, W * 0.36],
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

    # ── Installments table ───────────────────────────────────────────────────
    payments_list = list(po.payments) if getattr(po, "payments", None) else []
    if payments_list:
        sorted_pmts = sorted(payments_list, key=lambda p: p.installment_no)
        total_pmts  = len(sorted_pmts)
        inst_rows   = [[
            Paragraph(_t("installment_no", lang), cell_hdr),
            Paragraph(_t("due_date",        lang), cell_hdr),
            Paragraph(_t("amount_col",      lang), cell_hdr),
            Paragraph(_t("payment_status",  lang), cell_hdr),
        ]]
        for pmt in sorted_pmts:
            status_label = _t("status_paid", lang) if pmt.is_paid else _t("status_open", lang)
            st_p = ParagraphStyle("sp", fontSize=8, fontName="Helvetica-Bold",
                                  textColor=colors.white, alignment=TA_CENTER, leading=10)
            inst_rows.append([
                Paragraph(f"{pmt.installment_no}/{total_pmts}", cell_body_c),
                Paragraph(_fmt_date(pmt.due_date, lang),        cell_body_c),
                Paragraph(_fmt_brl(pmt.amount or 0),            cell_body_r),
                Paragraph(status_label,                         st_p),
            ])

        inst_tbl = Table(inst_rows,
                         colWidths=[W * 0.14, W * 0.27, W * 0.31, W * 0.28],
                         repeatRows=1)
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

    # ── Notes ────────────────────────────────────────────────────────────────
    obs = getattr(po, "notes", None) or ""
    if obs:
        story.append(Paragraph(_t("notes_hdr", lang), sec_hdr))
        story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
        bullet_st = ParagraphStyle("obs_bullet", parent=normal, leftIndent=12, firstLineIndent=-8)
        for line in obs.splitlines():
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if not safe.strip():
                story.append(Spacer(1, 3))
            elif safe.lstrip().startswith("- ") or safe.lstrip().startswith("* "):
                text = safe.lstrip()[2:]
                story.append(Paragraph(f"\u2022 {text}", bullet_st))
            else:
                story.append(Paragraph(safe, normal))
        story.append(Spacer(1, 4 * mm))

    # ── Informações Importantes ──────────────────────────────────────────────
    info_hdr_lbl = "Informações Importantes" if lang == "pt" else "Important Information"
    info_items = [
        ("Hora Extra: 10% sobre o valor total da diária, a partir de 30 minutos de despera." if lang == "pt" else "Overtime: 10% of the total daily rate, after 30 minutes of waiting."),
    ]
    info_bullet_st = ParagraphStyle("info_bullet", parent=normal, leftIndent=12, firstLineIndent=-8)
    story.append(Paragraph(info_hdr_lbl, sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    for txt in info_items:
        story.append(Paragraph(f"• {txt}", info_bullet_st))
    story.append(Spacer(1, 4 * mm))

    # ── Operational Data ─────────────────────────────────────────────────────
    op_driver   = getattr(po, "driver_name",        None) or ""
    op_dphone   = getattr(po, "driver_phone",       None) or ""
    op_modelo   = getattr(po, "vehicle_model",      None) or ""
    op_obs      = getattr(po, "vehicle_description",None) or ""
    op_plate    = getattr(po, "vehicle_plate",      None) or ""
    op_pickup   = _fmt_datetime(getattr(po, "pickup_datetime", None), lang)
    op_from     = getattr(po, "pickup_location",    None) or ""
    op_to       = getattr(po, "dropoff_location",   None) or ""
    op_pax      = getattr(po, "passenger_name",     None) or ""
    op_pphone   = getattr(po, "passenger_phone",    None) or ""
    op_flight   = getattr(po, "flight_number",      None) or ""
    op_pax_cnt  = getattr(po, "pax_count",          None)

    _op_has_data = any([op_driver, op_modelo, op_plate, op_from, op_to,
                        op_pax, op_flight, op_pax_cnt])

    if _op_has_data:
        story.append(Spacer(1, 6 * mm))

        # ── Header bar ──────────────────────────────────────────────────────
        lbl_st = ParagraphStyle(
            "op_lbl", fontName="Helvetica-Bold", fontSize=7,
            textColor=colors.HexColor("#64748b"), spaceAfter=1,
        )
        val_st = ParagraphStyle(
            "op_val", fontName="Helvetica-Bold", fontSize=9.5,
            textColor=BRAND_DARK, spaceAfter=0,
        )
        hdr_st = ParagraphStyle(
            "op_hdr_st", fontName="Helvetica-Bold", fontSize=10,
            textColor=colors.white, alignment=TA_CENTER,
        )

        hdr_cell = Paragraph(_t("op_hdr", lang), hdr_st)
        hdr_tbl  = Table([[hdr_cell]], colWidths=[W])
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS",(0, 0), (-1, -1), [4, 4, 0, 0]),
        ]))
        story.append(hdr_tbl)

        # ── Info grid — flat 4-col table: lbl1 | val1 | lbl2 | val2 ──────────
        _op_pickup_str = op_pickup if op_pickup != "–" else "–"
        if op_pax_cnt:
            _op_pickup_str = (_op_pickup_str + f"  •  {op_pax_cnt} PAX").strip(" • ")

        op_rows_raw = [
            ("op_driver",    op_driver,        "op_driver_phone", op_dphone),
            ("op_modelo",    op_modelo,        "op_plate",        op_plate),
            ("op_pickup",    _op_pickup_str,   "op_flight",       op_flight),
            ("op_from",      op_from,          "op_to",           op_to),
            ("op_passenger", op_pax,           "op_pax_phone",    op_pphone),
            ("op_obs",       op_obs,           "",                ""),
        ]

        # 4 columns: label-left | value-left | label-right | value-right
        CL = W * 0.18   # label column width
        CV = W * 0.32   # value column width

        grid_rows = []
        span_rows = []  # row indices that span full width
        for lk1, v1, lk2, v2 in op_rows_raw:
            if not v1 and not v2:
                continue
            if not lk2:
                # full-width row: label | value spanning cols 1-3
                span_rows.append(len(grid_rows))
                grid_rows.append([
                    Paragraph(_t(lk1, lang).upper(), lbl_st),
                    Paragraph(v1 or "–", val_st),
                    Paragraph("", lbl_st),
                    Paragraph("", val_st),
                ])
            else:
                grid_rows.append([
                    Paragraph(_t(lk1, lang).upper(), lbl_st),
                    Paragraph(v1 or "–", val_st),
                    Paragraph(_t(lk2, lang).upper(), lbl_st),
                    Paragraph(v2 or "–", val_st),
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
                # shade label columns lightly
                ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BACKGROUND",    (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
                *span_cmds,
            ]))
            story.append(grid_tbl)

        story.append(Spacer(1, 5 * mm))

    # ── Signature area ────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    sig_data = [[
        Paragraph(f"___________________________<br/><font size='7' color='#94a3b8'>"
                  f"{_t('approved_by', lang)}</font>",
                  ParagraphStyle("sg1", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
        Paragraph(f"___________________________<br/><font size='7' color='#94a3b8'>"
                  f"{_t('supplier_sig', lang)}</font>",
                  ParagraphStyle("sg2", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
        Paragraph(f"___________________________<br/><font size='7' color='#94a3b8'>"
                  f"{_t('date_sig', lang)}</font>",
                  ParagraphStyle("sg3", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
    ]]
    sig_tbl = Table(sig_data, colWidths=[W / 3, W / 3, W / 3])
    sig_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(sig_tbl)

    # ── Footer callback ───────────────────────────────────────────────────────
    from datetime import datetime as _dt  # noqa: PLC0415
    cnpj_lbl_footer = "CNPJ" if lang == "pt" else "TAX ID"
    tax_part        = (f"{company_name} \u2022 {cnpj_lbl_footer} {company_doc}"
                       if company_doc else company_name)
    now_str         = _dt.now().strftime("%m/%d/%Y %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
    _footer_line    = f"{_t('generated', lang)} {now_str}   \u2022   {tax_part}"
    _lm, _rm, _pw  = 15 * mm, A4[0] - 15 * mm, A4[0]

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
