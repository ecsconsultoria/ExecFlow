from flask import Blueprint
service_orders_bp = Blueprint("service_orders", __name__)
from . import routes  # noqa
