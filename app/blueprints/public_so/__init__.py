from flask import Blueprint

public_so_bp = Blueprint("public_so", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
