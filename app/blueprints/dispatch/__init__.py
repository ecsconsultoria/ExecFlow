from flask import Blueprint
dispatch_bp = Blueprint("dispatch", __name__)
from . import routes  # noqa
