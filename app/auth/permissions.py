"""Role-based access control and permission definitions."""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

# Permission definitions for each role
# '*' means all permissions granted
PERMISSIONS = {
    'admin': '*',
    'accountant': [
        'view_dashboard', 'view_reports', 'view_financials',
        'manage_expenses', 'view_inventory', 'view_products',
        'view_customers', 'view_suppliers', 'view_invoices',
        'view_payments', 'manage_settings',
    ],
    'cashier': [
        'view_dashboard', 'create_sale', 'create_receipt',
        'view_inventory', 'view_products', 'view_customers',
        'view_invoices',
    ],
    'storekeeper': [
        'view_inventory', 'manage_inventory', 'create_purchase',
        'view_products', 'view_suppliers', 'view_bills',
        'manage_production',
    ],
    'viewer': [
        'view_dashboard', 'view_reports', 'view_inventory',
        'view_products', 'view_customers', 'view_suppliers',
    ],
}


def has_permission(user, permission):
    """Check if a user has the given permission."""
    if not user or not user.is_authenticated:
        return False

    role = getattr(user, 'role', 'viewer')

    if role == 'admin':
        return True

    role_perms = PERMISSIONS.get(role, [])
    if role_perms == '*':
        return True
    if permission in role_perms:
        return True
    return False


def permission_required(permission):
    """Decorator that checks if the current user has the given permission."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if not has_permission(current_user, permission):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def check_feature_access(feature_name):
    """Check if the current business's subscription allows this feature.

    Can be used in templates or routes.
    Returns True if access is allowed.
    """
    from flask import current_app
    if current_app.testing and current_app.config.get('LOGIN_DISABLED'):
        return True

    try:
        from app.services.subscription_service import check_access
        biz_id = getattr(current_user, 'business_id', None)
        if biz_id is None:
            # For backwards-compatibility with seed data without business
            return True
        return check_access(biz_id, feature_name)
    except Exception:
        return True