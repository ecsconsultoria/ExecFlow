"""Security hardening — Phase 8.

Fornece:
1. `LoginRateLimiter` — janela deslizante em memória para limitar tentativas
   de login por IP e por e-mail (defesa contra brute force / credential stuffing).
2. `register_security_headers(app)` — middleware after_request que adiciona
   headers de segurança padrão (X-Frame-Options, X-Content-Type-Options,
   Referrer-Policy, Permissions-Policy).

NOTA sobre produção: o rate limiter usa estado in-process. Em deploys com
múltiplos workers (gunicorn -w N) cada worker mantém seu próprio contador.
Para limite global use Flask-Limiter + Redis. Para a escala atual do app
(single-tenant ERP) o limiter local já oferece proteção significativa.
"""
from __future__ import annotations
import time
from collections import deque
from threading import Lock
from typing import Iterable


class LoginRateLimiter:
    """Janela deslizante simples por chave (IP ou e-mail).

    Uso:
        rl = LoginRateLimiter(max_attempts=5, window_seconds=900)
        if rl.is_blocked(ip): abort(429)
        # ... tenta login ...
        if falhou: rl.record_failure(ip)
        else: rl.reset(ip)
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        dq = self._events.setdefault(key, deque())
        cutoff = now - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()
        return dq

    def is_blocked(self, key: str) -> bool:
        if not key:
            return False
        with self._lock:
            now = time.time()
            dq = self._prune(key, now)
            return len(dq) >= self.max_attempts

    def record_failure(self, *keys: str) -> None:
        with self._lock:
            now = time.time()
            for k in keys:
                if not k:
                    continue
                dq = self._prune(k, now)
                dq.append(now)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._events.pop(k, None)

    def retry_after(self, key: str) -> int:
        """Segundos até o próximo slot liberar (estimativa para Retry-After)."""
        with self._lock:
            now = time.time()
            dq = self._prune(key, now)
            if len(dq) < self.max_attempts:
                return 0
            return max(1, int(dq[0] + self.window - now))


# Instância singleton — importada por auth/routes.py
login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def register_security_headers(app, extra: dict | None = None) -> None:
    """Registra hook after_request que aplica headers de segurança a toda resposta."""
    headers = dict(_SECURITY_HEADERS)
    if extra:
        headers.update(extra)

    @app.after_request
    def _apply_security_headers(response):
        for name, value in headers.items():
            response.headers.setdefault(name, value)
        # Cookie de sessão: HttpOnly já é default no Flask; reforçar SameSite=Lax
        # e Secure=True apenas em produção (config flag).
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security",
                                        "max-age=31536000; includeSubDomains")
        return response
