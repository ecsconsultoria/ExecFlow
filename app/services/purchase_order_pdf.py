"""PDF generator for Purchase Orders (PO) — Portuguese version."""
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
    _fmt_brl,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    if d is None:
        return "–"
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _safe(val, default="–") -> str:
    return str(val) if val else default


def _style(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


# ─── Generator ───────────────────────────────────────────────────────────────

def generate_po_pdf(po) -> io.BytesIO:
    """Return a BytesIO containing the PO PDF."""
    buf = io.BytesIO()
    PAGE_W, PAGE_H = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
    )

    W = PAGE_W - 2 * margin
    story = []

    # ── Styles ────────────────────────────────────────────────────────────────
    GREY_TEXT = colors.HexColor("#64748b")
    VIOLET    = colors.HexColor("#7c3aed")
    WHITE     = colors.white
    DARK      = colors.HexColor(f"#{BRAND_DARK:06x}") if isinstance(BRAND_DARK, int) else BRAND_DARK
    GOLD      = colors.HexColor(f"#{BRAND_GOLD:06x}") if isinstance(BRAND_GOLD, int) else BRAND_GOLD

    s_title = _style("title", fontName="Helvetica-Bold", fontSize=18, textColor=VIOLET,
                     alignment=TA_LEFT, spaceBefore=0, spaceAfter=2)
    s_sub   = _style("sub",   fontName="Helvetica",      fontSize=9,  textColor=GREY_TEXT,
                     alignment=TA_LEFT)
    s_lbl   = _style("lbl",   fontName="Helvetica-Bold", fontSize=7,  textColor=GREY_TEXT,
                     alignment=TA_LEFT)
    s_val   = _style("val",   fontName="Helvetica",      fontSize=9,  textColor=colors.black,
                     alignment=TA_LEFT)
    s_hdr   = _style("hdr",   fontName="Helvetica-Bold", fontSize=8,  textColor=WHITE,
                     alignment=TA_CENTER)
    s_cell  = _style("cell",  fontName="Helvetica",      fontSize=8,  textColor=colors.black,
                     alignment=TA_LEFT)
    s_cellr = _style("cellr", fontName="Helvetica-Bold", fontSize=8,  textColor=colors.black,
                     alignment=TA_RIGHT)
    s_total = _style("total", fontName="Helvetica-Bold", fontSize=12, textColor=VIOLET,
                     alignment=TA_RIGHT)

    # ── Logo / Header row ─────────────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), "..", "static", "images", "logo.png")
    logo_path = os.path.normpath(logo_path)

    company = po.company if hasattr(po, "company") and po.company else None
    company_name = company.name if company and hasattr(company, "name") else "Executive BR"

    title_cell = [
        Paragraph("PURCHASE ORDER", _style("po_title", fontName="Helvetica-Bold",
                                           fontSize=22, textColor=VIOLET, alignment=TA_RIGHT)),
        Paragraph(f"<b>{_safe(po.number)}</b>",
                  _style("po_num", fontName="Helvetica-Bold", fontSize=14,
                         textColor=DARK, alignment=TA_RIGHT)),
    ]
    company_cell = [
        Paragraph(f"<b>{company_name}</b>",
                  _style("co", fontName="Helvetica-Bold", fontSize=11,
                         textColor=DARK, alignment=TA_LEFT)),
    ]

    try:
        from reportlab.platypus import Image
        if os.path.exists(logo_path):
            logo_img = Image(logo_path, width=40 * mm, height=12 * mm, kind="proportional")
            header_data = [[logo_img, title_cell]]
        else:
            header_data = [[company_cell, title_cell]]
    except Exception:
        header_data = [[company_cell, title_cell]]

    header_tbl = Table(header_data, colWidths=[W * 0.5, W * 0.5])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width=W, thickness=2, color=VIOLET, spaceAfter=6))

    # ── Meta info row ─────────────────────────────────────────────────────────
    linked_so_num = ""
    if hasattr(po, "order") and po.order:
        linked_so_num = po.order.number
    elif hasattr(po, "service_order") and po.service_order:
        linked_so_num = po.service_order.number

    pickup_str = "–"
    if po.pickup_datetime:
        try:
            pickup_str = po.pickup_datetime.strftime("%d/%m/%Y %H:%M")
        except Exception:
            pickup_str = str(po.pickup_datetime)

    meta_data = [
        [Paragraph("Nº PO", s_lbl),       Paragraph("Data Pickup", s_lbl),
         Paragraph("SO Vinculada", s_lbl), Paragraph("Forma Pagto.", s_lbl)],
        [Paragraph(f"<b>{_safe(po.number)}</b>", s_val),
         Paragraph(pickup_str, s_val),
         Paragraph(_safe(linked_so_num), s_val),
         Paragraph(_safe(po.payment_method), s_val)],
    ]
    meta_tbl = Table(meta_data, colWidths=[W * 0.22, W * 0.26, W * 0.26, W * 0.26])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("ROWBACKGROUNDS",(0, 1), (-1, 1), [colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 6))

    # ── Supplier table ────────────────────────────────────────────────────────
    supplier = po.supplier if hasattr(po, "supplier") and po.supplier else None
    sup_name    = supplier.name     if supplier else "–"
    sup_contact = supplier.contact  if supplier else "–"
    sup_email   = supplier.email    if supplier else "–"
    sup_phone   = supplier.phone    if supplier else "–"
    sup_doc     = supplier.document if supplier else "–"

    sup_header = Table(
        [[Paragraph("FORNECEDOR", _style("sh", fontName="Helvetica-Bold", fontSize=8,
                                         textColor=WHITE, alignment=TA_LEFT))]],
        colWidths=[W],
    )
    sup_header.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), DARK),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(sup_header)

    sup_data = [
        [Paragraph("Nome", s_lbl),     Paragraph("Contato", s_lbl),
         Paragraph("Email", s_lbl),    Paragraph("Telefone", s_lbl),  Paragraph("CNPJ/CPF", s_lbl)],
        [Paragraph(sup_name, s_val),   Paragraph(_safe(sup_contact), s_val),
         Paragraph(_safe(sup_email), s_val), Paragraph(_safe(sup_phone), s_val),
         Paragraph(_safe(sup_doc), s_val)],
    ]
    sup_tbl = Table(sup_data, colWidths=[W * 0.28, W * 0.18, W * 0.24, W * 0.16, W * 0.14])
    sup_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sup_tbl)
    story.append(Spacer(1, 6))

    # ── Service / Items table ─────────────────────────────────────────────────
    service = po.service if hasattr(po, "service") and po.service else None
    svc_code = f"{service.id:03d} – {service.name}" if service else "–"
    qty_str   = str(po.pax_count or 1)
    unit_str  = _fmt_brl(po.amount or 0)
    total_str = _fmt_brl((po.pax_count or 1) * (po.amount or 0))

    svc_header = Table(
        [[Paragraph("SERVIÇO / CUSTO", _style("svch", fontName="Helvetica-Bold", fontSize=8,
                                               textColor=WHITE, alignment=TA_LEFT))]],
        colWidths=[W],
    )
    svc_header.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), DARK),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(svc_header)

    items_data = [
        [Paragraph("Serviço", s_hdr),    Paragraph("Qtd", s_hdr),
         Paragraph("Unit. R$", s_hdr),   Paragraph("Total R$", s_hdr)],
        [Paragraph(svc_code, s_cell),    Paragraph(qty_str, _style("qc", fontName="Helvetica", fontSize=8, alignment=TA_CENTER)),
         Paragraph(unit_str, _style("ur", fontName="Helvetica", fontSize=8, alignment=TA_RIGHT)),
         Paragraph(total_str, _style("tr2", fontName="Helvetica-Bold", fontSize=8, textColor=VIOLET, alignment=TA_RIGHT))],
    ]
    # Operational details row if available
    op_details = []
    if po.pickup_location:
        op_details.append(f"Embarque: {po.pickup_location}")
    if po.dropoff_location:
        op_details.append(f"Desembarque: {po.dropoff_location}")
    if po.passenger_name:
        op_details.append(f"Passageiro: {po.passenger_name}")
    if po.driver_name:
        op_details.append(f"Motorista: {po.driver_name}")
    if po.vehicle_description:
        op_details.append(f"Veículo: {po.vehicle_description}")
    if po.flight_number:
        op_details.append(f"Voo: {po.flight_number}")
    if op_details:
        items_data.append([
            Paragraph(" · ".join(op_details),
                      _style("op", fontName="Helvetica-Oblique", fontSize=7,
                             textColor=GREY_TEXT, alignment=TA_LEFT)),
            "", "", "",
        ])

    items_tbl = Table(items_data, colWidths=[W * 0.50, W * 0.10, W * 0.20, W * 0.20])
    items_style = [
        ("BACKGROUND",   (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("ALIGN",        (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN",        (1, 0), (1, -1), "CENTER"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if op_details:
        items_style += [
            ("SPAN",         (0, 2), (-1, 2)),
            ("BACKGROUND",   (0, 2), (-1, 2), colors.HexColor("#f5f3ff")),
        ]
    items_tbl.setStyle(TableStyle(items_style))
    story.append(items_tbl)

    # Total row
    total_data = [[
        Paragraph("TOTAL DA PO", _style("tlbl", fontName="Helvetica-Bold", fontSize=9,
                                         textColor=GREY_TEXT, alignment=TA_RIGHT)),
        Paragraph(total_str, _style("tval", fontName="Helvetica-Bold", fontSize=12,
                                    textColor=VIOLET, alignment=TA_RIGHT)),
    ]]
    total_tbl = Table(total_data, colWidths=[W * 0.80, W * 0.20])
    total_tbl.setStyle(TableStyle([
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEABOVE",    (0, 0), (-1, 0), 1, VIOLET),
    ]))
    story.append(total_tbl)
    story.append(Spacer(1, 6))

    # ── Notes ─────────────────────────────────────────────────────────────────
    if po.notes:
        notes_hdr = Table(
            [[Paragraph("OBSERVAÇÕES", _style("nh", fontName="Helvetica-Bold", fontSize=8,
                                               textColor=WHITE, alignment=TA_LEFT))]],
            colWidths=[W],
        )
        notes_hdr.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#475569")),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(notes_hdr)
        notes_body = Table(
            [[Paragraph(po.notes.replace("\n", "<br/>"),
                        _style("nb", fontName="Helvetica-Oblique", fontSize=8,
                               textColor=colors.black, alignment=TA_LEFT))]],
            colWidths=[W],
        )
        notes_body.setStyle(TableStyle([
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(notes_body)
        story.append(Spacer(1, 6))

    # ── Signature area ────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    sig_data = [[
        Paragraph("___________________________<br/><font size='7' color='#94a3b8'>Aprovado por</font>",
                  _style("sg1", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
        Paragraph("___________________________<br/><font size='7' color='#94a3b8'>Fornecedor</font>",
                  _style("sg2", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
        Paragraph("___________________________<br/><font size='7' color='#94a3b8'>Data</font>",
                  _style("sg3", fontName="Helvetica", fontSize=9, alignment=TA_CENTER)),
    ]]
    sig_tbl = Table(sig_data, colWidths=[W / 3, W / 3, W / 3])
    sig_tbl.setStyle(TableStyle([
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(sig_tbl)

    doc.build(story)
    return buf
