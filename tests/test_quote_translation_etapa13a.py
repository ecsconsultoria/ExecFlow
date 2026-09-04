"""Testes da Etapa 13A — tradução automática no PDF de RFQ.

Cobre:
  1. Padrão genérico "Diária NNh [+ NNkm Franquia]" → "Disposal NN Hours + NN Km Included"
     para QUALQUER carga horária (05h, 10h, 14h, 24h, por extenso) — corrige a RFQ 73
     ("Diária 14h" saía como "Disposal 14h" sem o sufixo de km).
  2. Regra reversa no PDF PT (serviços cadastrados em inglês → português).
  3. Tradução automática das observações no PDF EN (translate_obs) e fallback em falha.
"""
from __future__ import annotations

import sys
import types

import pytest

from app.services.quote_pdf import _translate_service


# ── 1. Padrão genérico de horas (EN) ──────────────────────────────────────
class TestDiariaGenericaEN:
    @pytest.mark.parametrize("raw,expected", [
        ("Diária 14h + 100km Franquia", "Disposal 14 Hours + 100 Km Included"),
        ("Diária 10h + 100km Franquia", "Disposal 10 Hours + 100 Km Included"),
        ("Diária 05h + 50km Franquia",  "Disposal 5 Hours + 50 Km Included"),
        ("Diária 5h + 50km Franquia",   "Disposal 5 Hours + 50 Km Included"),
        ("Diária 24h + 100km Franquia", "Disposal 24 Hours + 100 Km Included"),
        # Sem franquia informada: padrão 50km para até 5h, 100km acima
        ("Diária 12h",                  "Disposal 12 Hours + 100 Km Included"),
        ("Diária 5h",                   "Disposal 5 Hours + 50 Km Included"),
        # Variante com "horas" por extenso
        ("Diária 14 horas + 100km Franquia", "Disposal 14 Hours + 100 Km Included"),
        ("Diária 14 Horas",             "Disposal 14 Hours + 100 Km Included"),
    ])
    def test_diaria_generica(self, raw, expected):
        assert _translate_service(raw, "en") == expected

    def test_freelance_nao_converte_horas(self):
        # Comportamento antigo preservado: veículo free lance não recebe "Hours"
        assert (_translate_service("Diária 14h + 100km Franquia", "en",
                                   "Sedan Free Lance") == "Disposal 14h")


# ── 2. Regra reversa (PT) — nomes cadastrados em inglês ────────────────────
class TestReversaPT:
    @pytest.mark.parametrize("raw,expected", [
        ("Disposal 14 Hours + 100 Km Included", "Diária 14h + 100km Franquia"),
        ("Disposal 5 Hours + 50 Km Included",   "Diária 5h + 50km Franquia"),
        ("Disposal 12 Hours",                   "Diária 12h + 100km Franquia"),
    ])
    def test_disposal_para_diaria(self, raw, expected):
        assert _translate_service(raw, "pt") == expected

    def test_airport_transfer_pt_regressao(self):
        assert _translate_service("Airport Transfer CGH", "pt") == "Transfer Aeroporto CGH"


# ── 3. Tradução automática das observações ─────────────────────────────────
class TestTranslateObs:
    def test_pt_devolve_original(self):
        from app.utils.translate import translate_obs
        texto = "Obs: dia 09/09 - Incluso Viagem ida e volta cidade Cajati."
        assert translate_obs(texto, "pt") == texto

    def test_vazio_devolve_vazio(self):
        from app.utils.translate import translate_obs
        assert translate_obs("", "en") == ""
        assert translate_obs(None, "en") is None

    def test_falha_devolve_original(self, monkeypatch):
        # Simula rede fora: GoogleTranslator explode → fallback silencioso
        fake = types.ModuleType("deep_translator")

        class _Boom:
            def __init__(self, *a, **k):
                raise RuntimeError("sem rede")

        fake.GoogleTranslator = _Boom
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
        from app.utils.translate import translate_obs
        texto = "Obs: dia 09/09 - Incluso Viagem ida e volta"
        assert translate_obs(texto, "en") == texto

    def test_sucesso_traduz(self, monkeypatch):
        fake = types.ModuleType("deep_translator")

        class _Fake:
            def __init__(self, *a, **k):
                pass

            def translate(self, text):
                return f"EN[{text}]"

        fake.GoogleTranslator = _Fake
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
        from app.utils.translate import translate_obs
        assert translate_obs("algum texto", "en") == "EN[algum texto]"


# ── 4. Integração: observações dentro do PDF da RFQ ────────────────────────
def _stub_quote(obs=""):
    """Stub mínimo do que generate_quote_pdf usa (sem DB)."""
    return types.SimpleNamespace(
        number="TEST-73",
        company=None,
        client=None,
        client_name="Cliente Teste",
        contact_name="Contato",
        email="contato@teste.com",
        phone="(11) 99999-9999",
        status="pendente",
        items=[],
        inclusions=[],
        obs=obs,
        billing_type="recibo",
        payment_method="pix",
        payment_terms="a vista",
        usd_rate=None,
    )


def _pdf_text(buf) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(buf)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


OBS_PT = "Obs: dia 09/09 - Incluso Viagem ida e volta cidade Cajati."
MARCA = "TRANSLATED OBS HERE"


def _norm(s: str) -> str:
    """Remove espaços/quebras para comparação robusta (a extração quebra linhas)."""
    import re
    return re.sub(r"\s+", "", s)


class TestObsNoPdf:
    def test_en_traduz_observacoes(self, monkeypatch):
        from app.services.quote_pdf import generate_quote_pdf
        monkeypatch.setattr(
            "app.utils.translate.translate_obs",
            lambda texto, lang: MARCA if lang == "en" else texto,
        )
        buf = generate_quote_pdf(_stub_quote(obs=OBS_PT), lang="en")
        texto = _norm(_pdf_text(buf))
        assert _norm(MARCA) in texto
        assert _norm(OBS_PT) not in texto

    def test_pt_mantem_observacoes(self, monkeypatch):
        from app.services.quote_pdf import generate_quote_pdf
        chamadas = []
        monkeypatch.setattr(
            "app.utils.translate.translate_obs",
            lambda texto, lang: chamadas.append((texto, lang)) or texto,
        )
        buf = generate_quote_pdf(_stub_quote(obs=OBS_PT), lang="pt")
        texto = _norm(_pdf_text(buf))
        assert _norm(OBS_PT) in texto
        assert chamadas == []
