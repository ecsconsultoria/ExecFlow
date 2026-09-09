"""Testes da Etapa 13I — data/hora do serviço preservadas ao editar a RFQ.

Bug: o edit_data do formulário de edição não incluía service_date/service_time
dos itens; qualquer edição (mesmo só nas observações) apagava a data/hora
gravada na primeira versão da RFQ.
"""
from __future__ import annotations

import types
from datetime import date, time

import pytest

from app.blueprints.quotes.routes import _edit_item_payload
from app.services.quote_service import _parse_date, _parse_time


def _item(sd=None, st=None):
    return types.SimpleNamespace(
        service_id=1, category_id=2, ref_note=None, description="Diária 10h",
        vehicle_description="", driver_name="", state_code="",
        quantity=1, unit_price=400.0, hour_extra=None, total_price=400.0,
        price_base=0, price_nf=0, price_cartao=0, price_nf_cartao=0,
        km_extra=None, km_extra_rate=None, sort_order=0,
        service_date=sd, service_time=st,
    )


class TestEditItemPayload:
    def test_data_e_hora_serializadas(self):
        payload = _edit_item_payload(_item(sd=date(2026, 9, 11), st=time(14, 56)))
        assert payload["service_date"] == "2026-09-11"
        assert payload["service_time"] == "14:56"

    def test_data_meia_noite_serializa_00_00(self):
        payload = _edit_item_payload(_item(sd=date(2026, 9, 11), st=time(0, 0)))
        assert payload["service_time"] == "00:00"

    def test_sem_data_e_hora_vira_string_vazia(self):
        payload = _edit_item_payload(_item(sd=None, st=None))
        assert payload["service_date"] == ""
        assert payload["service_time"] == ""

    def test_valores_serializados_sao_aceitos_pelo_parser_do_save(self):
        # Round-trip: o que o formulário envia volta a virar date/time no banco
        payload = _edit_item_payload(_item(sd=date(2026, 9, 11), st=time(14, 56)))
        assert _parse_date(payload["service_date"]) == date(2026, 9, 11)
        assert _parse_time(payload["service_time"]) == time(14, 56)

    def test_chave_do_servico_nao_afeta_data(self):
        payload = _edit_item_payload(_item(sd=date(2026, 1, 2), st=time(23, 59)))
        assert (payload["service_date"], payload["service_time"]) == ("2026-01-02", "23:59")
