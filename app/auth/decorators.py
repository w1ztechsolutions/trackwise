from functools import wraps

from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user


# REVIEW: Role-based authorization decorator.
# REVIEW: Enforces current_user.role in allowed_roles; returns 401 if unauthenticated, 403 if unauthorized.
# REVIEW: Bypassed when testing with LOGIN_DISABLED=True.
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


# REVIEW: Phase D (ADR-0018) — mutation-scoped role guard for money routes.
# REVIEW: Unlike role_required (403 on every method), this only intercepts
# REVIEW: MUTATING requests (POST/PUT/PATCH/DELETE): read pages stay open to
# REVIEW: all logged-in staff, while the financial write paths require one of
# REVIEW: the allowed roles. Denial is a flash + redirect back instead of a
# REVIEW: bare 403, because these are form submissions from the browser UI —
# REVIEW: the user sees why the action was refused instead of an error page.
def mutation_role_required(*allowed_roles):
    """Decorator enforcing allowed roles on mutating HTTP methods only."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_app.config.get("LOGIN_DISABLED", False):
                return f(*args, **kwargs)
            if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
                return f(*args, **kwargs)
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in allowed_roles:
                flash(
                    'Your role is not permitted to perform this action. '
                    'Ask an admin or manager for help.',
                    'danger',
                )
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator
