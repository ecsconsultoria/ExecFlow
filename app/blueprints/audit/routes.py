"""Audit log viewer — read-only."""
from flask import render_template, request
from flask_login import login_required, current_user
from . import audit_bp
from ...models.audit import AuditLog
from ...utils.decorators import require_permission


@audit_bp.route("/")
@login_required
@require_permission("audit.view")
def index():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    q = (AuditLog.query
         .filter_by(company_id=current_user.company_id)
         .order_by(AuditLog.created_at.desc()))
    total = q.count()
    logs  = q.offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("audit/index.html",
                           logs=logs, page=page, pages=pages, total=total)
