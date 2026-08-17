from flask import Blueprint

accounting_bp = Blueprint('accounting', __name__)

from . import routes  # noqa: E402,F401
