"""Decorators de autorização RBAC.

Todas as rotas sensíveis devem ser protegidas server-side via
`@require_permission(...)` ou `@require_any_permission(...)`.
Template checks (`{% if has_perm(...) %}`) são apenas UX, NUNCA segurança.
"""
from functools import wraps
from flask import abort
from flask_login import current_user


def require_role(*codes):
    """Aborta com 403 se o user não pertencer a um dos roles informados.

    Aceita códigos do novo sistema (ADMIN/MANAGER/...) e legados
    (admin/superadmin/manager/operator). Implementado via `User.has_role()`.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_role(*codes):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_permission(code):
    """Aborta com 403 se o user não tiver a permission `code`.

    Exemplo: `@require_permission("financial.manage")`.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(code):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_any_permission(*codes):
    """Aborta com 403 se o user não tiver pelo menos UMA das permissions."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not any(current_user.has_permission(c) for c in codes):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def tenant_required(f):
    """Garante que current_user.company_id está definido."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.company_id:
            abort(403)
        return f(*args, **kwargs)
    return wrapped
