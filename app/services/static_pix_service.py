"""static_pix_service.py — QR Code PIX estático com valor injetado.

Enquanto a integração Banco Inter (cobrança dinâmica) está em análise, usa o
payload EMV "copia e cola" estático da empresa e injeta o campo 54 (valor da
cobrança) recalculando o CRC-16/CCITT-FALSE. O app do banco abre pré-preenchido
com o valor real do orçamento.

Atenção: PIX estático NÃO avisa pagamento — a confirmação é conferida pela
empresa no extrato.
"""
from __future__ import annotations

import base64
import io

import qrcode
from flask import current_app


def _crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _parse_tlv(payload: str) -> dict:
    """Parseia os campos EMV (antes do campo 63/CRC)."""
    fields = {}
    i = 0
    n = len(payload)
    while i + 4 <= n:
        tag = payload[i:i + 2]
        if tag == "63":
            break
        ln = int(payload[i + 2:i + 4])
        fields[tag] = payload[i + 4:i + 4 + ln]
        i += 4 + ln
    return fields


def with_amount(base_payload: str, amount: float) -> str:
    """Devolve o payload com o campo 54 (valor) e o CRC recalculado."""
    fields = _parse_tlv(base_payload)
    fields["54"] = f"{float(amount):.2f}"
    out = "".join(f"{tag}{len(val):02d}{val}" for tag, val in sorted(fields.items()))
    out += "6304" + f"{_crc16_ccitt_false(out.encode() + b'6304'):04X}"
    return out


def qr_base64(payload: str) -> str:
    """Gera a imagem PNG do QR Code em base64."""
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_static_pix(amount: float) -> dict:
    """Monta a cobrança estática: {pix_codigo, qrcode_base64} (sem txid)."""
    base = current_app.config.get("PIX_STATIC_CODE", "")
    if not base:
        raise ValueError("PIX estático não configurado (PIX_STATIC_CODE).")
    payload = with_amount(base, amount)
    return {"txid": "", "pix_codigo": payload, "qrcode_base64": qr_base64(payload)}
