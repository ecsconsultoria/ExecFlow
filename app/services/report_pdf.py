"""report_pdf.py — Relatórios financeiros em PDF (Etapa 12E).

Wrapper ReportLab com identidade visual única para os relatórios do ExecFlow:

  * cabeçalho com logo da empresa (quando disponível);
  * título do relatório + período + filtros utilizados;
  * tabelas com cabeçalho destacado, zebra e linha de totais;
  * BRL formatado (R$ 1.234,56), negativos em vermelho;
  * rodapé com paginação ("Página N de M"), data/hora e usuário que gerou.

Fonte: Arial TTF embutida (app/static/fonts) — cobre acentos e caracteres
especiais (ó, ê, à, ç, —, R$) que as fontes Type1 padrão do ReportLab
(Helvetica, latin-1) perderiam. Sem a fonte, fallback para Helvetica.

SOMENTE LEITURA: este módulo apenas formata dados já calculados.
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── Fontes (TTF embutidas — preservam UTF-8) ────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "static", "fonts")
_FONT = "Arial"
_FONT_B = "Arial-Bold"

_fonts_registered = False


def _register_fonts() -> None:
    global _fonts_registered, _FONT, _FONT_B
    if _fonts_registered:
        return
    try:
        pdfmetrics.registerFont(TTFont(_FONT, os.path.join(_FONT_DIR, "arial.ttf")))
        pdfmetrics.registerFont(TTFont(_FONT_B, os.path.join(_FONT_DIR, "arialbd.ttf")))
    except Exception:
        # Fallback: fontes Type1 padrão (sem suporte a — e alguns acentos)
        _FONT, _FONT_B = "Helvetica", "Helvetica-Bold"
    _fonts_registered = True


# ── Formatação ───────────────────────────────────────────────────────────────

def brl(value) -> str:
    """1234.5 -> '1.234,50'"""
    try:
        v = round(float(value or 0), 2)
    except (TypeError, ValueError):
        return "0,00"
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl_full(value) -> str:
    return f"R$ {brl(value)}"


def dt_br(d) -> str:
    """date/datetime -> 'dd/mm/aaaa'"""
    if d is None:
        return "—"
    try:
        return d.strftime("%d/%m/%Y")
    except AttributeError:
        return str(d)


# ── Paleta / estilos ─────────────────────────────────────────────────────────
_C_SLATE = colors.HexColor("#334155")     # cabeçalho de tabela
_C_ZEBRA = colors.HexColor("#F1F5F9")     # linha alternada
_C_RULE = colors.HexColor("#CBD5E1")      # regras
_C_TEXT = colors.HexColor("#0F172A")
_C_MUTED = colors.HexColor("#64748B")
_C_RED = colors.HexColor("#DC2626")
_C_GREEN = colors.HexColor("#059669")


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("rt", fontName=_FONT_B, fontSize=14,
                                textColor=_C_TEXT, spaceAfter=2),
        "meta": ParagraphStyle("rm", fontName=_FONT, fontSize=8,
                               textColor=_C_MUTED, leading=11),
        "section": ParagraphStyle("rs", fontName=_FONT_B, fontSize=10,
                                  textColor=_C_SLATE, spaceBefore=10, spaceAfter=4),
        "cell": ParagraphStyle("rc", fontName=_FONT, fontSize=8.5,
                               textColor=_C_TEXT, leading=11),
        "cell_b": ParagraphStyle("rcb", fontName=_FONT_B, fontSize=8.5,
                                 textColor=_C_TEXT, leading=11),
        "cell_r": ParagraphStyle("rcr", fontName=_FONT, fontSize=8.5,
                                 textColor=_C_TEXT, leading=11, alignment=TA_RIGHT),
        "cell_br": ParagraphStyle("rcbr", fontName=_FONT_B, fontSize=8.5,
                                  textColor=_C_TEXT, leading=11, alignment=TA_RIGHT),
        "head": ParagraphStyle("rh", fontName=_FONT_B, fontSize=8,
                               textColor=colors.white, leading=10),
        "head_r": ParagraphStyle("rhr", fontName=_FONT_B, fontSize=8,
                                 textColor=colors.white, leading=10, alignment=TA_RIGHT),
        "note": ParagraphStyle("rn", fontName=_FONT, fontSize=7.5,
                               textColor=_C_MUTED, leading=10),
    }


# ── Paginação com total de páginas ───────────────────────────────────────────

class _NumberedCanvas(_canvas.Canvas):
    """Recipe padrão do ReportLab: permite 'Página N de M' no rodapé."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        page = self._pageNumber
        w, h = A4
        self.setStrokeColor(_C_RULE)
        self.setLineWidth(0.5)
        self.line(16 * mm, 15 * mm, w - 16 * mm, 15 * mm)
        self.setFont(_FONT, 7.5)
        self.setFillColor(_C_MUTED)
        self.drawString(16 * mm, 11 * mm, self._footer_left)
        self.drawRightString(w - 16 * mm, 11 * mm, f"Página {page} de {total}")
        self.setFont(_FONT, 6.5)
        self.drawString(16 * mm, 7.5 * mm, self._footer_sub)


def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    w, h = A4
    canvas_obj.setFont(_FONT, 7.5)
    canvas_obj.setFillColor(_C_MUTED)
    canvas_obj.drawRightString(w - 16 * mm, h - 10 * mm, doc._report_short_title)
    canvas_obj.restoreState()


def build_report_pdf(*, title: str, short_title: str, meta_lines: list[str],
                     sections: list[dict], notes: list[str] | None = None,
                     company_name: str = "", logo_path: str | None = None,
                     generated_by: str = "", now: datetime | None = None) -> bytes:
    """Monta o PDF do relatório.

    sections: lista de dicts:
        {"heading": str|None, "headers": [str], "rows": [[cell]],
         "money_cols": [idx], "totals": bool, "widths": [float|None]}
        cells: str | float | None (floats em money_cols são formatados via brl).
    """
    _register_fonts()
    now = now or datetime.now()
    st = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=title, author=generated_by or company_name or "ExecFlow",
        pageCompression=0,
    )
    doc._report_short_title = short_title or title

    story: list = []

    # ── Cabeçalho (primeira página): logo + título + meta ──
    header_cells = []
    logo_flow = None
    if logo_path and os.path.exists(logo_path):
        from reportlab.platypus import Image
        try:
            from PIL import Image as PILImage  # type: ignore
            with PILImage.open(logo_path) as im:
                w_px, h_px = im.size
            max_w, max_h = 34 * mm, 12 * mm
            scale = min(max_w / (w_px * 0.2646), max_h / (h_px * 0.2646), 1.0)
            logo_flow = Image(logo_path,
                              width=w_px * 0.2646 * scale,
                              height=h_px * 0.2646 * scale)
        except Exception:
            logo_flow = None
    meta_paras = [Paragraph(l, st["meta"]) for l in meta_lines]
    if logo_flow:
        header_cells = [[logo_flow, [Paragraph(title, st["title"]), *meta_paras]]]
    else:
        header_cells = [[[Paragraph(title, st["title"]), *meta_paras]]]
    header_t = Table(header_cells, colWidths=[None, doc.width - (34 * mm if logo_flow else 0)] if logo_flow else [doc.width])
    header_t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_t)
    story.append(Spacer(1, 4))
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(width="100%", thickness=0.8, color=_C_SLATE,
                            spaceAfter=6))

    # ── Seções ──
    for sec in sections:
        if sec.get("heading"):
            story.append(Paragraph(sec["heading"], st["section"]))

        headers = sec["headers"]
        money_cols = set(sec.get("money_cols") or [])
        widths = list(sec.get("widths") or [])
        ncols = len(headers)
        if len(widths) != ncols:
            avail = doc.width
            fixed = [w for w in widths if w]
            flex = ncols - len(fixed)
            each = (avail - sum(fixed)) / max(flex, 1)
            widths = [w if w else each for w in (widths + [None] * (ncols - len(widths)))]

        head_row = [Paragraph(h, st["head_r"] if idx in money_cols else st["head"])
                    for idx, h in enumerate(headers)]
        body_rows = []
        for r in sec["rows"]:
            cells = []
            for idx, val in enumerate(r):
                if idx in money_cols:
                    try:
                        v = round(float(val or 0), 2)
                    except (TypeError, ValueError):
                        v = 0.0
                    style = st["cell_br"]
                    if v < 0:
                        cells.append(Paragraph(
                            f'<font color="#DC2626">({brl(abs(v))})</font>', style))
                    else:
                        cells.append(Paragraph(brl(v), style))
                else:
                    cells.append(Paragraph(str(val if val is not None else "—"),
                                           st["cell"]))
            body_rows.append(cells)

        table_rows = [head_row] + body_rows
        tbl = Table(table_rows, colWidths=widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _C_SLATE),
            ("GRID", (0, 0), (-1, -1), 0.4, _C_RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(1, len(table_rows)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), _C_ZEBRA))
        if sec.get("totals") and body_rows:
            last = len(table_rows) - 1
            style_cmds += [
                ("BACKGROUND", (0, last), (-1, last), _C_ZEBRA),
                ("LINEABOVE", (0, last), (-1, last), 1, _C_SLATE),
                ("TOPPADDING", (0, last), (-1, last), 4),
                ("BOTTOMPADDING", (0, last), (-1, last), 4),
            ]
        tbl.setStyle(TableStyle(style_cmds))
        story.append(tbl)
        story.append(Spacer(1, 2))

    for n in (notes or []):
        story.append(Paragraph(n, st["note"]))
        story.append(Spacer(1, 2))

    # Rodapé
    generated_at = now.strftime("%d/%m/%Y %H:%M")
    footer_left = (company_name or "ExecFlow") + f" — {short_title or title}"
    footer_sub = f"Gerado em {generated_at}" + (f" por {generated_by}" if generated_by else "")
    canvasmaker = _NumberedCanvas
    canvasmaker._footer_left = footer_left
    canvasmaker._footer_sub = footer_sub

    doc.build(story, canvasmaker=canvasmaker, onFirstPage=_header_footer,
              onLaterPages=_header_footer)
    return buf.getvalue()
