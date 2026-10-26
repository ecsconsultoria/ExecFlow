from flask import Blueprint

public_quotes_bp = Blueprint("public_quotes", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
