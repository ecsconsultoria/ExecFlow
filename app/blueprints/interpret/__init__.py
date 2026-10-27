from flask import Blueprint

interpret_bp = Blueprint("interpret", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
