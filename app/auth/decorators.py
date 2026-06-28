from functools import wraps
from flask import abort, current_app
from flask_login import current_user


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Allow all roles when LOGIN_DISABLED (e.g. testing)
            if current_app.config.get("LOGIN_DISABLED", False):
                return f(*args, **kwargs)
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
