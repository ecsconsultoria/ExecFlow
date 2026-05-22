from flask import Blueprint
purchase_orders_bp = Blueprint("purchase_orders", __name__)
from . import routes  # noqa
