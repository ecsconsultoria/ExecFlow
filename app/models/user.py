from flask import g, has_request_context
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db, login_manager
from .base import TimestampMixin
from .rbac import user_roles  # association table M:N


# Legacy role values — mantidos para backward-compat (User.role string).
ROLES = ("superadmin", "admin", "manager", "operator")


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id                   = db.Column(db.Integer, primary_key=True)
    company_id           = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name                 = db.Column(db.String(200), nullable=False)
    email                = db.Column(db.String(200), unique=True, nullable=False)
    password_hash        = db.Column(db.String(500))
    # Coluna legada single-role — preservada para rollback/compat. Não dropar.
    role                 = db.Column(db.String(50), default="operator")
    is_active            = db.Column(db.Boolean, default=True)
    last_login           = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)

    # RBAC novo: M:N com Role
    roles = db.relationship(
        "Role",
        secondary=user_roles,
        lazy="joined",
        backref=db.backref("users", lazy="select"),
    )

    # ── senha ────────────────────────────────────────────────────────────────
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # ── helpers RBAC ─────────────────────────────────────────────────────────
    @property
    def role_codes(self) -> set:
        """Códigos dos Role objects atribuídos (novo sistema)."""
        return {r.code for r in (self.roles or [])}

    def has_role(self, *codes) -> bool:
        """
        Verifica se o user pertence a um dos roles informados.

        Aceita códigos do novo sistema (ADMIN/MANAGER/OPERATIONAL/FINANCIAL/VIEWER)
        E códigos legados (superadmin/admin/manager/operator) para backward-compat.
        """
        if not codes:
            return False
        wanted = set(codes)
        if wanted & self.role_codes:
            return True
        if self.role and self.role in wanted:
            return True
        return False

    def permission_codes(self) -> set:
        """Union das permissões de todos os roles atribuídos.

        Shortcut: se for ADMIN (novo ou legacy), retorna o catálogo completo.
        """
        if self._is_effective_admin():
            from ..utils.permissions import ALL_PERMS
            return set(ALL_PERMS)
        codes = set()
        for r in (self.roles or []):
            codes |= r.permission_codes
        return codes

    def has_permission(self, code: str) -> bool:
        """Checa permissão. Cache por request via flask.g."""
        if not code:
            return False
        if self._is_effective_admin():
            return True
        cache = self._perm_cache()
        if cache is not None:
            return code in cache
        return code in self.permission_codes()

    # ── internos ─────────────────────────────────────────────────────────────
    def _is_effective_admin(self) -> bool:
        """ADMIN no novo sistema OU role legado admin/superadmin."""
        if "ADMIN" in self.role_codes:
            return True
        if self.role in ("admin", "superadmin"):
            return True
        return False

    def _perm_cache(self):
        if not has_request_context():
            return None
        key = f"_perm_cache_{self.id}"
        cached = getattr(g, key, None)
        if cached is None:
            cached = self.permission_codes()
            setattr(g, key, cached)
        return cached

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
