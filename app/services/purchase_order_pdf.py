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
    NextPageTemplate,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.lib.pagesizes import landscape as _landscape

# Re-use brand constants + helpers from quote_pdf
from .quote_pdf import BRAND_DARK, BRAND_GOLD, BRAND_LIGHT, _fmt_brl, _fmt_phone_link, _fmt_time_12h, _get_vehicle_model, _translate_service, _translate_vehicle, _translate_driver


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
    "linked_so":       {"pt": "SO VINCULADO",               "en": "LINKED SO"},
    "payment":         {"pt": "FORMA PGTO.",                "en": "PAYMENT"},
    "supplier_lbl":    {"pt": "FORNECEDOR",                 "en": "SUPPLIER"},
    "supplier_hdr":    {"pt": "FORNECEDOR",                 "en": "SUPPLIER"},
    "service_col":     {"pt": "SERVIÇO",                     "en": "SERVICE"},
    "hash_col":        {"pt": "#",                          "en": "#"},
    "qty_col":         {"pt": "QTD",                        "en": "QTY"},
    "unit_col":        {"pt": "UNIT. R$",                   "en": "UNIT R$"},
    "total_col":       {"pt": "TOTAL R$",                   "en": "TOTAL R$"},
    "discount":        {"pt": "DESCONTO",                   "en": "DISCOUNT"},
    "freight":         {"pt": "FRETE",                      "en": "FREIGHT"},
    "other_costs":     {"pt": "CUSTOS EXTRAS",              "en": "EXTRA COSTS"},
    "payment_col":     {"pt": "FORMA DE PAGAMENTO",         "en": "PAYMENT METHOD"},
    "prazo_col":       {"pt": "PRAZO",                      "en": "TERMS"},
    "total_price_col": {"pt": "PREÇO TOTAL",                "en": "TOTAL PRICE"},
    "installment_no":  {"pt": "PARCELA",                    "en": "INSTALLMENT"},
    "due_date":        {"pt": "VENCIMENTO",                 "en": "DUE DATE"},
    "amount_col":      {"pt": "VALOR (R$)",                 "en": "AMOUNT (R$)"},
    "payment_status":  {"pt": "PAGAMENTO",                  "en": "PAYMENT"},
    "status_paid":     {"pt": "PAGO",                       "en": "PAID"},
    "status_open":     {"pt": "PENDENTE",                   "en": "PENDING"},
    "notes_hdr":       {"pt": "OBSERVAÇÕES",                "en": "NOTES"},
    "approved_by":     {"pt": "APROVADO POR",               "en": "APPROVED BY"},
    "supplier_sig":    {"pt": "FORNECEDOR",                 "en": "SUPPLIER"},
    "date_sig":        {"pt": "DATA",                       "en": "DATE"},
    "emission":        {"pt": "DATA DE EMISSÃO",            "en": "ISSUE DATE"},
    "delivery":        {"pt": "DATA PICKUP",                "en": "PICKUP DATE"},
    "vendor_lbl":      {"pt": "COMPRADOR",                  "en": "BUYER"},
    "generated":       {"pt": "GERADO EM",                  "en": "GENERATED ON"},
    # Operational
    "op_hdr":          {"pt": "DADOS OPERACIONAIS",           "en": "OPERATIONAL DATA"},
    "op_driver":       {"pt": "MOTORISTA",                    "en": "DRIVER"},
    "op_driver_phone": {"pt": "FONE",                          "en": "PHONE"},
    "op_modelo":       {"pt": "MODELO",                        "en": "MODEL"},
    "op_plate":        {"pt": "PLACA",                        "en": "PLATE"},
    "op_pickup":       {"pt": "DATA / HORA PICKUP",            "en": "PICKUP DATE/TIME"},
    "op_pickup_date":  {"pt": "DATA PICKUP",                  "en": "PICKUP DATE"},
    "op_pickup_time":  {"pt": "HORA PICKUP",                  "en": "PICKUP TIME"},
    "op_from":         {"pt": "EMBARQUE",                        "en": "PICKUP LOCATION"},
    "op_to":           {"pt": "DESEMBARQUE",                     "en": "DROPOFF LOCATION"},
    "op_passenger":    {"pt": "PASSAGEIRO",                   "en": "PASSENGER"},
    "op_pax_phone":    {"pt": "FONE PAX",                      "en": "PASSENGER PHONE"},
    "op_flight":       {"pt": "Nº VOO",                       "en": "FLIGHT NO."},
    "op_pax":          {"pt": "PAX",                          "en": "PAX"},
    "op_obs":          {"pt": "OBSERVAÇÕES",                  "en": "NOTES"},
}


def _t(key: str, lang: str) -> str:
    entry = _LABELS.get(key, {})
    return entry.get(lang) or entry.get("pt") or key


# ─── Standalone Sign PDF ──────────────────────────────────────────────────────

def generate_sign_pdf(text: str = "", img_path: str = "", img_pos: str = "abaixo") -> io.BytesIO:
    """Gera PDF standalone com uma página landscape para placa de receptivo."""
    buffer = io.BytesIO()
    ls_page = _landscape(A4)
    ls_W = ls_page[0] - 40 * mm
    ls_frame = Frame(20 * mm, 20 * mm, ls_W, ls_page[1] - 40 * mm, id='main')
    templates = [PageTemplate(id='Main', frames=[ls_frame], pagesize=ls_page)]
    doc = BaseDocTemplate(buffer, pageTemplates=templates)

    story = []
    _render_sign_page(story, text, img_path, img_pos)
    doc.build(story)
    buffer.seek(0)
    return buffer


def _render_sign_page(story: list, text: str, img_path: str, img_pos: str):
    """Adiciona conteúdo da placa de receptivo a uma story (reutilizável)."""
    ls_W_val = _landscape(A4)[0] - 40 * mm

    img_flowable = None
    if img_path:
        try:
            from flask import current_app
            full = os.path.join(current_app.config["UPLOAD_FOLDER"],
                               img_path.replace('/uploads/', '').lstrip('/'))
            if os.path.isfile(full):
                if img_pos == 'centro' and not text:
                    img_flowable = RLImage(full, width=ls_W_val * 0.9, height=140 * mm, kind="proportional")
                else:
                    img_flowable = RLImage(full, width=ls_W_val * 0.4, height=40 * mm, kind="proportional")
        except Exception:
            pass

    if text:
        name_len = len(text)
        if name_len <= 10:   fs = 96
        elif name_len <= 20: fs = 80
        else:                fs = 64
        sign_st = ParagraphStyle("placa_st", fontSize=fs, fontName="Helvetica-Bold",
                                  textColor=BRAND_DARK, alignment=TA_CENTER, leading=fs * 1.15)
        story.append(Spacer(1, 30 * mm if (img_flowable and img_pos != 'centro') else 50 * mm))
        story.append(Paragraph(text, sign_st))
        story.append(Spacer(1, 15 * mm))
        story.append(HRFlowable(width=ls_W_val * 0.5, thickness=2, color=BRAND_GOLD,
                                 spaceAfter=15 * mm, hAlign="CENTER"))
        if img_flowable:
            img_tbl = Table([[img_flowable]], colWidths=[ls_W_val])
            img_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(img_tbl)
    elif img_flowable:
        story.append(Spacer(1, 30 * mm))
        img_tbl = Table([[img_flowable]], colWidths=[ls_W_val])
        img_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(img_tbl)


# ─── Generator ───────────────────────────────────────────────────────────────

def generate_po_pdf(po, lang: str = "pt") -> io.BytesIO:
    """Return a BytesIO containing the PO PDF (same visual style as SO PDF)."""
    buffer = io.BytesIO()
    W = A4[0] - 30 * mm

    # Placas de receptivo (páginas landscape extras)
    _placas = []  # [(text, img_path, img_pos), ...]
    for it in (po.items or []):
        if getattr(it, 'placa_receptivo', None):
            txt = (getattr(it, 'placa_receptivo_texto', '') or '').strip()
            img = (getattr(it, 'placa_imagem', '') or '').strip()
            pos = (getattr(it, 'placa_imagem_pos', '') or 'abaixo').strip()
            if txt or img:
                _placas.append((txt, img, pos))

    portrait_frame = Frame(15 * mm, 20 * mm, W, A4[1] - 35 * mm, id='portrait')
    templates = [PageTemplate(id='Portrait', frames=[portrait_frame], pagesize=A4)]
    if _placas:
        ls_page = _landscape(A4)
        ls_W = ls_page[0] - 40 * mm
        ls_frame = Frame(20 * mm, 20 * mm, ls_W, ls_page[1] - 40 * mm, id='landscape')
        templates.append(PageTemplate(id='Landscape', frames=[ls_frame], pagesize=ls_page))

    doc = BaseDocTemplate(
        buffer,
        pageTemplates=templates,
        title=f"{_t('doc_title', lang)} {po.number}",
    )

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

    # ── Header: logo left + title/number right ──────────────────────────────
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

    info_st = ParagraphStyle("inf", fontSize=8.5, textColor=BRAND_DARK,
                             alignment=TA_RIGHT, leading=13)
    def _clean(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() == "none":
            return None
        return s

    # Load company logo
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
                logo_img = RLImage(logo_path, width=100 * mm, height=20 * mm, kind="proportional")
        except Exception:
            logo_img = None

    left_cell  = logo_img if logo_img else Paragraph(f"<b>{company_name.upper()}</b>",
                ParagraphStyle("hc", fontSize=12, fontName="Helvetica-Bold",
                               textColor=BRAND_DARK, alignment=TA_LEFT))
    right_cell = Paragraph(
        f"<b>{_t('doc_title', lang)}</b><br/><font color='#b88b2d' size='9'><b>No. {po.number}</b></font>",
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

    # ── PO meta table ────────────────────────────────────────────────────────
    _STATUS_LABELS: dict[str, dict[str, str]] = {
        "rascunho":    {"pt": "Rascunho",    "en": "Draft"},
        "aberto":      {"pt": "Aberto",      "en": "Open"},
        "enviado":     {"pt": "Aberto",      "en": "Open"},
        "aprovado":    {"pt": "Aprovado",     "en": "Approved"},
        "em_execucao": {"pt": "Em Execução",  "en": "In Execution"},
        "concluido":   {"pt": "Concluído",    "en": "Concluded"},
        "cancelado":   {"pt": "Cancelado",    "en": "Cancelled"},
    }
    status_val = _STATUS_LABELS.get(po.status or "rascunho", {}).get(lang, po.status or "–")

    pickup_str = "–"
    if getattr(po, "pickup_datetime", None):
        pickup_str = _fmt_date(po.pickup_datetime, lang)
    else:
        # fallback: primeiro item com op_pickup_datetime
        items_list = list(getattr(po, "items", None) or [])
        for _it in items_list:
            _dt = getattr(_it, "op_pickup_datetime", None)
            if _dt:
                pickup_str = _fmt_date(_dt, lang)
                break

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
            "CONTATO" if lang == "pt" else "CONTACT",
            "EMAIL",
            "TELEFONE" if lang == "pt" else "PHONE",
            "CNPJ/CPF" if lang == "pt" else "TAX ID"]],
         [Paragraph(v, cell_body_c) for v in [
            sup_name, sup_contact, sup_email, sup_phone, sup_doc]]],
        colWidths=[W * 0.22, W * 0.17, W * 0.23, W * 0.16, W * 0.22],
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
        Paragraph(_t("service_col", lang), cell_hdr),
        Paragraph(_t("qty_col",     lang), cell_hdr),
        Paragraph(_t("unit_col",    lang), cell_hdr),
        Paragraph(_t("total_col",   lang), cell_hdr),
    ]]

    if getattr(po, "items", None):
        for idx, item in enumerate(sorted(po.items, key=lambda x: getattr(x, "sort_order", 0) or 0), 1):
            service_name_raw = item.description or (item.service.name if getattr(item, "service", None) else "–")
            cat_name_raw = (item.category.name if getattr(item, "category", None) else "") or ""
            driver_name_raw = getattr(item, 'op_driver_name', '') or ''

            desc = _translate_service(service_name_raw, lang, cat_name_raw)
            cat_name = _translate_vehicle(cat_name_raw, lang)
            driver_disp = _translate_driver(driver_name_raw, lang)
            date_prefix = ''
            if getattr(item, 'service_date', None):
                if lang == 'en':
                    date_prefix = item.service_date.strftime('%m/%d')
                else:
                    date_prefix = item.service_date.strftime('%d/%m')
                if getattr(item, 'service_time', None):
                    h = item.service_time.hour
                    m = item.service_time.minute
                    ampm = 'AM' if h < 12 else 'PM'
                    h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
                    date_prefix += f' {h12}:{m:02d} {ampm}'
            if date_prefix:
                desc = f'{date_prefix} – {desc}'

            # Build sub-label: driver + category + vehicle model
            sub_parts = []
            if driver_disp:
                sub_parts.append(driver_disp)
            if cat_name:
                sub_parts.append(cat_name)
            cat_display = " – ".join(sub_parts)
            vehicle_model = item.vehicle_description or _get_vehicle_model(cat_name_raw, lang) or ''
            if vehicle_model and cat_display:
                cat_display = f'{cat_display} ({vehicle_model})'

            svc_lines = [f"<b>{desc}</b>"]
            if cat_display:
                svc_lines.append(f'<font color="#334155" size="7.5">{cat_display}</font>')
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
            st_p = ParagraphStyle("sp", fontSize=7, fontName="Helvetica-Bold",
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
    story.append(Paragraph(_t("notes_hdr", lang), sec_hdr))
    story.append(HRFlowable(width=W, thickness=1, color=BRAND_GOLD, spaceAfter=3))
    bullet_st = ParagraphStyle("obs_bullet", parent=normal, leftIndent=12, firstLineIndent=-8)
    if po.status != "faturado":
        hora_extra_txt = (
            "Hora Extra: 10% sobre o valor total da diária, a partir de 30 minutos de despera."
            if lang == "pt" else
            "Overtime: 10% of the total daily rate, after 30 minutes of waiting."
        )
        story.append(Paragraph(f"• {hora_extra_txt}", bullet_st))
    if obs:
        from ..utils.translate import translate_obs
        obs_text = translate_obs(obs, lang) if lang != "pt" else obs
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
    op_value_st = ParagraphStyle(
        "po_op_value", fontName="Helvetica", fontSize=7.5,
        textColor=BRAND_DARK, leading=10, spaceAfter=0,
    )
    op_title_st = ParagraphStyle(
        "po_op_title", fontName="Helvetica-Bold", fontSize=8,
        textColor=colors.white, alignment=TA_LEFT, leading=10,
    )

    items_sorted = sorted(po.items, key=lambda it: (getattr(it, "sort_order", 0) or 0, it.id))
    item_index   = {it.id: i + 1 for i, it in enumerate(items_sorted)}

    # Dados operacionais omitidos no PDF pós-faturamento
    op_groups: list[tuple[tuple, list]] = []  # [(key_tuple, [items])]
    if po.status != "faturado":
        for it in items_sorted:
            op_pickup_dt = getattr(it, "op_pickup_datetime", None)
            pax_cnt      = getattr(it, "op_pax_count", None)
            key = (
                op_pickup_dt.isoformat() if op_pickup_dt else "",
                (getattr(it, "op_pickup_location", "") or "").strip(),
                (getattr(it, "op_dropoff_location", "") or "").strip(),
                (getattr(it, "op_passenger_name", "") or "").strip(),
                (getattr(it, "op_passenger_phone", "") or "").strip(),
                (getattr(it, "op_flight_number", "") or "").strip(),
                str(pax_cnt) if pax_cnt else "",
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
        story.append(Spacer(1, 4 * mm))

    for key, items in op_groups:
        sample = items[0]
        pickup_dt = getattr(sample, "op_pickup_datetime", None)
        pickup_date_str = _fmt_date(pickup_dt.date() if pickup_dt else None, lang) if pickup_dt else ""
        if pickup_date_str == "\u2013":
            pickup_date_str = ""
        pickup_time_str = _fmt_time_12h(pickup_dt, lang) if pickup_dt else ""

        fields = [
            ("op_passenger",    key[3]),
            ("op_pax_phone",    key[4]),
            ("op_flight",       key[5]),
            ("op_pax",          key[6]),
            ("op_pickup_date",  pickup_date_str),
            ("op_pickup_time",  pickup_time_str),
            ("op_from",         key[1]),
            ("op_to",           key[2]),
            ("op_obs",          key[7]),
        ]
        filled = [(lk, v) for lk, v in fields if v]
        if not filled:
            continue

        # Header com subtítulo (quais itens)
        if len(items) == total_items and total_items > 1:
            sub = "Todos os itens" if lang == "pt" else "All items"
        else:
            nums = ", ".join(f"#{item_index[it.id]}" for it in items)
            sub = (f"Item {nums}" if len(items) == 1 else
                   (f"Itens {nums}" if lang == "pt" else f"Items {nums}"))
        hdr_text = f"{_t('op_hdr', lang)} \u2014 {sub}"

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
        # op_obs é separado para ocupar linha inteira
        obs_entry = next(((lk, v) for lk, v in filled if lk == "op_obs"), None)
        filled_main = [(lk, v) for lk, v in filled if lk != "op_obs"]

        COLS = 4
        cells = []
        for lk, v in filled_main:
            label = _t(lk, lang)
            if lk in ("op_driver_phone", "op_pax_phone") and v and any(c.isdigit() for c in v):
                add_55 = (lk == "op_driver_phone")
                safe = _fmt_phone_link(v, add_country=add_55)
            else:
                safe = (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            cells.append(Paragraph(f"<b>{label}:</b> {safe}", op_value_st))

        if cells:
            while len(cells) % COLS != 0:
                cells.append(Paragraph("", op_value_st))
            rows = [cells[i:i + COLS] for i in range(0, len(cells), COLS)]

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

        if obs_entry:
            obs_label = _t(obs_entry[0], lang)
            obs_safe  = (obs_entry[1] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            obs_tbl = Table(
                [[Paragraph(f"<b>{obs_label}:</b> {obs_safe}", op_value_st)]],
                colWidths=[W],
            )
            obs_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(obs_tbl)
        story.append(Spacer(1, 2 * mm))

    if op_groups:
        story.append(Spacer(1, 3 * mm))

    # ── Placas de Receptivo (páginas landscape) ──────────────────────────────
    for _ptext, _pimg, _ppos in _placas:
        story.append(NextPageTemplate('Landscape'))
        story.append(PageBreak())
        _render_sign_page(story, _ptext, _pimg, _ppos)

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

    templates[0].onPage = _draw_footer
    doc.build(story)
    buffer.seek(0)
    return buffer
