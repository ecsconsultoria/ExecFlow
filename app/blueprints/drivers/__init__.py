from flask import Blueprint
drivers_bp = Blueprint("drivers", __name__)
from . import routes  # noqa
