# REVIEW: Authentication blueprint module defining login, user administration, and session routes.
from flask import Blueprint
from .decorators import role_required as role_required  # explicit re-export

auth_bp = Blueprint('auth', __name__)

from . import routes  # noqa: F401,E402  # side-effect import: registers routes on auth_bp
from . import register_routes  # noqa: F401,E402  # side-effect import: registers register_routes endpoints
