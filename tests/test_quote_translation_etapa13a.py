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

from app.services.quote_pdf import _sanitize_phone, _translate_service


class TestSanitizePhone:
    @pytest.mark.parametrize("raw,expected", [
        # Hífen não separável (U+2011) — caso real do SO 65/RFQ 76
        ("+55 21 98210‑1221", "+55 21 98210-1221"),
        # Marcas de direção de texto (U+202A/U+202C) e espaços não separáveis
        ("‪+55 21 98210‑1221‬", "+55 21 98210-1221"),
        # Hífen comum e dígitos normais ficam como estão
        ("(11) 99999-9999", "(11) 99999-9999"),
        # Diversos hífens Unicode usados em telefones
        ("11‐98210−1221", "11-98210-1221"),
        ("11‒98210–1221", "11-98210-1221"),
        ("11－98210﹘1221", "11-98210-1221"),
        # Placeholder en-dash NÃO é convertido
        ("–", "–"),
        ("", ""),
        (None, None),
    ])
    def test_sanitize(self, raw, expected):
        assert _sanitize_phone(raw) == expected


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
        # Franquia ANTES do número (caso RFQ 76: "Diária 10h + Franquia 600km")
        ("Diária 10h + Franquia 600km", "Disposal 10 Hours + 600 Km Included"),
        ("Diária 10h + Franquia 600 km", "Disposal 10 Hours + 600 Km Included"),
        ("Diária 14 horas + Franquia 600km", "Disposal 14 Hours + 600 Km Included"),
    ])
    def test_diaria_generica(self, raw, expected):
        assert _translate_service(raw, "en") == expected

    def test_freelance_nao_converte_horas(self):
        # Comportamento antigo preservado: veículo free lance não recebe "Hours"
        assert (_translate_service("Diária 14h + 100km Franquia", "en",
                                   "Sedan Free Lance") == "Disposal 14h")
        # Franquia na ordem inversa também é removida no free lance
        assert (_translate_service("Diária 10h + Franquia 600km", "en",
                                   "Sedan Free Lance") == "Disposal 10h")


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


# ── 2b. Transfer sem "Airport" NÃO pode ganhar "Airport" (SO 60) ────────────
class TestTransferSemAirport:
    @pytest.mark.parametrize("raw", [
        "Transfer São Paulo x Lençóis Paulista",
        "Transfer Lençóis Paulista x Araraquara",
        "Transfer Araraquara x Holambra",
        "Transfer Holambra x São Paulo",
    ])
    def test_transfer_intermunicipal_fica_como_esta(self, raw):
        # Caso SO 60: transfers não-aeroporto não podem virar "Airport Transfer"
        assert _translate_service(raw, "en") == raw

    @pytest.mark.parametrize("raw,expected", [
        # Nomes de aeroporto em inglês: só reordena
        ("Transfer Airport CGH", "Airport Transfer CGH"),
        ("Transfer Airport GRU", "Airport Transfer GRU"),
        # Nomes cadastrados em português: traduz "Aeroporto" → "Airport"
        ("Transfer Aeroporto Guarulhos", "Airport Transfer Guarulhos"),
        ("Transfer Aeroporto", "Airport Transfer"),
    ])
    def test_transfer_aeroporto_mantem_airport(self, raw, expected):
        assert _translate_service(raw, "en") == expected


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

    def test_pagina_de_erro_do_google_e_descartada(self, monkeypatch):
        # Caso SO 65: Google respondeu com página de erro (status 200) e o
        # deep-translator entregou o texto do erro como "tradução".
        fake = types.ModuleType("deep_translator")

        class _ErroGoogle:
            def __init__(self, *a, **k):
                pass

            def translate(self, text):
                return ("Error 500 (Server Error)!!1500. That's an error. "
                        "There was an error. Please try again later. "
                        "That's all we know.")

        fake.GoogleTranslator = _ErroGoogle
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
        from app.utils.translate import translate_obs
        texto = "TESTE PEIDO"
        assert translate_obs(texto, "en") == texto

    def test_cache_reusa_traducao_sem_rechamar(self, monkeypatch):
        # Gerações consecutivas do mesmo PDF não chamam o Google de novo.
        import app.utils.translate as T
        T._CACHE.clear()
        chamadas = []
        fake = types.ModuleType("deep_translator")

        class _Conta:
            def __init__(self, *a, **k):
                pass

            def translate(self, text):
                chamadas.append(text)
                return f"EN[{text}]"

        fake.GoogleTranslator = _Conta
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
        from app.utils.translate import translate_obs
        assert translate_obs("TESTE PEIDO", "en") == "EN[TESTE PEIDO]"
        assert translate_obs("TESTE PEIDO", "en") == "EN[TESTE PEIDO]"
        assert len(chamadas) == 1
        # Outro idioma não reusa o cache
        assert translate_obs("TESTE PEIDO", "es") == "EN[TESTE PEIDO]"
        assert len(chamadas) == 2

    def test_falha_nao_poluia_o_cache(self, monkeypatch):
        # Tradução falha → texto original e NÃO entra no cache (próxima
        # tentativa pode chamar o serviço de novo).
        import app.utils.translate as T
        T._CACHE.clear()
        fake = types.ModuleType("deep_translator")

        class _FalhaUmaVez:
            # contador de classe: translate_obs cria uma instância nova por chamada
            n = 0

            def __init__(self, *a, **k):
                pass

            def translate(self, text):
                type(self).n += 1
                if type(self).n == 1:
                    raise RuntimeError("sem rede")
                return f"EN[{text}]"

        fake.GoogleTranslator = _FalhaUmaVez
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
        from app.utils.translate import translate_obs
        assert translate_obs("TESTE PEIDO 2", "en") == "TESTE PEIDO 2"
        assert translate_obs("TESTE PEIDO 2", "en") == "EN[TESTE PEIDO 2]"


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
    def test_telefone_com_hifen_unicode_sai_corrigido(self):
        # Caso real: telefone com U+2011 quebrava o glifo no PDF.
        from app.services.quote_pdf import generate_quote_pdf
        stub = _stub_quote()
        stub.phone = "‪+55 21 98210‑1221‬"
        buf = generate_quote_pdf(stub, lang="pt")
        texto = _norm(_pdf_text(buf))
        assert "98210-1221" in texto

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
