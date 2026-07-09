from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.models import db as _db

from . import auth_bp

db = _db


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Local import to avoid circular imports
    from app.models import User

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not business_name or not email or not password:
            flash('Business name, email and password are required.', 'danger')
            return render_template('register.html', show_nav=False)


        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', show_nav=False)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html', show_nav=False)

        # Multi-business: business name is currently for display/workflow only.
        # Data separation is not wired in the backend yet.
        user = User(email=email, password_hash=generate_password_hash(password), role='viewer', is_active=True)

        db.session.add(user)
        db.session.commit()

        flash('Account created successfully. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', show_nav=False)

