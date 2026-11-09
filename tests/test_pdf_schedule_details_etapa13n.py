"""Testes da Etapa 13N — página de dados operacionais e página da placa.

Regra (11/2026): a página 2 (DETALHES DA AGENDA / SCHEDULE DETAILS) foi
REMOVIDA dos PDFs de SO e PO — a agenda operacional é acompanhada no
Controle de Despacho. Os PDFs terminam após Observações/Inclusos/Política.
A página da placa de receptivo (landscape, só em PO) PERMANECE, com o
título "Meet & Greet" (11pt) nos dois idiomas.

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
    def test_titulo_da_placa_tem_ampersand_escapado(self):
        # Paragraph do ReportLab interpreta markup — o '&' precisa vir escapado.
        assert _PLACA_TITULO == "Meet &amp; Greet"

    def test_so_nao_tem_titulo_de_placa(self):
        # O SO não tem placa receptivo — a chave não deve existir lá.
        assert _t_order("op_meet_greet", "pt") == "op_meet_greet"


class TestPaginaOperacionalRemovida:
    """Regra 11/2026: a página 2 (DETALHES DA AGENDA) saiu dos PDFs de SO e PO."""

    @pytest.mark.parametrize("lang,titulo", [("pt", TITULO_PT), ("en", TITULO_EN)])
    def test_so_nao_tem_pagina_operacional(self, app, lang, titulo):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            o = _so_com_dados_op()
            if o is None:
                pytest.skip("nenhum SO com dados operacionais no banco de dev")
            paginas = _paginas(generate_order_pdf(o, lang=lang))
        texto = " ".join(t for t, _ in paginas)
        assert titulo not in texto, f"título da página 2 ainda presente no SO ({lang})"
        assert not any(land for _, land in paginas), "SO não deve ter página landscape"

    @pytest.mark.parametrize("lang,titulo", [("pt", TITULO_PT), ("en", TITULO_EN)])
    def test_po_sem_receptivo_nao_tem_pagina_operacional(self, app, lang, titulo):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            p = _po_com_dados_op(receptivo=False)
            if p is None:
                pytest.skip("sem PO com dados operacionais e sem receptivo")
            paginas = _paginas(generate_po_pdf(p, lang=lang))
        texto = " ".join(t for t, _ in paginas)
        assert titulo not in texto, f"título da página 2 ainda presente no PO ({lang})"
        assert MEET not in texto
        assert not any(land for _, land in paginas)

    @pytest.mark.parametrize("lang", ["pt", "en"])
    def test_so_mostra_sem_rotulos_operacionais(self, app, lang):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            o = _so_com_dados_op()
            if o is None:
                pytest.skip("nenhum SO com dados operacionais no banco de dev")
            texto = " ".join(t for t, _ in _paginas(generate_order_pdf(o, lang=lang)))
        assert "DADOS OPERACIONAIS" not in texto
        assert "OPERATIONAL DATA" not in texto


class TestSO:
    """PDF de SO: sem página 2 e sem página de placa."""

    @pytest.fixture(autouse=True)
    def _requer_so(self, app):
        with app.app_context():
            if _so_com_dados_op() is None:
                pytest.skip("nenhum SO com dados operacionais no banco de dev")

    def test_so_nao_gera_pagina_de_placa(self, app):
        from app.services.order_pdf import generate_order_pdf
        with app.app_context():
            paginas = _paginas(generate_order_pdf(_so_com_dados_op(), lang="pt"))
        assert not any(land for _, land in paginas), "SO não deve ter página landscape"
        # "Meet & Greet" pode aparecer como item de Serviços Inclusos (opção da
        # tela do SO), mas nunca como TÍTULO de página de placa.
        for text, _ in paginas:
            assert not text.lstrip().startswith(MEET), (
                "SO não deve ter página de placa com título 'Meet & Greet'")


class TestPOComReceptivo:
    """PO com placa receptivo: só a(s) página(s) landscape da placa."""

    @pytest.fixture(autouse=True)
    def _requer_po(self, app):
        with app.app_context():
            if _po_com_dados_op(receptivo=True) is None:
                pytest.skip("sem PO com receptivo e dados operacionais")

    @pytest.mark.parametrize("lang", ["pt", "en"])
    def test_retrato_sem_meet_greet(self, app, lang):
        from app.services.purchase_order_pdf import generate_po_pdf
        with app.app_context():
            paginas = _paginas(generate_po_pdf(_po_com_dados_op(receptivo=True), lang=lang))
        retrato = [t for t, land in paginas if not land]
        assert not any(MEET in t for t in retrato), "Meet & Greet vazou para o retrato"

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
