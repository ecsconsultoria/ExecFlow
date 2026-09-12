"""Testes da Etapa 13C — tradução dos VALORES no PDF de PO.

O PDF de PO traduzia rótulos, mas imprimia valores brutos em português no EN:
  'TRANSFERÊNCIA' (deveria ser 'Wire Transfer'), '15 dias' (deveria ser '15 Days').
A correção usa o mesmo padrão já existente nos PDFs de RFQ e SO.
Também cobre a normalização do idioma na rota do PDF (links com '?ts=' grudado).
"""
from __future__ import annotations

import pytest

from app.blueprints.purchase_orders.routes import _normalize_lang
from app.models.purchase_order import PurchaseOrder
from app.services.purchase_order_pdf import _pay_method_label, _pay_terms_label
from app.services.purchase_order_service import _apply_data
from app.services.quote_pdf import _total_cell_text


class TestApplyDataUsdRate:
    """PO 75: usd_rate='' no save quebrava o Postgres (double precision)."""

    def test_vazio_vira_none(self):
        po = PurchaseOrder()
        _apply_data(po, {"usd_rate": "", "amount": "1.100,00"})
        assert po.usd_rate is None
        assert po.amount == 1100.0

    def test_virgula_parseia(self):
        po = PurchaseOrder()
        _apply_data(po, {"usd_rate": "5,40"})
        assert po.usd_rate == 5.4

    def test_zero_vira_none(self):
        po = PurchaseOrder()
        _apply_data(po, {"usd_rate": "0"})
        assert po.usd_rate is None

    def test_float_nativo_mantem(self):
        po = PurchaseOrder()
        _apply_data(po, {"usd_rate": 5.4})
        assert po.usd_rate == 5.4

    def test_invalido_vira_none(self):
        po = PurchaseOrder()
        _apply_data(po, {"usd_rate": "abc"})
        assert po.usd_rate is None


class TestTotalCellTextUSD:
    def test_com_cotacao_mostra_usd(self):
        out = _total_cell_text(9200.0, "en", 5.4)
        assert "USD" in out

    def test_sem_cotacao_nao_mostra_usd(self):
        assert "USD" not in _total_cell_text(9200.0, "en", None)
        assert "USD" not in _total_cell_text(9200.0, "pt", 0)

    def test_formato_brl_preservado(self):
        out = _total_cell_text(9200.0, "pt", None)
        assert "9.200,00" in out


class TestNormalizeLang:
    @pytest.mark.parametrize("raw,expected", [
        ("pt", "pt"),
        ("en", "en"),
        # Links antigos com cache-buster grudado (bug do '?ts=' no template)
        ("pt?ts=1756800000", "pt"),
        ("en?ts=1756800000", "en"),
        ("en?_cb=123.0", "en"),
        # Valores inválidos caem no padrão pt
        ("", "pt"),
        (None, "pt"),
        ("fr", "pt"),
        ("PT", "pt"),
    ])
    def test_normalize(self, raw, expected):
        assert _normalize_lang(raw) == expected


class TestPayMethodLabel:
    @pytest.mark.parametrize("raw,lang,expected", [
        # pt → mantém o valor original (título do dicionário)
        ("transferência", "pt", "Transferência"),
        ("Transferência", "pt", "Transferência"),
        # en → traduzido
        ("transferência", "en", "Wire Transfer"),
        ("TRANSFERÊNCIA", "en", "Wire Transfer"),
        ("dinheiro",     "en", "Cash"),
        ("DINHEIRO",     "en", "Cash"),
        ("boleto",       "en", "Bank Slip"),
        ("cartão de crédito", "en", "Credit Card"),
        ("pix",          "en", "PIX"),
        # valor fora do dicionário → texto original
        ("cheque",       "en", "cheque"),
    ])
    def test_pay_method(self, raw, lang, expected):
        assert _pay_method_label(raw, lang) == expected

    def test_vazio_vira_traco(self):
        assert _pay_method_label("", "en") == "–"
        assert _pay_method_label(None, "pt") == "–"


class TestPayTermsLabel:
    @pytest.mark.parametrize("raw,lang,expected", [
        ("15 dias", "en", "15 Days"),
        ("10 dias", "en", "10 Days"),
        ("à vista", "en", "Full Payment"),
        ("à vista + 1 parcela", "en", "Split into 2 payments"),
        # pt → mantém o original
        ("15 dias", "pt", "15 dias"),
        # fora do dicionário → texto original
        ("30/60 dias", "en", "30/60 dias"),
    ])
    def test_pay_terms(self, raw, lang, expected):
        assert _pay_terms_label(raw, lang) == expected

    def test_vazio_vira_traco(self):
        assert _pay_terms_label("", "en") == "–"
