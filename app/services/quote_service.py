"""QuoteService — criação e atualização de orçamentos."""
import json
from ..models.quote  import Quote, QuoteItem, QuoteInclusion
from ..extensions    import db
from ..utils         import now_br


def _next_number(company_id: int) -> str:
    from . import numbering_service
    return numbering_service.next_rfq(company_id)


def _parse_usd_rate(raw) -> float | None:
    """Converte a cotação R$/USD informada em float; retorna None se vazio/inválido."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        val = float(str(raw).replace(".", "").replace(",", ".")) if "," in str(raw) else float(raw)
    except (ValueError, TypeError):
        return None
    return val if val > 0 else None


class QuoteService:

    @staticmethod
    def create_quote(company_id: int, data: dict, created_by: int | None = None) -> Quote:
        items_data = data.get("items", [])
        if isinstance(items_data, str):
            items_data = json.loads(items_data)

        from datetime import date as _date
        raw_valid = data.get("valid_until")
        valid_until_val = None
        if raw_valid:
            try:
                valid_until_val = _date.fromisoformat(str(raw_valid))
            except (ValueError, TypeError):
                valid_until_val = None
        quote = Quote(
            company_id     = company_id,
            number         = _next_number(company_id),
            client_id      = data.get("client_id") or None,
            client_name    = data.get("client_name", ""),
            contact_name   = data.get("contact_name", ""),
            email          = data.get("email", ""),
            phone          = data.get("phone", ""),
            language       = data.get("language", "pt"),
            billing_type   = data.get("billing_type", "recibo"),
            payment_method = data.get("payment_method", "") or "",
            payment_terms  = data.get("payment_terms",  "") or "",
            obs            = data.get("obs", ""),
            usd_rate       = _parse_usd_rate(data.get("usd_rate")),
            valid_until    = valid_until_val,
            status         = "pendente",
            created_by     = created_by,
        )
        db.session.add(quote)
        db.session.flush()

        # Populate contact/email/phone from the linked client if not explicitly provided
        if quote.client_id and (not quote.contact_name or not quote.email or not quote.phone):
            from ..models.client import Client
            client_obj = Client.query.get(quote.client_id)
            if client_obj:
                if not quote.client_name:
                    quote.client_name  = client_obj.name or ""
                if not quote.contact_name:
                    quote.contact_name = client_obj.contact or ""
                if not quote.email:
                    quote.email        = client_obj.email or ""
                if not quote.phone:
                    quote.phone        = client_obj.phone or ""

        total = 0.0
        for i, it in enumerate(items_data):
            qty             = int(it.get("quantity", 1))
            price           = float(it.get("unit_price", 0))
            hour_extra_rate = float(it.get("hour_extra", 0))  # display rate, not added to total
            km_val          = round(float(it.get("km_extra", 0)) * float(it.get("km_extra_rate", 0)), 2)
            line            = round(price * qty + km_val, 2)
            item = QuoteItem(
                quote_id            = quote.id,
                service_id          = it.get("service_id") or None,
                category_id         = it.get("category_id") or None,
                description         = it.get("description", ""),
                vehicle_description = it.get("vehicle_description", ""),
                driver_name         = it.get("driver_name", "") or "",
                state_code          = it.get("state_code", "") or "",
                ref_note            = it.get("ref_note", "") or "",
                quantity            = qty,
                unit_price          = price,
                hour_extra          = hour_extra_rate,
                total_price         = line,
                sort_order          = int(it.get("sort_order", i)),
                price_base          = float(it.get("price_base",      0)),
                price_nf            = float(it.get("price_nf",        0)),
                price_cartao        = float(it.get("price_cartao",    0)),
                price_nf_cartao     = float(it.get("price_nf_cartao", 0)),
                km_extra            = float(it.get("km_extra",        0)),
                km_extra_rate       = float(it.get("km_extra_rate",   0)),
            )
            db.session.add(item)
            total += line

        quote.total_amount = round(total, 2)

        # Save inclusions / add-ons
        inclusions_data = data.get("inclusions", [])
        if isinstance(inclusions_data, str):
            inclusions_data = json.loads(inclusions_data)
        for idx, inc in enumerate(inclusions_data):
            qi = QuoteInclusion(
                quote_id   = quote.id,
                text_pt    = inc.get("text_pt", ""),
                text_en    = inc.get("text_en", ""),
                included   = bool(inc.get("included", True)),
                sort_order = int(inc.get("sort_order", idx)),
            )
            db.session.add(qi)

        db.session.commit()
        return quote

    @staticmethod
    def update_quote(quote: Quote, data: dict) -> Quote:
        items_data = data.get("items", [])
        if isinstance(items_data, str):
            items_data = json.loads(items_data)

        new_client_id = data.get("client_id") or quote.client_id
        client_changed = str(new_client_id) != str(quote.client_id) if (new_client_id and quote.client_id) else bool(new_client_id)
        quote.client_id = new_client_id

        # Repopula dados de contato do cliente vinculado sempre que o cliente mudar
        # ou se os campos não foram enviados explicitamente no data
        if quote.client_id:
            from ..models.client import Client
            client_obj = Client.query.get(quote.client_id)
            if client_obj:
                if client_changed or "client_name" not in data:
                    quote.client_name = client_obj.name or ""
                if client_changed or "contact_name" not in data:
                    quote.contact_name = client_obj.contact or ""
                if client_changed or "email" not in data:
                    quote.email = client_obj.email or ""
                if client_changed or "phone" not in data:
                    quote.phone = client_obj.phone or ""
        else:
            quote.client_name  = data.get("client_name",  quote.client_name or "")
            quote.contact_name = data.get("contact_name", quote.contact_name or "")
            quote.email        = data.get("email",        quote.email or "")
            quote.phone        = data.get("phone",        quote.phone or "")
        quote.language       = data.get("language",       quote.language)
        quote.billing_type   = data.get("billing_type",   quote.billing_type)
        quote.payment_method = data.get("payment_method", quote.payment_method)
        quote.payment_terms  = data.get("payment_terms",  quote.payment_terms)
        quote.obs            = data.get("obs",            quote.obs)
        if "usd_rate" in data:
            quote.usd_rate   = _parse_usd_rate(data.get("usd_rate"))

        for item in list(quote.items):
            db.session.delete(item)
        db.session.flush()

        total = 0.0
        for i, it in enumerate(items_data):
            qty             = int(it.get("quantity", 1))
            price           = float(it.get("unit_price", 0))
            hour_extra_rate = float(it.get("hour_extra", 0))  # display rate, not added to total
            km_val          = round(float(it.get("km_extra", 0)) * float(it.get("km_extra_rate", 0)), 2)
            line            = round(price * qty + km_val, 2)
            item = QuoteItem(
                quote_id            = quote.id,
                service_id          = it.get("service_id") or None,
                category_id         = it.get("category_id") or None,
                description         = it.get("description", ""),
                vehicle_description = it.get("vehicle_description", ""),
                driver_name         = it.get("driver_name", "") or "",
                state_code          = it.get("state_code", "") or "",
                ref_note            = it.get("ref_note", "") or "",
                quantity            = qty,
                unit_price          = price,
                hour_extra          = hour_extra_rate,
                total_price         = line,
                sort_order          = int(it.get("sort_order", i)),
                price_base          = float(it.get("price_base",      0)),
                price_nf            = float(it.get("price_nf",        0)),
                price_cartao        = float(it.get("price_cartao",    0)),
                price_nf_cartao     = float(it.get("price_nf_cartao", 0)),
                km_extra            = float(it.get("km_extra",        0)),
                km_extra_rate       = float(it.get("km_extra_rate",   0)),
            )
            db.session.add(item)
            total += line

        quote.total_amount = round(total, 2)

        # Update inclusions if provided
        inclusions_data = data.get("inclusions")
        if inclusions_data is not None:
            if isinstance(inclusions_data, str):
                inclusions_data = json.loads(inclusions_data)
            for inc in list(quote.inclusions):
                db.session.delete(inc)
            db.session.flush()
            for idx, inc in enumerate(inclusions_data):
                qi = QuoteInclusion(
                    quote_id   = quote.id,
                    text_pt    = inc.get("text_pt", ""),
                    text_en    = inc.get("text_en", ""),
                    included   = bool(inc.get("included", True)),
                    sort_order = int(inc.get("sort_order", idx)),
                )
                db.session.add(qi)

        quote.updated_at   = now_br()
        db.session.commit()
        return quote
