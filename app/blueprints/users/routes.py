"""Users management — admin CRUD + role assignment.

Todas as rotas protegidas por @require_permission("users.manage").
Mantém isolamento por company (não vê users de outras empresas).
"""
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import users_bp
from ...models.user import User
from ...models.rbac import Role
from ...extensions import db
from ...utils.decorators import require_permission


@users_bp.route("/")
@login_required
@require_permission("users.manage")
def index():
    users = (User.query
             .filter_by(company_id=current_user.company_id)
             .order_by(User.is_active.desc(), User.name.asc())
             .all())
    return render_template("users/index.html", users=users)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("users.manage")
def new():
    roles = Role.query.order_by(Role.code).all()
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name  = (request.form.get("name")  or "").strip()
        if not email or not name:
            flash("Nome e e-mail são obrigatórios.", "danger")
            return render_template("users/form.html", user=None, roles=roles, role_ids=[])

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.", "danger")
            return render_template("users/form.html", user=None, roles=roles, role_ids=[])

        password = (request.form.get("password") or "").strip()
        if len(password) < 6:
            flash("Senha deve ter no mínimo 6 caracteres.", "danger")
            return render_template("users/form.html", user=None, roles=roles, role_ids=[])

        u = User(
            company_id           = current_user.company_id,
            name                 = name,
            email                = email,
            is_active            = bool(request.form.get("is_active")),
            must_change_password = True,   # força troca no 1º login
            role                 = "operator",  # legacy default
        )
        u.set_password(password)

        # Roles atribuídas
        selected_ids = [int(x) for x in request.form.getlist("roles") if x.isdigit()]
        u.roles = [r for r in roles if r.id in selected_ids]

        db.session.add(u)
        db.session.commit()
        flash("Usuário criado. Ele deverá trocar a senha no primeiro login.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", user=None, roles=roles, role_ids=[])


@users_bp.route("/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("users.manage")
def edit(uid):
    u = User.query.filter_by(id=uid, company_id=current_user.company_id).first_or_404()
    roles = Role.query.order_by(Role.code).all()

    if request.method == "POST":
        u.name      = (request.form.get("name") or u.name).strip()
        u.is_active = bool(request.form.get("is_active"))

        selected_ids = [int(x) for x in request.form.getlist("roles") if x.isdigit()]

        # Self-lockout: usuário logado não pode remover o próprio ADMIN
        if u.id == current_user.id:
            admin_role = Role.query.filter_by(code="ADMIN").first()
            if admin_role and admin_role.id not in selected_ids and current_user._is_effective_admin():
                flash("Você não pode remover seu próprio papel ADMIN.", "danger")
                return redirect(url_for("users.edit", uid=u.id))

        u.roles = [r for r in roles if r.id in selected_ids]

        # Reset opcional de senha
        new_pass = (request.form.get("new_password") or "").strip()
        if new_pass:
            if len(new_pass) < 6:
                flash("Nova senha deve ter no mínimo 6 caracteres.", "danger")
                return redirect(url_for("users.edit", uid=u.id))
            u.set_password(new_pass)
            u.must_change_password = True
            flash("Senha redefinida. Usuário deverá trocá-la no próximo login.", "warning")

        db.session.commit()
        flash("Usuário atualizado.", "success")
        return redirect(url_for("users.index"))

    role_ids = [r.id for r in u.roles]
    return render_template("users/form.html", user=u, roles=roles, role_ids=role_ids)


@users_bp.route("/<int:uid>/toggle-active", methods=["POST"])
@login_required
@require_permission("users.manage")
def toggle_active(uid):
    u = User.query.filter_by(id=uid, company_id=current_user.company_id).first_or_404()
    if u.id == current_user.id:
        flash("Você não pode desativar a si mesmo.", "danger")
        return redirect(url_for("users.index"))
    u.is_active = not u.is_active
    db.session.commit()
    flash(f"Usuário {'ativado' if u.is_active else 'desativado'}.", "info")
    return redirect(url_for("users.index"))
