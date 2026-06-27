from flask import Blueprint

purchases_bp = Blueprint('purchases', __name__)

from . import routes  # noqa: E402,F401

