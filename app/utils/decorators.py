"""Decorators de autorização — idênticos ao V3."""
from functools import wraps
from flask import abort
from flask_login import current_user


def require_role(*roles):
    """Aborta com 403 se o user logado não tiver um dos roles informados."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
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
