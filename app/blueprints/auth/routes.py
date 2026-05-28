from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ...models.user import User
from ...utils import now_br
from ...utils.security import login_rate_limiter
from ...extensions import db


def _client_ip() -> str:
    """Extrai IP cliente honrando X-Forwarded-For (1º hop) em deploys com proxy."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        ip       = _client_ip()

        # Rate-limit ANTES de qualquer query — protege contra enumeração de e-mails
        if login_rate_limiter.is_blocked(ip) or (email and login_rate_limiter.is_blocked(email)):
            retry = max(login_rate_limiter.retry_after(ip),
                        login_rate_limiter.retry_after(email))
            flash(f"Muitas tentativas. Tente novamente em {retry//60 + 1} min.", "error")
            resp = render_template("auth/login.html"), 429
            return resp

        user = User.query.filter_by(email=email, is_active=True).first()
        if user and user.check_password(password):
            login_rate_limiter.reset(ip, email)
            login_user(user)
            user.last_login = now_br()
            db.session.commit()
            if user.must_change_password:
                flash("Por favor, defina uma nova senha.", "warning")
                return redirect(url_for("auth.change_password"))
            return redirect(request.args.get("next") or url_for("dashboard.index"))

        # Falha — registra IP + e-mail (mesmo que e-mail não exista, para
        # impedir enumeração via timing/contagem)
        login_rate_limiter.record_failure(ip, email)
        flash("E-mail ou senha inválidos.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    force = bool(current_user.must_change_password)
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw     = request.form.get("new_password", "")
        confirm    = request.form.get("confirm_password", "")
        if not current_user.check_password(current_pw):
            flash("Senha atual incorreta.", "danger")
        elif len(new_pw) < 6:
            flash("Nova senha deve ter no mínimo 6 caracteres.", "danger")
        elif new_pw != confirm:
            flash("Confirmação não confere.", "danger")
        elif new_pw == current_pw:
            flash("A nova senha deve ser diferente da atual.", "danger")
        else:
            current_user.set_password(new_pw)
            current_user.must_change_password = False
            db.session.commit()
            flash("Senha atualizada.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", force=force)
