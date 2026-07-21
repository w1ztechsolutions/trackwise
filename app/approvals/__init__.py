"""Approvals Blueprint — approval workflow configuration and transaction approval processing."""

from flask import Blueprint

approvals_bp = Blueprint(
    'approvals',
    __name__,
    template_folder='templates',
    url_prefix='/approvals',
)

from . import routes  # noqa: E402, F401