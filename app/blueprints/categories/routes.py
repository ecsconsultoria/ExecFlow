from flask import render_template
from flask_login import login_required
from . import categories_bp
from ...models.vehicle import VehicleCategory
from ...utils.decorators import require_permission


@categories_bp.route("/")
@login_required
@require_permission("catalog.view")
def index():
    categories = VehicleCategory.query.order_by(VehicleCategory.sort_order).all()
    return render_template("categories/index.html", categories=categories)
