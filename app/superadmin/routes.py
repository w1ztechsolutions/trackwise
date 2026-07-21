"""SuperAdmin routes for platform-level management of businesses and their admins."""

from datetime import datetime, timezone
from functools import wraps

from flask import (
    abort, flash, redirect, render_template, request, session, url_for,
)
from werkzeug.security import generate_password_hash

from app.models import db, SuperAdmin, Business, User
from . import superadmin_bp


def superadmin_required(f):
    """Decorator that checks if the current session has a logged-in super admin."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'superadmin_id' not in session:
            flash('Please log in as Super Admin first.', 'warning')
            return redirect(url_for('superadmin.login'))
        sa = db.session.get(SuperAdmin, session['superadmin_id'])
        if not sa:
            session.pop('superadmin_id', None)
            flash('Super Admin session invalid.', 'warning')
            return redirect(url_for('superadmin.login'))
        return f(*args, **kwargs)
    return wrapped


def _get_superadmin():
    """Get the currently logged-in super admin from session."""
    sa_id = session.get('superadmin_id')
    if sa_id is None:
        return None
    return db.session.get(SuperAdmin, sa_id)


@superadmin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Super Admin login page — separate from regular user login."""
    # If already logged in, redirect to dashboard
    if 'superadmin_id' in session:
        return redirect(url_for('superadmin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        sa = SuperAdmin.query.filter_by(email=email).first()
        if sa and sa.check_password(password):
            session['superadmin_id'] = sa.id
            session.permanent = True
            flash(f'Welcome back, {sa.name}!', 'success')
            return redirect(url_for('superadmin.dashboard'))

        flash('Invalid super admin credentials.', 'danger')

    return render_template('sa_login.html')


@superadmin_bp.route('/logout')
def logout():
    """Super Admin logout."""
    session.pop('superadmin_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('superadmin.login'))


@superadmin_bp.route('/dashboard')
@superadmin_required
def dashboard():
    """Super Admin dashboard showing platform statistics."""
    sa = _get_superadmin()
    total_businesses = Business.query.count()
    total_admins = User.query.filter_by(role='admin').count()
    total_users = User.query.count()

    businesses = Business.query.order_by(Business.created_at.desc()).all()

    business_stats = []
    for biz in businesses:
        admin_count = User.query.filter_by(business_id=biz.id, role='admin').count()
        user_count = User.query.filter_by(business_id=biz.id).count()
        business_stats.append({
            'business': biz,
            'admin_count': admin_count,
            'user_count': user_count,
        })

    return render_template(
        'sa_dashboard.html',
        sa=sa,
        total_businesses=total_businesses,
        total_admins=total_admins,
        total_users=total_users,
        business_stats=business_stats,
    )


@superadmin_bp.route('/businesses')
@superadmin_required
def list_businesses():
    """List all businesses."""
    sa = _get_superadmin()
    businesses = Business.query.order_by(Business.created_at.desc()).all()
    return render_template('sa_businesses.html', sa=sa, businesses=businesses)


@superadmin_bp.route('/businesses/create', methods=['GET', 'POST'])
@superadmin_required
def create_business():
    """Create a new business."""
    sa = _get_superadmin()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        tax_id = request.form.get('tax_id', '').strip() or None
        currency = request.form.get('currency', 'MWK').strip().upper()

        if not name:
            flash('Business name is required.', 'danger')
            return render_template('sa_business_form.html', sa=sa, business=None)

        business = Business(
            name=name,
            tax_id=tax_id,
            currency=currency,
            created_by_superadmin_id=sa.id,
        )
        db.session.add(business)
        db.session.commit()

        flash(f'Business "{name}" created successfully.', 'success')
        return redirect(url_for('superadmin.dashboard'))

    return render_template('sa_business_form.html', sa=sa, business=None)


@superadmin_bp.route('/businesses/<int:biz_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def edit_business(biz_id):
    """Edit an existing business."""
    sa = _get_superadmin()
    business = db.session.get(Business, biz_id)
    if not business:
        abort(404)

    if request.method == 'POST':
        business.name = request.form.get('name', '').strip()
        business.tax_id = request.form.get('tax_id', '').strip() or None
        business.currency = request.form.get('currency', 'MWK').strip().upper()
        db.session.commit()

        flash(f'Business "{business.name}" updated.', 'success')
        return redirect(url_for('superadmin.dashboard'))

    return render_template('sa_business_form.html', sa=sa, business=business)


@superadmin_bp.route('/businesses/<int:biz_id>/delete', methods=['POST'])
@superadmin_required
def delete_business(biz_id):
    """Delete a business and all its associated data."""
    business = db.session.get(Business, biz_id)
    if not business:
        abort(404)

    name = business.name
    db.session.delete(business)
    db.session.commit()

    flash(f'Business "{name}" and all its data deleted.', 'success')
    return redirect(url_for('superadmin.dashboard'))


@superadmin_bp.route('/businesses/<int:biz_id>/admins')
@superadmin_required
def list_admins(biz_id):
    """List all admin users for a specific business."""
    sa = _get_superadmin()
    business = db.session.get(Business, biz_id)
    if not business:
        abort(404)

    admins = User.query.filter_by(business_id=biz_id, role='admin').all()
    return render_template('sa_admins.html', sa=sa, business=business, admins=admins)


@superadmin_bp.route('/businesses/<int:biz_id>/admins/create', methods=['GET', 'POST'])
@superadmin_required
def create_admin(biz_id):
    """Create an admin user for a specific business."""
    sa = _get_superadmin()
    business = db.session.get(Business, biz_id)
    if not business:
        abort(404)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not name or not password:
            flash('Email, name and password are required.', 'danger')
            return render_template('sa_admin_form.html', sa=sa, business=business, admin=None)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('sa_admin_form.html', sa=sa, business=business, admin=None)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('A user with this email already exists.', 'danger')
            return render_template('sa_admin_form.html', sa=sa, business=business, admin=None)

        admin = User(
            business_id=biz_id,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            is_active=True,
            must_change_password=True,
        )
        db.session.add(admin)
        db.session.commit()

        flash(f'Admin "{name}" created for {business.name}. They must change password on first login.', 'success')
        return redirect(url_for('superadmin.list_admins', biz_id=biz_id))

    return render_template('sa_admin_form.html', sa=sa, business=business, admin=None)


@superadmin_bp.route('/businesses/<int:biz_id>/admins/<int:admin_id>/delete', methods=['POST'])
@superadmin_required
def delete_admin(biz_id, admin_id):
    """Delete an admin user."""
    admin = db.session.get(User, admin_id)
    if not admin or admin.business_id != biz_id:
        abort(404)

    db.session.delete(admin)
    db.session.commit()

    flash(f'Admin "{admin.email}" deleted.', 'success')
    return redirect(url_for('superadmin.list_admins', biz_id=biz_id))


@superadmin_bp.route('/users')
@superadmin_required
def list_all_users():
    """List all users across all businesses."""
    sa = _get_superadmin()
    users = User.query.order_by(User.business_id, User.role).all()
    businesses = {b.id: b for b in Business.query.all()}
    return render_template('sa_users.html', sa=sa, users=users, businesses=businesses)