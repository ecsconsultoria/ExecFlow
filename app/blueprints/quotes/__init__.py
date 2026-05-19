from flask import Blueprint
quotes_bp = Blueprint("quotes", __name__)
from . import routes  # noqa
