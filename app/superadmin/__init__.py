"""SuperAdmin Blueprint — platform-level administration of businesses and their admins."""

from flask import Blueprint

superadmin_bp = Blueprint(
    'superadmin',
    __name__,
    template_folder='templates',
    url_prefix='/superadmin',
)

from . import routes  # noqa: E402, F401