from flask import Blueprint

production_bp = Blueprint('production', __name__)

from . import routes  # noqa: E402,F401
