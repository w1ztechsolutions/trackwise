from flask import Blueprint
from .decorators import role_required

auth_bp = Blueprint('auth', __name__)

from . import routes  # noqa: F401,E402