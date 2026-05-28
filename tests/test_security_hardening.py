"""Phase 8 — security hardening tests.

Cobre:
- Rate limiter (lógica pura)
- Login rate limit por IP/e-mail end-to-end (5 falhas → 429)
- Reset após sucesso
- Security headers presentes em respostas
"""
from __future__ import annotations
import pytest
from app.utils.security import LoginRateLimiter


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — limiter puro
# ──────────────────────────────────────────────────────────────────────────────

def test_rate_limiter_blocks_after_max():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert not rl.is_blocked("1.2.3.4")
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert not rl.is_blocked("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.is_blocked("1.2.3.4")


def test_rate_limiter_reset_clears_block():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.record_failure("x", "x")
    assert rl.is_blocked("x")
    rl.reset("x")
    assert not rl.is_blocked("x")


def test_rate_limiter_keys_are_independent():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.record_failure("a", "a")
    assert rl.is_blocked("a")
    assert not rl.is_blocked("b")


def test_rate_limiter_ignores_empty_keys():
    rl = LoginRateLimiter(max_attempts=1, window_seconds=60)
    rl.record_failure("", "")
    assert not rl.is_blocked("")


# ──────────────────────────────────────────────────────────────────────────────
# Integration — endpoint /auth/login
# ──────────────────────────────────────────────────────────────────────────────

def test_login_rate_limit_returns_429_after_5_failures(anon_client):
    from app.utils.security import login_rate_limiter
    login_rate_limiter.reset("127.0.0.1", "spam@nowhere.invalid")

    for _ in range(5):
        r = anon_client.post("/auth/login",
                             data={"email": "spam@nowhere.invalid",
                                   "password": "wrong"},
                             follow_redirects=False)
        # Falha normal devolve 200 (re-render do form com flash)
        assert r.status_code in (200, 302)

    # 6ª tentativa deve ser bloqueada
    r = anon_client.post("/auth/login",
                         data={"email": "spam@nowhere.invalid",
                               "password": "wrong"},
                         follow_redirects=False)
    assert r.status_code == 429, f"Esperava 429 após 5 falhas, recebeu {r.status_code}"

    # Cleanup para não afetar testes subsequentes
    login_rate_limiter.reset("127.0.0.1", "spam@nowhere.invalid")


def test_successful_login_resets_rate_limit(anon_client):
    from app.utils.security import login_rate_limiter
    from tests.conftest import ROLE_EMAILS, TEST_PASSWORD

    email = ROLE_EMAILS["VIEWER"]
    login_rate_limiter.reset("127.0.0.1", email)

    # 3 falhas (abaixo do limite)
    for _ in range(3):
        anon_client.post("/auth/login",
                         data={"email": email, "password": "wrong"},
                         follow_redirects=False)

    # Sucesso reseta o contador
    r = anon_client.post("/auth/login",
                         data={"email": email, "password": TEST_PASSWORD},
                         follow_redirects=False)
    assert r.status_code == 302  # redirect pós-login

    # Após sucesso, IP/email não estão bloqueados
    assert not login_rate_limiter.is_blocked(email)
    assert not login_rate_limiter.is_blocked("127.0.0.1")


# ──────────────────────────────────────────────────────────────────────────────
# Security headers
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("header,expected_substr", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options",        "SAMEORIGIN"),
    ("Referrer-Policy",        "strict-origin"),
    ("Permissions-Policy",     "geolocation"),
])
def test_security_headers_on_login_page(anon_client, header, expected_substr):
    r = anon_client.get("/auth/login")
    assert r.status_code == 200
    assert header in r.headers, f"Header {header} ausente"
    assert expected_substr in r.headers[header]


def test_security_headers_on_authenticated_page(viewer_client):
    r = viewer_client.get("/orders/")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "SAMEORIGIN" in r.headers.get("X-Frame-Options", "")
