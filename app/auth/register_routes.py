"""Admin-only user creation route.

Replaced the public registration flow. Now only business admins can create
new users for their business. New users are created with must_change_password=True
so they are forced to set their own password on first login.
"""

import json

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.models import db as _db
from app.models import User
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
        return redirect(url_for('auth.user_management'))

    return render_template('create_user.html')


@auth_bp.route('/users')
@login_required
def user_management():
    """Admin-only: User management dashboard with tabs."""
    if current_user.role != 'admin':
        flash('Only administrators can access user management.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    biz_id = getattr(current_user, 'business_id', None)
    if not biz_id:
        flash('No business associated with your account.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    users = User.query.filter_by(business_id=biz_id).order_by(User.role, User.email).all()
    return render_template('user_management.html', users=users)


@auth_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Admin-only: Edit user details (email, active status, must_change_password)."""
    if current_user.role != 'admin':
        flash('Only administrators can edit users.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    biz_id = getattr(current_user, 'business_id', None)
    user = db.session.get(User, user_id)
    if not user or user.business_id != biz_id:
        abort(404)

    if request.method == 'POST':
        user.email = request.form.get('email', '').strip().lower()
        user.is_active = request.form.get('is_active') == 'on'
        user.must_change_password = request.form.get('must_change_password') == 'on'

        # Check if email is taken by another user
        existing = User.query.filter(User.email == user.email, User.id != user_id).first()
        if existing:
            flash('Email is already in use by another user.', 'danger')
            return render_template('edit_user.html', user=user)

        db.session.commit()
        flash(f'User "{user.email}" updated successfully.', 'success')
        return redirect(url_for('auth.user_management'))

    return render_template('edit_user.html', user=user)


@auth_bp.route('/users/<int:user_id>/role', methods=['GET', 'POST'])
@login_required
def assign_role(user_id):
    """Admin-only: Assign or modify user role."""
    if current_user.role != 'admin':
        flash('Only administrators can assign roles.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    biz_id = getattr(current_user, 'business_id', None)
    user = db.session.get(User, user_id)
    if not user or user.business_id != biz_id:
        abort(404)

    if request.method == 'POST':
        new_role = request.form.get('role', '').strip().lower()
        valid_roles = ['admin', 'manager', 'accountant', 'cashier', 'storekeeper', 'viewer']

        if new_role not in valid_roles:
            flash(f'Invalid role. Must be one of: {", ".join(valid_roles)}', 'danger')
            return render_template('assign_role.html', user=user)

        old_role = user.role
        user.role = new_role
        db.session.commit()

        flash(f'User role changed from "{old_role}" to "{new_role}" successfully.', 'success')
        return redirect(url_for('auth.user_management'))

    return render_template('assign_role.html', user=user)


@auth_bp.route('/users/<int:user_id>/tasks', methods=['GET', 'POST'])
@login_required
def manage_user_tasks(user_id):
    """Admin-only: Assign custom tasks to a user."""
    if current_user.role != 'admin':
        flash('Only administrators can assign tasks.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    biz_id = getattr(current_user, 'business_id', None)
    user = db.session.get(User, user_id)
    if not user or user.business_id != biz_id:
        abort(404)

    available_tasks = [
        ('approve_transactions', 'Can approve transactions'),
        ('manage_settings', 'Can manage settings'),
        ('manage_inventory', 'Can manage inventory'),
        ('view_financials', 'Can view financial reports'),
    ]

    if request.method == 'POST':
        selected_tasks = request.form.getlist('tasks')
        user.custom_tasks = json.dumps(selected_tasks)
        db.session.commit()
        flash(f'Custom tasks updated for "{user.email}".', 'success')
        return redirect(url_for('auth.user_management'))

    current_tasks = []
    if user.custom_tasks:
        try:
            current_tasks = json.loads(user.custom_tasks)
        except (json.JSONDecodeError, TypeError):
            current_tasks = []

    return render_template('manage_tasks.html', user=user, available_tasks=available_tasks, current_tasks=current_tasks)
