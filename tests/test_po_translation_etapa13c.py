"""Testes da Etapa 13C — tradução dos VALORES no PDF de PO.

O PDF de PO traduzia rótulos, mas imprimia valores brutos em português no EN:
  'TRANSFERÊNCIA' (deveria ser 'Wire Transfer'), '15 dias' (deveria ser '15 Days').
A correção usa o mesmo padrão já existente nos PDFs de RFQ e SO.
"""
from __future__ import annotations

import pytest

from app.services.purchase_order_pdf import _pay_method_label, _pay_terms_label


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
