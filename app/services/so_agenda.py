"""so_agenda.py — Contexto da agenda pública do SO (link sem preços).

Modelo visual do link público do RFQ (identidade preto/dourado), mas SEM
valores de preço e COM os dados operacionais preenchidos no SO (op_* por
item). Link só existe a partir da tela do SO (token HMAC do id).
"""
from __future__ import annotations

import re
from datetime import datetime as _dt

from flask import current_app

from ..models.order import Order
from ..utils import make_client_token


def _clean_phone(v) -> str:
    """Apenas dígitos, sempre com 55 na frente e sem o sinal de +."""
    digits = re.sub(r"\D", "", v or "")
    if not digits:
        return ""
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


def _wa_link(phone) -> str:
    digits = _clean_phone(phone)
    return f"https://wa.me/{digits}" if digits else ""


_WA_ICON = ('<svg class="wa-ic" viewBox="0 0 24 24" fill="#25D366">'
            '<path d="M17.5 14.4c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17'
            '-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48-.89-.79-1.49-1.77-1.66-2.07-.17-.3-.02-.46.13-.61'
            '.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.62-.92-2.22-.24-.58'
            '-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.5 0 1.47 1.07 2.9 1.22 3.1.15.2'
            ' 2.11 3.22 5.1 4.51.71.31 1.27.49 1.7.63.72.23 1.37.2 1.88.12.57-.09 1.76-.72 2-1.42.25-.7.25-1.3'
            '.18-1.42-.07-.12-.27-.2-.57-.35z"/></svg>')


def _phone_html(phone: str) -> str:
    """Telefone + ícone do WhatsApp, ambos dentro do link wa.me."""
    wa = _wa_link(phone)
    if not wa:
        return phone
    return (f'<a href="{wa}" target="_blank" rel="noopener" '
            f'style="color:#fff;text-decoration:none">{phone}{_WA_ICON}</a>')


def so_token(order_id: int) -> str:
    """Token de acesso público da agenda do SO (HMAC do id com a SECRET_KEY)."""
    return make_client_token(order_id, current_app.config["SECRET_KEY"])


def _dt_pt_en(dt) -> tuple[str, str]:
    if not dt:
        return "", ""
    pt = f"{dt.day:02d}/{dt.month:02d}/{dt.year} às {dt.hour:02d}:{dt.minute:02d}h"
    en = f"{dt.month:02d}/{dt.day:02d}/{dt.year} at {dt.hour:02d}:{dt.minute:02d}"
    return pt, en


def _item_block(order: Order, it) -> dict:
    """Bloco de agenda do item: dados operacionais (op_*) com fallback nos campos do item."""
    from .quote_pdf import _translate_vehicle, _translate_service, _translate_driver as _pdf_driver

    dt = it.op_pickup_datetime
    if dt is None and it.service_date:
        t = it.service_time
        dt = _dt(it.service_date.year, it.service_date.month, it.service_date.day,
                 t.hour if t else 0, t.minute if t else 0)
    dt_pt, dt_en = _dt_pt_en(dt)
    cat_name = it.category.name if it.category else ""
    model = it.op_vehicle_model or (it.vehicle_description or "")
    driver = it.op_driver_name or (it.driver_name or "")
    driver_phone = it.op_driver_phone or ""
    # Serviço dos dados operacionais primeiro; fallback no serviço original do item
    desc = it.op_service or it.description or ""
    service_pt = _translate_service(desc, "pt")
    service_en = _translate_service(desc, "en")
    return {
        "dt_pt": dt_pt,
        "dt_en": dt_en,
        "service_pt": service_pt,
        "service_en": service_en,
        "vehicle_pt": _translate_vehicle(cat_name, "pt"),
        "vehicle_en": _translate_vehicle(cat_name, "en"),
        "model": model,
        "plate": it.op_vehicle_plate or "",
        "driver": driver,
        "driver_en": _pdf_driver(driver, "en") if driver else "",
        "driver_phone": driver_phone,
        "driver_phone_html": _phone_html(driver_phone) if driver_phone else "",
        "pickup": it.op_pickup_location or "",
        "dropoff": it.op_dropoff_location or "",
        "pax_name": it.op_passenger_name or "",
        "pax_phone": it.op_passenger_phone or "",
        "pax_phone_html": _phone_html(it.op_passenger_phone) if it.op_passenger_phone else "",
        "flight": it.op_flight_number or "",
        "notes": it.op_notes or "",
    }


def build_agenda_context(order: Order) -> dict:
    """Contexto completo para o template da agenda pública do SO (sem preços)."""
    client_name = (order.client.name if order.client else "") or order.client_name or ""
    client_phone = ""
    if order.client:
        client_phone = order.client.whatsapp or order.client.phone or ""
    if not client_phone:
        client_phone = order.celular or order.phone or ""
    if not client_phone and order.quote_id:
        # fallback: telefone do cliente vive no RFQ vinculado
        from ..models.quote import Quote
        quote = Quote.query.filter_by(id=order.quote_id, deleted_at=None).first()
        if quote:
            client_phone = (quote.phone or "")
            if not client_phone and quote.client:
                client_phone = quote.client.whatsapp or quote.client.phone or ""
    items = [it for it in sorted(order.items, key=lambda x: x.sort_order or 0)]
    # Observações SOMENTE dos dados operacionais (op_notes por item), nunca do SO original
    op_notes_all = []
    for it in items:
        n = (it.op_notes or "").strip()
        if n and n not in op_notes_all:
            op_notes_all.append(n)
    inclusions = []
    if order.quote_id:
        from ..models.quote import Quote
        quote = Quote.query.filter_by(id=order.quote_id, deleted_at=None).first()
        if quote:
            inclusions = [inc for inc in sorted(quote.inclusions, key=lambda x: x.sort_order or 0) if inc.included]
    ctx = {
        "order": order,
        "number": order.number,
        "so_url": _so_url(order),
        "client": client_name,
        "client_phone": client_phone,
        "client_phone_html": _phone_html(client_phone) if client_phone else "",
        "items": [_item_block(order, it) for it in items],
        "inclusions": inclusions,
        "obs": "\n".join(op_notes_all),
        "lang": "pt",
    }
    ctx["i18n"] = _i18n_dict(ctx)
    return ctx


def _so_url(order: Order) -> str:
    """Hiperlink do próprio pedido de venda (página dele no sistema)."""
    try:
        from flask import url_for
        return url_for("orders.detail", oid=order.id, _external=True)
    except Exception:
        return ""


def _i18n_dict(ctx: dict) -> dict:
    pt, en = {}, {}
    pt["title"], en["title"] = "DETALHES DA AGENDA", "SCHEDULE DETAILS"
    pt["ref"], en["ref"] = "PEDIDO DE VENDA", "SERVICE ORDER"
    pt["client_lbl"], en["client_lbl"] = "Cliente", "Client"
    pt["service_lbl"], en["service_lbl"] = "Serviço", "Service"
    pt["vehicle_lbl"], en["vehicle_lbl"] = "Veículo", "Vehicle"
    pt["note_lbl"], en["note_lbl"] = "Notas", "Notes"
    pt["dt_lbl"], en["dt_lbl"] = "Data/Hora", "Date/Time"
    pt["driver_lbl"], en["driver_lbl"] = "Motorista", "Driver"
    pt["pickup_lbl"], en["pickup_lbl"] = "Embarque", "Pickup"
    pt["dropoff_lbl"], en["dropoff_lbl"] = "Desembarque", "Drop-off"
    pt["pax_lbl"], en["pax_lbl"] = "Passageiro", "Passenger"
    pt["flight_lbl"], en["flight_lbl"] = "Voo", "Flight"
    pt["inc_title"], en["inc_title"] = "INCLUSO", "INCLUDED"
    pt["notes_lbl"], en["notes_lbl"] = "OBSERVAÇÕES", "NOTES"
    pt["item_lbl"], en["item_lbl"] = "ITEM", "ITEM"
    for i, it in enumerate(ctx["items"]):
        pt[f"it{i}_dt"], en[f"it{i}_dt"] = it["dt_pt"], it["dt_en"]
        pt[f"it{i}_svc"], en[f"it{i}_svc"] = it["service_pt"], it["service_en"]
        pt[f"it{i}_veh"], en[f"it{i}_veh"] = it["vehicle_pt"], it["vehicle_en"]

        def _drv(driver, phone):
            if not driver:
                return ""
            if phone:
                return f'{driver} · <span class="mini-lbl">Mobile</span> {_phone_html(phone)}'
            return driver

        pt[f"it{i}_drv"] = _drv(it["driver"], it["driver_phone"])
        en[f"it{i}_drv"] = _drv(it["driver_en"] or it["driver"], it["driver_phone"])
    pt["company_line"], en["company_line"] = (
        "Executive Car SP • CNPJ 11.183.125/0001-10",
        "Executive Car SP • TAX ID 11.183.125/0001-10",
    )
    return {"pt": pt, "en": en}
