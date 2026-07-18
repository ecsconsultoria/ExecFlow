"""PDF generator for receptive sign (placa de receptivo) — landscape A4."""
from __future__ import annotations

import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND_DARK = colors.HexColor("#0b0b0b")
BRAND_GOLD = colors.HexColor("#b88b2d")


def generate_sign_pdf(po, name: str, include_logo: bool = True) -> io.BytesIO:
    """Retorna BytesIO com PDF paisagem para placa de receptivo."""
    buffer = io.BytesIO()
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )

    W = page_w - 40 * mm  # usable width
    H = page_h - 35 * mm  # usable height

    name_style = ParagraphStyle("sign_name", fontSize=48, fontName="Helvetica-Bold",
                                 textColor=BRAND_DARK, alignment=TA_CENTER, leading=54)
    story = []

    # Espaço vertical para centralizar o nome
    story.append(Spacer(1, H * 0.30))

    # Nome do cliente
    display_name = (name or "").strip() or "Convidado"
    story.append(Paragraph(display_name, name_style))
    story.append(Spacer(1, 12 * mm))

    # Linha decorativa dourada
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(width=W * 0.4, thickness=1.5, color=BRAND_GOLD,
                             spaceAfter=12 * mm, hAlign="CENTER"))

    # Logo no bottom (se solicitado)
    if include_logo:
        company = getattr(po, "company", None)
        logo_url = (company.logo_url if company else None) if company else None
        logo_img = None
        if logo_url:
            try:
                from reportlab.platypus import Image as RLImage
                from flask import current_app
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
                    logo_img = RLImage(logo_path, width=80 * mm, height=20 * mm,
                                       kind="proportional")
            except Exception:
                logo_img = None

        story.append(Spacer(1, 40 * mm))
        if logo_img:
            logo_tbl = Table([[logo_img]], colWidths=[W])
            logo_tbl.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            story.append(logo_tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer
