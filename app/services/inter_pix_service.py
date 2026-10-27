"""inter_pix_service.py — Cobrança Pix via Banco Inter (QR Code).

Fluxo: OAuth2 client_credentials com mTLS (certificado .crt/.key) → cria a
cobrança imediata (POST /pix/v2/cob) → busca o QR code e o copia-e-cola
(GET /pix/v2/loc/{id}/qrcode). Não persiste nada no banco.
"""
from __future__ import annotations

import base64
import tempfile

import requests
from flask import current_app

_cert_paths = None  # cache dos arquivos temporários do certificado mTLS


def _base() -> str:
    env = current_app.config.get("INTER_ENV", "sandbox")
    if env == "sandbox":
        return "https://cdpj-sandbox.partners.uatinter.co"
    return "https://cdpj.partners.bancointer.com.br"


def _cert():
    """Decodifica os certificados base64 para arquivos temporários (com cache)."""
    global _cert_paths
    if _cert_paths:
        return _cert_paths
    cert_b64 = current_app.config.get("INTER_CERT_BASE64", "")
    key_b64 = current_app.config.get("INTER_KEY_BASE64", "")
    if not cert_b64 or not key_b64:
        raise ValueError("Certificados Banco Inter não configurados")
    cert_f = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
    key_f = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
    cert_f.write(base64.b64decode(cert_b64))
    key_f.write(base64.b64decode(key_b64))
    cert_f.close()
    key_f.close()
    _cert_paths = (cert_f.name, key_f.name)
    return _cert_paths


def _token() -> str:
    """Access token OAuth2 do Banco Inter (client_credentials + mTLS)."""
    cert = _cert()
    r = requests.post(
        f"{_base()}/oauth/v2/token",
        data={
            "client_id": current_app.config.get("INTER_CLIENT_ID", ""),
            "client_secret": current_app.config.get("INTER_CLIENT_SECRET", ""),
            "scope": "cob.write cob.read",
            "grant_type": "client_credentials",
        },
        cert=cert,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def create_pix(amount: float, numero: str) -> dict:
    """Cria a cobrança Pix e devolve {txid, pix_codigo, qrcode_base64}."""
    if not current_app.config.get("INTER_PIX_KEY", ""):
        raise ValueError("Chave Pix (INTER_PIX_KEY) não configurada")
    cert = _cert()
    token = _token()
    payload = {
        "calendario": {"expiracao": 3600},
        "valor": {"original": f"{float(amount):.2f}"},
        "chave": current_app.config["INTER_PIX_KEY"],
        "solicitacaoPagador": f"Orcamento {numero}",
        "infoAdicionais": [{"nome": "Orcamento", "valor": numero}],
    }
    r = requests.post(
        f"{_base()}/pix/v2/cob",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        cert=cert,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    txid = data.get("txid", "")
    loc_id = data.get("loc", {}).get("id")
    pix_code = ""
    qr_base64 = ""
    if loc_id:
        qr_r = requests.get(
            f"{_base()}/pix/v2/loc/{loc_id}/qrcode",
            headers={"Authorization": f"Bearer {token}"},
            cert=cert,
            timeout=15,
        )
        if qr_r.ok:
            qr_data = qr_r.json()
            pix_code = qr_data.get("pixCopiaECola", "")
            qr_base64 = qr_data.get("imagemQrcode", "")
    return {"txid": txid, "pix_codigo": pix_code, "qrcode_base64": qr_base64}


def check_pix(txid: str) -> str:
    """Consulta o status da cobrança. Devolve 'pago' ou 'pendente'."""
    try:
        cert = _cert()
        token = _token()
        r = requests.get(
            f"{_base()}/pix/v2/cob/{txid}",
            headers={"Authorization": f"Bearer {token}"},
            cert=cert,
            timeout=10,
        )
        if not r.ok:
            return "pendente"
        return "pago" if r.json().get("status") == "CONCLUIDA" else "pendente"
    except Exception:
        return "pendente"
