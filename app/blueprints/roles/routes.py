"""Roles & Permissions — read-only listing (Phase 3).

Gestão de roles customizadas será adicionada futuramente atrás de roles.manage.

IMPORTANTE: Role e Permission são tabelas GLOBAIS (sem company_id).
Roles e permissões são definidas em nível de sistema, não por tenant.
Esta é uma decisão de design intencional — todos os tenants compartilham
o mesmo catálogo de permissões e roles canônicas.
"""
from collections import OrderedDict
from flask import render_template
from flask_login import login_required
from . import roles_bp
from ...models.rbac import Role, Permission
from ...utils.decorators import require_permission


@roles_bp.route("/")
@login_required
@require_permission("users.manage")
def index():
    # Tabelas globais — roles e permissões são compartilhadas entre tenants
    roles = Role.query.order_by(Role.code).all()

    # Agrupa permissions por categoria para exibir na UI
    perms_by_cat = OrderedDict()
    for p in Permission.query.order_by(Permission.category, Permission.code).all():
        perms_by_cat.setdefault(p.category, []).append(p)

    return render_template("roles/index.html",
                           roles=roles,
                           perms_by_cat=perms_by_cat)
