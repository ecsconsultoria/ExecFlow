"""paypal_service.py — Criação de pedido de pagamento no PayPal (Checkout).

Usa as credenciais do config (PAYPAL_CLIENT_ID/SECRET/MODE) e devolve o link
de aprovação (approve) para o cliente pagar o orçamento. Não captura o
pagamento — apenas abre o checkout do PayPal já com o valor.
"""
from __future__ import annotations

import requests
from flask import current_app


def paypal_approve_url(amount: float, reference: str, return_url: str, cancel_url: str):
    """Cria o pedido no PayPal e devolve (approve_url, erro)."""
    client_id = current_app.config.get("PAYPAL_CLIENT_ID", "")
    secret = current_app.config.get("PAYPAL_CLIENT_SECRET", "")
    mode = current_app.config.get("PAYPAL_MODE", "sandbox")
    if not client_id or not secret:
        return None, "PayPal não configurado no servidor."
    base = "https://api-m.sandbox.paypal.com" if mode == "sandbox" else "https://api-m.paypal.com"
    try:
        token = _token(base, client_id, secret)
        approve = _create_order(base, token, amount, reference, return_url, cancel_url)
        return approve, None
    except requests.RequestException as exc:
        return None, f"Falha na API do PayPal: {exc}"
    except (KeyError, ValueError) as exc:
        return None, f"Resposta inesperada do PayPal: {exc}"


def _token(base: str, client_id: str, secret: str) -> str:
    r = requests.post(
        f"{base}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _create_order(base: str, token: str, amount: float, reference: str,
                  return_url: str, cancel_url: str) -> str:
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": reference,
            "amount": {"currency_code": "BRL", "value": f"{float(amount):.2f}"},
        }],
        "application_context": {"return_url": return_url, "cancel_url": cancel_url},
    }
    r = requests.post(
        f"{base}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return link["href"]
    raise ValueError("link de aprovação ausente")
