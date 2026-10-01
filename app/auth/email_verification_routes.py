"""Email verification confirm/resend routes."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import limiter
from app.models import db as _db

from . import auth_bp

db = _db


@auth_bp.route('/verify-email')
def verify_email():
    from app.services.email_service import confirm_verification_token

    token = request.args.get('token', '')
    if not token:
        flash('No verification token provided.', 'danger')
        return redirect(url_for('auth.login'))

    user, error = confirm_verification_token(token)
    if error == 'already_verified':
        flash('Your email is already verified. You can sign in.', 'info')
    elif error:
        flash(error, 'danger')
    else:
        flash('Email verified successfully. You can now sign in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/verify-email/resend', methods=['POST'])
@limiter.limit("5 per hour")
def resend_verification():
    from app.models import User
    from app.services.email_service import send_verification_email

    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first() if email else None

    if user is not None and not user.email_verified:
        send_verification_email(user)

    # Deliberately generic: never reveal whether an email exists or was sent.
    flash('If that account still needs verification, a new link has been sent.', 'info')
    return redirect(url_for('auth.login'))
