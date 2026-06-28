"""Pytest fixtures for App_Orcamentos_V2.

Uses the running app's SQLite database (instance/DB_V2.db). Tests are
read-only RBAC probes against fake IDs (99999) — no real data is mutated.
"""
from __future__ import annotations
import os
import sys
import pytest

# Ensure project root on path
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ExecFlow import app as _app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.rbac import Role  # noqa: E402

TEST_PASSWORD = "TestRBAC123!"
ADMIN_EMAIL = "admin@executivecarsp.com"

ROLE_EMAILS = {
    "VIEWER":      "viewer_rbac@test.local",
    "OPERATIONAL": "operational_rbac@test.local",
}


@pytest.fixture(scope="session")
def app():
    # Tests usam o mesmo app dev (com DB real) — desabilitamos CSRF aqui
    # porque o test_client não emite tokens. Em produção CSRF segue ativo.
    _app.config["WTF_CSRF_ENABLED"] = False
    return _app


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_users(app):
    """Garante que os usuários de teste existem com as roles corretas."""
    with app.app_context():
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        if admin is None:
            pytest.skip("Admin user não encontrado — rode o app pelo menos 1 vez para semear.")
        cid = admin.company_id

        for role_code, email in ROLE_EMAILS.items():
            role = Role.query.filter_by(code=role_code).first()
            if role is None:
                pytest.skip(f"Role {role_code} não existe — rode o seeder RBAC.")
            u = User.query.filter_by(email=email).first()
            if u is None:
                u = User(email=email, name=f"Test {role_code}",
                         company_id=cid, is_active=True, role="operator")
                u.set_password(TEST_PASSWORD)
                db.session.add(u)
            u.roles = [role]
            u.is_active = True
            u.set_password(TEST_PASSWORD)
            db.session.commit()
    yield


def _login(email: str):
    c = _app.test_client()
    r = c.post("/auth/login",
               data={"email": email, "password": TEST_PASSWORD},
               follow_redirects=False)
    assert r.status_code in (200, 302), f"login {email} falhou ({r.status_code})"
    return c


@pytest.fixture
def viewer_client():
    return _login(ROLE_EMAILS["VIEWER"])


@pytest.fixture
def operational_client():
    return _login(ROLE_EMAILS["OPERATIONAL"])


@pytest.fixture
def anon_client():
    return _app.test_client()


@pytest.fixture
def admin_client():
    """Login como superadmin (acesso a todas as perms)."""
    c = _app.test_client()
    r = c.post("/auth/login",
               data={"email": ADMIN_EMAIL, "password": "admin123"},
               follow_redirects=False)
    assert r.status_code in (200, 302), f"login admin falhou ({r.status_code})"
    return c
