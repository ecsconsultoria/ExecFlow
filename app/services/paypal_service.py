"""paypal_service.py — Pedidos de pagamento no PayPal (Checkout + Captura).

Fluxo do botão PayPal na página pública:
1. create_order: cria o pedido com o valor do orçamento (intent=CAPTURE) e
   devolve o order_id para o SDK do PayPal abrir o popup de pagamento;
2. capture_order: após o cliente aprovar, CAPTURA o pedido — só nesse
   momento o dinheiro é efetivamente movimentado.
"""
from __future__ import annotations

import requests
from flask import current_app


def _base() -> str:
    mode = current_app.config.get("PAYPAL_MODE", "sandbox")
    if mode == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


def _creds() -> tuple[str, str]:
    client_id = current_app.config.get("PAYPAL_CLIENT_ID", "")
    secret = current_app.config.get("PAYPAL_CLIENT_SECRET", "")
    if not client_id or not secret:
        raise ValueError("PayPal não configurado no servidor.")
    return client_id, secret


def _token() -> str:
    client_id, secret = _creds()
    r = requests.post(
        f"{_base()}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def create_order(amount: float, reference: str, return_url: str = "", cancel_url: str = "") -> str:
    """Cria o pedido e devolve o order_id (para o SDK abrir o popup)."""
    _creds()
    token = _token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": reference,
            "amount": {"currency_code": "BRL", "value": f"{float(amount):.2f}"},
        }],
    }
    if return_url:
        payload["application_context"] = {"return_url": return_url, "cancel_url": cancel_url}
    r = requests.post(
        f"{_base()}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def capture_order(order_id: str) -> str:
    """Captura o pedido aprovado pelo cliente. Devolve o status ('COMPLETED'...)."""
    _creds()
    token = _token()
    r = requests.post(
        f"{_base()}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("status", "")


def paypal_approve_url(amount: float, reference: str, return_url: str, cancel_url: str):
    """Link de aprovação (fluxo antigo de redirect) — mantido por compatibilidade."""
    _creds()
    token = _token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": reference,
            "amount": {"currency_code": "BRL", "value": f"{float(amount):.2f}"},
        }],
        "application_context": {"return_url": return_url, "cancel_url": cancel_url},
    }
    r = requests.post(
        f"{_base()}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return link["href"], None
    return None, "Resposta inesperada do PayPal: link de aprovação ausente"
