"""RBAC models — Role, Permission e tabelas associativas M:N."""
from ..extensions import db
from .base import TimestampMixin


# ─────────────────────────────────────────────────────────────────────────────
# Tabelas associativas M:N
# ─────────────────────────────────────────────────────────────────────────────
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id",       db.Integer, db.ForeignKey("roles.id",       ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# ─────────────────────────────────────────────────────────────────────────────
class Permission(db.Model, TimestampMixin):
    __tablename__ = "permissions"

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    category    = db.Column(db.String(40),  nullable=False, index=True)
    label       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), default="")

    def __repr__(self):
        return f"<Permission {self.code}>"


# ─────────────────────────────────────────────────────────────────────────────
class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(40),  unique=True, nullable=False, index=True)
    label       = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), default="")
    is_system   = db.Column(db.Boolean, default=False, nullable=False)

    permissions = db.relationship(
        "Permission",
        secondary=role_permissions,
        lazy="select",
        backref=db.backref("roles", lazy="select"),
    )

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for p in self.permissions}

    def __repr__(self):
        return f"<Role {self.code}>"
