"""Phase 9 — unit tests para decorators RBAC + helper de auditoria.

Cobre código de segurança/compliance que estava com baixa cobertura no
relatório do pytest-cov:
- app/utils/decorators.py (era 37%)
- app/utils/audit.py     (era 60%)
"""
from __future__ import annotations
import pytest
from werkzeug.exceptions import Forbidden, Unauthorized
from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from app.models.rbac import Role
from app.utils.audit import log_activity
from app.utils.decorators import (
    require_role,
    require_permission,
    require_any_permission,
    tenant_required,
)


ADMIN_EMAIL = "admin@executivecarsp.com"


# ──────────────────────────────────────────────────────────────────────────────
# Decorators — exercícios diretos via login_user no test_request_context
# ──────────────────────────────────────────────────────────────────────────────

def _run_with_user(app, user, view_fn):
    """Executa view_fn() dentro de um request com `user` logado.

    Usa flask_login.login_user dentro de app.test_request_context para
    simular um request autenticado sem precisar passar pelo HTTP.
    """
    from flask_login import login_user
    with app.test_request_context():
        login_user(user)
        return view_fn()


def _anonymous(app, view_fn):
    with app.test_request_context():
        return view_fn()


def test_require_permission_blocks_anonymous(app):
    @require_permission("clients.view")
    def view():
        return "ok"
    with pytest.raises(Unauthorized):
        _anonymous(app, view)


def test_require_permission_blocks_user_without_perm(app):
    @require_permission("financial.manage")  # VIEWER não tem
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    with pytest.raises(Forbidden):
        _run_with_user(app, u, view)


def test_require_permission_allows_user_with_perm(app):
    @require_permission("dashboard.view")
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    assert _run_with_user(app, u, view) == "ok"


def test_require_any_permission_passes_if_any(app):
    @require_any_permission("financial.manage", "dashboard.view")
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    assert _run_with_user(app, u, view) == "ok"


def test_require_any_permission_blocks_if_none(app):
    @require_any_permission("financial.manage", "audit.view")
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    with pytest.raises(Forbidden):
        _run_with_user(app, u, view)


def test_require_role_allows_matching(app):
    @require_role("VIEWER", "ADMIN")
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    assert _run_with_user(app, u, view) == "ok"


def test_require_role_blocks_non_matching(app):
    @require_role("ADMIN")
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
    with pytest.raises(Forbidden):
        _run_with_user(app, u, view)


def test_tenant_required_blocks_anonymous(app):
    @tenant_required
    def view():
        return "ok"
    with pytest.raises(Forbidden):
        _anonymous(app, view)


def test_tenant_required_allows_user_with_company(app):
    @tenant_required
    def view():
        return "ok"
    with app.app_context():
        u = User.query.filter_by(email="viewer_rbac@test.local").first()
        assert u.company_id is not None
    assert _run_with_user(app, u, view) == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# Audit helper
# ──────────────────────────────────────────────────────────────────────────────

def test_log_activity_creates_entry_pending_commit(app):
    """log_activity adiciona à sessão; caller commita."""
    with app.app_context():
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        before = AuditLog.query.count()
        log_activity("test_entity", 42, admin.company_id,
                     "ação de teste Phase 9", admin.id)
        db.session.commit()
        after = AuditLog.query.count()
        assert after == before + 1
        entry = (AuditLog.query
                 .filter_by(entity="test_entity", entity_id=42)
                 .order_by(AuditLog.id.desc()).first())
        assert entry is not None
        assert entry.action == "ação de teste Phase 9"
        assert entry.user_id == admin.id
        assert entry.company_id == admin.company_id

        # Cleanup
        db.session.delete(entry)
        db.session.commit()


def test_log_activity_accepts_null_user(app):
    """Ações de sistema podem ter user_id=None."""
    with app.app_context():
        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        log_activity("system", 0, admin.company_id, "evento sem user", None)
        db.session.commit()
        entry = (AuditLog.query
                 .filter_by(entity="system", action="evento sem user")
                 .order_by(AuditLog.id.desc()).first())
        assert entry is not None
        assert entry.user_id is None
        db.session.delete(entry)
        db.session.commit()
