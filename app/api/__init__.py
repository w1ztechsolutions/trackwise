# REVIEW: JSON REST API blueprint exporting AJAX lookups and accounting verification endpoints.
from flask import Blueprint

api_bp = Blueprint('api', __name__)

from . import routes  # noqa: E402,F401

