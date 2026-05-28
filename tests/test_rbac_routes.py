"""RBAC route-permission probes (Phase 6 — pytest port of smoke_rbac_phase2b).

Cada probe é uma tupla (path, method, expected_viewer, expected_operational).
- 200 = acesso permitido (GET) ou ação executou (POST)
- 403 = bloqueado por permissão
- 404 = passou o gate de permissão mas o ID inexistente (99999) não foi encontrado
- 302 = redirect (login ou flash)
"""
from __future__ import annotations
import pytest

PROBES = [
    # ── leitura ────────────────────────────────────────────────────────
    ("/orders/",                 "GET",  200, 200),
    ("/po/",                     "GET",  200, 200),
    ("/dispatch/",               "GET",  200, 200),

    # ── orders / SO ────────────────────────────────────────────────────
    ("/orders/99999/open",       "POST", 403, 404),
    ("/orders/99999/faturar",    "POST", 403, 403),  # OPERATIONAL não tem so.invoice
    ("/orders/99999/cancel",     "POST", 403, 403),  # OPERATIONAL não tem so.cancel
    ("/orders/99999/delete",     "POST", 403, 403),  # OPERATIONAL não tem so.delete

    # ── PO ─────────────────────────────────────────────────────────────
    ("/po/new",                  "GET",  403, 200),
    ("/po/99999/cancel",         "POST", 403, 403),
    ("/po/99999/conclude",       "POST", 403, 403),

    # ── clients / suppliers / drivers / vehicles ───────────────────────
    ("/clients/",                "GET",  200, 200),
    ("/clients/new",             "GET",  403, 200),
    ("/clients/99999/delete",    "POST", 403, 403),
    ("/suppliers/",              "GET",  200, 200),
    ("/suppliers/new",           "GET",  403, 403),
    ("/drivers/new",             "GET",  403, 403),
    ("/vehicles/new",            "GET",  403, 403),

    # ── catálogo ───────────────────────────────────────────────────────
    ("/categories/",             "GET",  200, 200),
    ("/services/",               "GET",  200, 200),
    ("/services/add",            "POST", 403, 403),

    # ── quotes ─────────────────────────────────────────────────────────
    ("/quotes/",                 "GET",  200, 200),
    ("/quotes/new",              "GET",  403, 200),
    ("/quotes/99999/approve",    "POST", 403, 404),
    ("/quotes/99999/delete",     "POST", 403, 403),

    # ── bookings ───────────────────────────────────────────────────────
    ("/bookings/",               "GET",  200, 200),
    ("/bookings/99999/complete", "POST", 403, 404),

    # ── reports ────────────────────────────────────────────────────────
    ("/reports/",                "GET",  200, 200),
]


@pytest.mark.parametrize("path,method,exp_viewer,exp_op", PROBES,
                         ids=[f"{m} {p}" for p, m, *_ in PROBES])
def test_viewer_role(viewer_client, path, method, exp_viewer, exp_op):
    r = viewer_client.open(path, method=method, follow_redirects=False)
    assert r.status_code == exp_viewer, (
        f"VIEWER {method} {path}: esperava {exp_viewer}, recebeu {r.status_code}"
    )


@pytest.mark.parametrize("path,method,exp_viewer,exp_op", PROBES,
                         ids=[f"{m} {p}" for p, m, *_ in PROBES])
def test_operational_role(operational_client, path, method, exp_viewer, exp_op):
    r = operational_client.open(path, method=method, follow_redirects=False)
    assert r.status_code == exp_op, (
        f"OPERATIONAL {method} {path}: esperava {exp_op}, recebeu {r.status_code}"
    )


def test_anonymous_redirects_to_login(anon_client):
    """Sem login → endpoints protegidos devolvem 302 → /auth/login."""
    r = anon_client.get("/orders/", follow_redirects=False)
    assert r.status_code == 302
    assert "/auth/login" in r.headers.get("Location", "")
