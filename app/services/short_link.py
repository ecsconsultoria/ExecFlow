"""short_link.py — Códigos curtos (base62) para links públicos.

Formato dos links: <SHORT_BASE_URL>/l/<code> (ex.: checkin.executivecarsp.com/l/AbC123)
redirecionando para a agenda pública completa com token HMAC.
"""
from __future__ import annotations

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(_ALPHABET)


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
