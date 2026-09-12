"""Testes da Etapa 13N — títulos das páginas de dados operacionais e da placa.

Regra definida pelo usuário:
  - A página de dados operacionais (SO e PO) passa a ter título próprio, grande
    (24pt) e centralizado: "DETALHES DA AGENDA" (pt) / "SCHEDULE DETAILS" (en).
    Vale SEMPRE, inclusive em PO com placa receptivo.
  - A página da placa de receptivo (landscape, só existe em PO) tem o título
    "Meet & Greet" — pequeno (11pt) e centralizado no cabeçalho, mesmo texto
    nos dois idiomas.
  - O SO não tem placa receptivo (o campo só existe em POItem), então lá não há
    página de placa.

Os testes de integração geram PDFs reais a partir do banco de dev (somente
leitura) e são ignorados (skip) se não houver registro adequado.
"""
from __future__ import annotations

import re

import pytest

from app.services.order_pdf import _t as _t_order
from app.services.purchase_order_pdf import _PLACA_TITULO, _t as _t_po

TITULO_PT = "DETALHES DA AGENDA"
TITULO_EN = "SCHEDULE DETAILS"
MEET = "Meet & Greet"


def _norm(s: str) -> str:
    """Normaliza espaços — a extração do PDF quebra linhas no meio das frases."""
    return re.sub(r"\s+", " ", s or "")


def _paginas(buf) -> list[tuple[str, bool]]:
    """[(texto_normalizado, eh_landscape), ...] na ordem das páginas."""
    from PyPDF2 import PdfReader
    buf.seek(0)
    out = []
    for page in PdfReader(buf).pages:
        largura, altura = float(page.mediabox.width), float(page.mediabox.height)
        out.append((_norm(page.extract_text()), largura > altura))
    return out


def _tem_dados_op(it) -> bool:
    return any([
        getattr(it, "op_pickup_datetime", None),
        (getattr(it, "op_pickup_location", "") or "").strip(),
        (getattr(it, "op_dropoff_location", "") or "").strip(),
        (getattr(it, "op_passenger_name", "") or "").strip(),
        (getattr(it, "op_flight_number", "") or "").strip(),
        (getattr(it, "op_notes", "") or "").strip(),
    ])


def _so_com_dados_op():
    """Primeiro SO (não faturado) com pelo menos um item com dados operacionais."""
    from app.models.order import Order
    for o in Order.query.order_by(Order.id.desc()).limit(300):
        if o.status != "faturado" and any(_tem_dados_op(it) for it in (o.items or [])):
            return o
    return None


def _po_com_dados_op(receptivo: bool | None = None):
    """Primeiro PO (não faturado) com dados operacionais, filtrando por receptivo."""
    from app.models.purchase_order import PurchaseOrder
    for p in PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).limit(300):
        if p.status == "faturado" or not any(_tem_dados_op(it) for it in (p.items or [])):
            continue
        rec = any(getattr(it, "placa_receptivo", False) for it in (p.items or []))
        if receptivo is not None and rec != receptivo:
            continue
        return p
    return None


class TestLabels:
    def test_titulo_grande_em_ambos_os_pdfs(self):
        assert _t_order("op_page_title", "pt") == TITULO_PT
        assert _t_order("op_page_title", "en") == TITULO_EN
        assert _t_po("op_page_title", "pt") == TITULO_PT
        assert _t_po("op_page_title", "en") == TITULO_EN

    def test_titulo_da_placa_tem_ampersand_escapado(self):
        # Paragraph do ReportLab interpreta markup — o '&' precisa vir escapado.
        assert _PLACA_TITULO == "Meet &amp; Greet"

    def test_so_nao_tem_titulo_de_placa(self):
        # O SO não tem placa receptivo — a chave não deve existir lá.
        assert _t_order("op_page_title", "pt") == TITULO_PT
        assert _t_order("op_meet_greet", "pt") == "op_meet_greet"


class TestTarjaDoBloco:
    """A tarja escura de cada bloco mostra apenas o item — o rótulo
    "DADOS OPERACIONAIS" / "OPERATIONAL DATA" foi removido dos PDFs."""

    def test_rotulo_removido_dos_dicionarios(self):
        assert _t_order("op_hdr", "pt") == "op_hdr"
        assert _t_po("op_hdr", "pt") == "op_hdr"

    @pytest.mark.parametrize("lang", ["pt", "en"])
    def test_so_mostra_item_e_nao_o_rotulo(self, app, lang):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            o = _so_com_dados_op()
            if o is None:
                pytest.skip("nenhum SO com dados operacionais no banco de dev")
            texto = " ".join(t for t, _ in _paginas(generate_order_pdf(o, lang=lang)))
        assert "DADOS OPERACIONAIS" not in texto
        assert "OPERATIONAL DATA" not in texto
        assert "Item" in texto

    @pytest.mark.parametrize("lang", ["pt", "en"])
    def test_po_mostra_item_e_nao_o_rotulo(self, app, lang):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            p = _po_com_dados_op()
            if p is None:
                pytest.skip("sem PO com dados operacionais no banco de dev")
            texto = " ".join(t for t, _ in _paginas(generate_po_pdf(p, lang=lang)))
        assert "DADOS OPERACIONAIS" not in texto
        assert "OPERATIONAL DATA" not in texto
        assert "Item" in texto


class TestSO:
    """PDF de SO: título grande, uma vez por página, em pt e en."""

    @pytest.fixture(autouse=True)
    def _requer_so(self, app):
        with app.app_context():
            if _so_com_dados_op() is None:
                pytest.skip("nenhum SO com dados operacionais no banco de dev")

    def test_pt_tem_detalhes_da_agenda(self, app):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            paginas = _paginas(generate_order_pdf(_so_com_dados_op(), lang="pt"))
        texto = " ".join(t for t, _ in paginas)
        assert TITULO_PT in texto
        assert TITULO_EN not in texto

    def test_en_tem_schedule_details(self, app):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            texto = " ".join(t for t, _ in _paginas(generate_order_pdf(_so_com_dados_op(), lang="en")))
        assert TITULO_EN in texto
        assert TITULO_PT not in texto

    def test_titulo_aparece_uma_vez_so(self, app):
        # O título é da página, não de cada bloco de item.
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            texto = " ".join(t for t, _ in _paginas(generate_order_pdf(_so_com_dados_op(), lang="pt")))
        assert texto.count(TITULO_PT) == 1

    def test_so_nao_gera_pagina_de_placa(self, app):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            paginas = _paginas(generate_order_pdf(_so_com_dados_op(), lang="pt"))
        assert not any(land for _, land in paginas), "SO não deve ter página landscape"
        assert MEET not in " ".join(t for t, _ in paginas)


class TestPOSemReceptivo:
    """PO sem placa receptivo: título grande, nenhuma página de placa."""

    @pytest.fixture(autouse=True)
    def _requer_po(self, app):
        with app.app_context():
            if _po_com_dados_op(receptivo=False) is None:
                pytest.skip("sem PO com dados operacionais e sem receptivo")

    def test_pt_e_en_tem_titulo_grande(self, app):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            p = _po_com_dados_op(receptivo=False)
            paginas_pt = _paginas(generate_po_pdf(p, lang="pt"))
            paginas_en = _paginas(generate_po_pdf(p, lang="en"))
        texto_pt = " ".join(t for t, _ in paginas_pt)
        texto_en = " ".join(t for t, _ in paginas_en)
        assert TITULO_PT in texto_pt
        assert TITULO_EN in texto_en
        assert MEET not in texto_pt
        assert MEET not in texto_en
        assert not any(land for _, land in paginas_pt)


class TestPOComReceptivo:
    """PO com placa receptivo: dados operacionais mantêm o título grande;
    o 'Meet & Greet' é o cabeçalho da(s) página(s) landscape da placa."""

    @pytest.fixture(autouse=True)
    def _requer_po(self, app):
        with app.app_context():
            if _po_com_dados_op(receptivo=True) is None:
                pytest.skip("sem PO com receptivo e dados operacionais")

    @pytest.mark.parametrize("lang,titulo", [("pt", TITULO_PT), ("en", TITULO_EN)])
    def test_dados_operacionais_mantem_titulo_grande(self, app, lang, titulo):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            paginas = _paginas(generate_po_pdf(_po_com_dados_op(receptivo=True), lang=lang))
        retrato = [t for t, land in paginas if not land]
        assert any(titulo in t for t in retrato), f"título grande ausente no {lang}"
        # o Meet & Greet NÃO deve aparecer nas páginas de retrato
        assert not any(MEET in t for t in retrato), "Meet & Greet vazou para a página de dados"

    @pytest.mark.parametrize("lang", ["pt", "en"])
    def test_paginas_da_placa_tem_meet_greet(self, app, lang):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            p = _po_com_dados_op(receptivo=True)
            n_placas = sum(
                1 for it in (p.items or [])
                if getattr(it, "placa_receptivo", False)
                and ((getattr(it, "placa_receptivo_texto", "") or "").strip()
                     or (getattr(it, "placa_imagem", "") or "").strip())
            )
            paginas = _paginas(generate_po_pdf(p, lang=lang))
        paisagem = [t for t, land in paginas if land]
        assert len(paisagem) == n_placas, "uma página landscape por placa"
        assert n_placas >= 1
        for t in paisagem:
            assert MEET in t, f"Meet & Greet ausente na página da placa ({lang})"


class TestSignPdfAvulso:
    """O PDF avulso da placa (generate_sign_pdf) também leva o cabeçalho."""

    def test_uma_pagina_landscape_com_meet_greet(self, app):
        from app.services.purchase_order_pdf import generate_sign_pdf
        with app.app_context():
            paginas = _paginas(generate_sign_pdf(text="ANDERSON"))
        assert len(paginas) == 1
        texto, land = paginas[0]
        assert land
        assert MEET in texto
        assert "ANDERSON" in texto

    def test_sem_texto_nem_imagem_ainda_tem_cabecalho(self, app):
        from app.services.purchase_order_pdf import generate_sign_pdf
        with app.app_context():
            paginas = _paginas(generate_sign_pdf())
        assert MEET in paginas[0][0]
