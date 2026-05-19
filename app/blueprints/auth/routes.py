from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ...models.user import User
from ...utils import now_br
from ...extensions import db


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, is_active=True).first()
        if user and user.check_password(password):
            login_user(user)
            user.last_login = now_br()
            db.session.commit()
            return redirect(request.args.get("next") or url_for("dashboard.index"))
        flash("E-mail ou senha inválidos.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
