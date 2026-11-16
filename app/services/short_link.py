"""short_link.py — Códigos curtos para links públicos.

Legado: <SHORT_BASE_URL>/l/<code> (base62, case-sensitive) — links antigos
continuam funcionando, mas novos links usam base36 minúscula em namespace
próprio para sobreviver a lowercasing de WhatsApp/Excel/digitacao:
  - PO: <SHORT_BASE_URL>/l/p/<code36>
  - SO: <SHORT_BASE_URL>/l/s/<code36>
"""
from __future__ import annotations

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(_ALPHABET)

# Base36 minúscula (subconjunto da base62 — índice idêntico dos chars)
_ALPHABET_LOWER = _ALPHABET[:36]
_BASE_LOWER = 36


def encode(n: int) -> str:
    """Codifica um id inteiro em base62."""
    if n < 0:
        raise ValueError("n deve ser >= 0")
    if n == 0:
        return _ALPHABET[0]
    out = []
    while n:
        n, r = divmod(n, _BASE)
        out.append(_ALPHABET[r])
    return "".join(reversed(out))


def decode(s: str) -> int | None:
    """Decodifica um código base62 de volta para o id (None se inválido)."""
    try:
        n = 0
        for ch in s:
            n = n * _BASE + _ALPHABET.index(ch)
        return n
    except ValueError:
        return None


def encode_lower(n: int) -> str:
    """Codifica um id inteiro em base36 minúscula (imune a lowercasing)."""
    if n < 0:
        raise ValueError("n deve ser >= 0")
    if n == 0:
        return _ALPHABET_LOWER[0]
    out = []
    while n:
        n, r = divmod(n, _BASE_LOWER)
        out.append(_ALPHABET_LOWER[r])
    return "".join(reversed(out))


def decode_lower(s: str) -> int | None:
    """Decodifica um código base36 de volta para o id.

    Tolerante a caixa: lowercasing (WhatsApp/Excel/digitacao) e uppercasing
    de qualquer ferramenta produzem o mesmo id.
    """
    try:
        n = 0
        for ch in s.lower():
            n = n * _BASE_LOWER + _ALPHABET_LOWER.index(ch)
        return n
    except ValueError:
        return None
