"""Admin-only user creation route.

Replaced the public registration flow. Now only business admins can create
new users for their business. New users are created with must_change_password=True
so they are forced to set their own password on first login.
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.models import db as _db
from app.auth.permissions import permission_required

from . import auth_bp

db = _db


@auth_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings')
def create_user():
    """Admin-only: Create a new user for the current business."""
    from app.models import User

    if current_user.role != 'admin':
        flash('Only administrators can create new users.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        flash('No business associated with your account.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'viewer').strip().lower()

        if not email or not name or not password:
            flash('Email, name and password are required.', 'danger')
            return render_template('create_user.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('create_user.html')

        valid_roles = ['admin', 'manager', 'accountant', 'cashier', 'storekeeper', 'viewer']
        if role not in valid_roles:
            flash(f'Invalid role. Must be one of: {", ".join(valid_roles)}', 'danger')
            return render_template('create_user.html')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('A user with this email already exists.', 'danger')
            return render_template('create_user.html')

        user = User(
            business_id=biz_id,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            is_active=True,
            must_change_password=True,
        )
        db.session.add(user)
        db.session.commit()

        flash(f'User "{name}" ({role}) created successfully. They must change password on first login.', 'success')
        return redirect(url_for('settings.settings'))

    return render_template('create_user.html')