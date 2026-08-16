from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import db as _db
from app.auth.validators import validate_email, validate_password_strength
from app import limiter

from . import auth_bp

db = _db


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    from app.models import User

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth.html', show_nav=False)

        user = User.query.filter_by(email=email).first()

        if user and user.is_active:
            try:
                valid_password = check_password_hash(user.password_hash, password)
            except ValueError:
                valid_password = False

            if valid_password:
                from flask_login import login_user
                login_user(user)

                if user.must_change_password:
                    flash('Please change your password before continuing.', 'warning')
                    return redirect(url_for('auth.change_password'))

                return redirect(url_for('dashboard.dashboard'))

        flash('Invalid credentials or inactive account.', 'danger')

    return render_template('auth.html', show_nav=False)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    from flask_login import current_user, logout_user

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')

        valid, message = validate_password_strength(new_password)
        if not valid:
            flash(message, 'danger')
            return render_template('change_password.html')

        current_user.password_hash = generate_password_hash(new_password)
        current_user.must_change_password = False
        db.session.commit()

        flash('Password changed successfully.', 'success')
        return redirect(url_for('dashboard.dashboard'))

    return render_template('change_password.html')


@auth_bp.route('/logout')
def logout():
    from flask_login import logout_user
    logout_user()
    return redirect(url_for('auth.login'))
