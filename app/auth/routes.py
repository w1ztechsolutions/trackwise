from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

from app.models import db as _db

from . import auth_bp

db = _db


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from app.models import User

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()


        if user and user.is_active and check_password_hash(user.password_hash, password):
            from flask_login import login_user
            login_user(user)
            return redirect(url_for('dashboard.dashboard'))

        flash('Invalid credentials or inactive account.', 'danger')

    return render_template('auth.html', show_nav=False)


@auth_bp.route('/logout')
def logout():
    from flask_login import logout_user
    logout_user()
    return redirect(url_for('auth.login'))