"""Dispatch blueprint routes — Centro Operacional."""
from flask import render_template, request
from flask_login import login_required, current_user
from . import dispatch_bp
from ...services import dispatch_service
from ...utils import now_br
from ...utils.decorators import require_permission
from datetime import date, timedelta


@dispatch_bp.route("/")
@login_required
@require_permission("dispatch.view")
def index():
    cid = current_user.company_id
    date_str = request.args.get("date", "")
    if date_str:
        try:
            ref_date = date.fromisoformat(date_str)
        except ValueError:
            ref_date = now_br().date()
    else:
        ref_date = now_br().date()

    summary = dispatch_service.get_summary(cid, ref_date)
    prev_date = (ref_date - timedelta(days=1)).isoformat()
    next_date = (ref_date + timedelta(days=1)).isoformat()
    return render_template("dispatch/index.html", summary=summary,
                           ref_date=ref_date.isoformat(), today=now_br().date().isoformat(),
                           prev_date=prev_date, next_date=next_date)
