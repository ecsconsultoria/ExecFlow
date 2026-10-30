"""po_agenda.py — Contexto da agenda pública da PO (mesmo HTML do SO).

Usa o MESMO template da agenda do SO (public_so/agenda.html) com os dados
operacionais da PO: op_* por item com fallback nos campos globais da PO.
Sem preços. Rótulo do cabeçalho: PEDIDO DE COMPRA / PURCHASE ORDER.
"""
from __future__ import annotations

from datetime import datetime as _dt

from flask import current_app, url_for

from ..models.purchase_order import PurchaseOrder
from ..utils import make_client_token
from .so_agenda import _dt_pt_en, _phone_html


def po_token(po_id: int) -> str:
    """Token de acesso público da agenda da PO (HMAC do id)."""
    return make_client_token(po_id, current_app.config["SECRET_KEY"])


def _item_block(po: PurchaseOrder, it) -> dict:
    """Bloco de agenda do item: op_* do item com fallback nos campos globais da PO."""
    from .quote_pdf import _translate_vehicle, _translate_service, _translate_driver as _pdf_driver

    dt = it.op_pickup_datetime or po.pickup_datetime
    if dt is None and it.service_date:
        t = it.service_time
        dt = _dt(it.service_date.year, it.service_date.month, it.service_date.day,
                 t.hour if t else 0, t.minute if t else 0)
    dt_pt, dt_en = _dt_pt_en(dt)
    desc = it.description or (it.service.name if it.service else "")
    cat_name = it.category.name if it.category else (
        po.vehicle_category.name if po.vehicle_category else "")
    model = it.op_vehicle_model or po.vehicle_model or ""
    plate = it.op_vehicle_plate or po.vehicle_plate or ""
    driver = it.op_driver_name or po.driver_name or ""
    driver_phone = it.op_driver_phone or po.driver_phone or ""
    pax_name = it.op_passenger_name or po.passenger_name or ""
    pax_phone = it.op_passenger_phone or po.passenger_phone or ""
    return {
        "dt_pt": dt_pt,
        "dt_en": dt_en,
        "service_pt": _translate_service(desc, "pt"),
        "service_en": _translate_service(desc, "en"),
        "model": model,
        "plate": plate,
        "driver": driver,
        "driver_en": _pdf_driver(driver, "en") if driver else "",
        "driver_phone": driver_phone,
        "driver_phone_html": _phone_html(driver_phone) if driver_phone else "",
        "pickup": it.op_pickup_location or po.pickup_location or "",
        "dropoff": it.op_dropoff_location or po.dropoff_location or "",
        "pax_name": pax_name,
        "pax_phone": pax_phone,
        "pax_phone_html": _phone_html(pax_phone) if pax_phone else "",
        "flight": it.op_flight_number or po.flight_number or "",
        "notes": it.op_notes or "",
    }


def build_agenda_context(po: PurchaseOrder) -> dict:
    """Contexto no MESMO formato da agenda do SO (template compartilhado)."""
    items = [it for it in sorted(po.items, key=lambda x: x.sort_order or 0)]
    # Observações SOMENTE dos dados operacionais (op_notes por item)
    op_notes_all = []
    for it in items:
        n = (it.op_notes or "").strip()
        if n and n not in op_notes_all:
            op_notes_all.append(n)
    ctx = {
        "order": po,
        "number": po.number,
        "so_url": url_for("purchase_orders.detail", po_id=po.id, _external=True),
        "ref_pt": "PEDIDO DE COMPRA",
        "ref_en": "PURCHASE ORDER",
        # PO: placa exibida AO LADO do veículo (SO: linha separada)
        "plate_inline": True,
        "items": [_item_block(po, it) for it in items],
        "inclusions": [],
        "obs": "\n".join(op_notes_all),
        "lang": "pt",
    }
    from .so_agenda import _i18n_dict
    d = _i18n_dict(ctx)
    d["pt"]["ref"], d["en"]["ref"] = "PEDIDO DE COMPRA", "PURCHASE ORDER"
    ctx["i18n"] = d
    return ctx
