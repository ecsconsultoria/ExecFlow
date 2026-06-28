"""Smoke test RBAC Phase 2b — SO/PO/Dispatch.

Cria (se necessário) dois usuários de teste no mesmo tenant do admin:
  * viewer_rbac@test.local      → role VIEWER  (só *.view, sem financeiro)
  * operational_rbac@test.local → role OPERATIONAL

Login via Flask test_client e probe os endpoints, comparando o status
recebido com o esperado.

Uso:
    python -m tools.smoke_rbac_phase2b
"""
from __future__ import annotations
import sys
from ExecFlow import app
from app.extensions import db
from app.models.user import User
from app.models.rbac import Role
from app.models.company import Company

TEST_PASSWORD = "TestRBAC123!"

USERS = {
    "VIEWER":      "viewer_rbac@test.local",
    "OPERATIONAL": "operational_rbac@test.local",
}

# (path, method, esperado_VIEWER, esperado_OPERATIONAL)
# GET 200 = permitido; 403 = bloqueado; 302 = redirect (cancel route redireciona
# em alguns casos antes de checar perm — só usamos GET de leitura aqui).
PROBES = [
    # leitura
    ("/orders/",                 "GET",  200, 200),
    ("/po/",                     "GET",  200, 200),
    ("/dispatch/",               "GET",  403, 200),  # VIEWER não tem dispatch.view? sim tem (.view universal)
    # ESCRITA — esperam 403 p/ VIEWER, 200/302 p/ OPERATIONAL (mas como id=99999 não existe,
    # OPERATIONAL deve receber 404 do _get_order; o que importa é que NÃO seja 403)
    ("/orders/99999/open",       "POST", 403, 404),
    ("/orders/99999/faturar",    "POST", 403, 403),  # OPERATIONAL não tem so.invoice
    ("/orders/99999/cancel",     "POST", 403, 403),  # OPERATIONAL não tem so.cancel
    ("/orders/99999/delete",     "POST", 403, 403),  # OPERATIONAL não tem so.delete
    ("/po/new",                  "GET",  403, 200),
    ("/po/99999/cancel",         "POST", 403, 403),  # OPERATIONAL não tem po.cancel
    ("/po/99999/conclude",       "POST", 403, 403),  # OPERATIONAL não tem po.close

    # ── Phase 2c ─────────────────────────────────────────────────────────
    # clients
    ("/clients/",                "GET",  200, 200),
    ("/clients/new",             "GET",  403, 200),  # VIEWER não tem clients.edit
    ("/clients/99999/delete",    "POST", 403, 403),  # OPERATIONAL não tem clients.delete
    # suppliers
    ("/suppliers/",              "GET",  200, 200),
    ("/suppliers/new",           "GET",  403, 403),  # OPERATIONAL não tem suppliers.edit (só view)
    # drivers / vehicles
    ("/drivers/new",             "GET",  403, 403),  # OPERATIONAL não tem drivers.edit
    ("/vehicles/new",            "GET",  403, 403),  # OPERATIONAL não tem vehicles.edit
    # catalog (services + categories)
    ("/categories/",             "GET",  200, 200),
    ("/services/",               "GET",  200, 200),
    ("/services/add",            "POST", 403, 403),  # OPERATIONAL não tem catalog.manage
    # quotes
    ("/quotes/",                 "GET",  200, 200),
    ("/quotes/new",              "GET",  403, 200),  # OPERATIONAL tem quote.create
    ("/quotes/99999/approve",    "POST", 403, 404),  # OPERATIONAL tem quote.approve → 404 (id inexistente)
    ("/quotes/99999/delete",     "POST", 403, 403),  # OPERATIONAL não tem quote.delete
    # bookings
    ("/bookings/",               "GET",  200, 200),
    ("/bookings/99999/complete", "POST", 403, 404),  # OPERATIONAL tem booking.edit → 404 (id inexistente)
    # reports
    ("/reports/",                "GET",  200, 200),
]


def _ensure_user(email: str, role_code: str, company_id: int) -> User:
    u = User.query.filter_by(email=email).first()
    role = Role.query.filter_by(code=role_code).first()
    if role is None:
        raise SystemExit(f"Role {role_code} não existe — rode o app pelo menos 1 vez para semear.")

    if u is None:
        u = User(
            email=email,
            name=f"Test {role_code}",
            company_id=company_id,
            is_active=True,
            role="operator",  # legacy column
        )
        u.set_password(TEST_PASSWORD)
        db.session.add(u)

    # garante roles M:N corretos (limpa e re-adiciona)
    u.roles = [role]
    u.is_active = True
    u.set_password(TEST_PASSWORD)
    db.session.commit()
    return u


def main() -> int:
    # /dispatch/ → VIEWER tem porque a regra é "todos *.view exceto financial/audit"
    # então corrigir esperado:
    expected_dispatch_viewer = 200
    for i, p in enumerate(PROBES):
        if p[0] == "/dispatch/":
            PROBES[i] = (p[0], p[1], expected_dispatch_viewer, p[3])

    with app.app_context():
        admin = User.query.filter_by(email="admin@executivecarsp.com").first()
        if admin is None:
            print("ERRO: admin não encontrado.")
            return 2
        cid = admin.company_id

        for role_code, email in USERS.items():
            _ensure_user(email, role_code, cid)
            print(f"  ✓ usuário {email} pronto (role={role_code})")

    failures = []
    for role_code, email in USERS.items():
        with app.test_client() as c:
            # login
            r = c.post("/auth/login",
                       data={"email": email, "password": TEST_PASSWORD},
                       follow_redirects=False)
            if r.status_code not in (200, 302):
                print(f"  ✗ login {email}: status={r.status_code}")
                failures.append((email, "login", r.status_code, "302"))
                continue
            print(f"\n=== {role_code} ({email}) ===")

            for (path, method, exp_viewer, exp_op) in PROBES:
                expected = exp_viewer if role_code == "VIEWER" else exp_op
                rr = c.open(path, method=method, follow_redirects=False)
                got = rr.status_code
                ok  = (got == expected)
                marker = "✓" if ok else "✗"
                print(f"  {marker} {method:4} {path:38} → got={got}  exp={expected}")
                if not ok:
                    failures.append((email, f"{method} {path}", got, expected))

    print("\n" + "=" * 60)
    if failures:
        print(f"FALHAS: {len(failures)}")
        for email, what, got, exp in failures:
            print(f"  - {email} | {what} | got={got} exp={exp}")
        return 1
    print("TODAS as checagens passaram ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
