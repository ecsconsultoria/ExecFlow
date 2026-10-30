from flask import Blueprint

public_po_bp = Blueprint("public_po", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
