from flask import Blueprint

short_links_bp = Blueprint("short_links", __name__)

from . import routes  # noqa: E402,F401
