"""Email delivery and the signup email-verification flow.

Verification uses a single-use, time-limited signed token (``itsdangerous``).
The token binds the user id and email address, so a link stops working the
moment the address is edited, and it is consumed implicitly once the account is
marked verified — a replayed link answers "already verified" rather than
re-verifying anyone.

SMTP credentials come exclusively from the environment (``SMTP_HOST``,
``SMTP_PORT``, ``SMTP_USER``, ``SMTP_PASSWORD``, ``SMTP_FROM``); nothing is
hardcoded. Verification is enforced only when SMTP is configured (or
``EMAIL_VERIFICATION_REQUIRED=1`` is set explicitly), so a database without
SMTP credentials — like the demo database — never locks its users out.
"""

import logging
import smtplib
from email.message import EmailMessage

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger(__name__)

EMAIL_TOKEN_SALT = "trackwise-email-verification"


def email_verification_required():
    """True when the deployment actually sends email, or when forced by env."""
    from flask import current_app

    if current_app.config.get("EMAIL_VERIFICATION_FORCED"):
        return True
    return bool(current_app.config.get("SMTP_HOST"))


def _serializer():
    from flask import current_app

    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=EMAIL_TOKEN_SALT)


def create_verification_token(user):
    return _serializer().dumps({"uid": user.id, "email": user.email})


def confirm_verification_token(token, max_age=None):
    """Return ``(user, error)``; ``user`` is None when the link is unusable."""
    from flask import current_app
    from app.models import db, User

    if max_age is None:
        max_age = current_app.config["EMAIL_TOKEN_MAX_AGE"]
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        return None, "This verification link has expired. Please request a new one."
    except BadSignature:
        return None, "This verification link is invalid or has already been used."

    user = db.session.get(User, payload.get("uid"))
    if user is None or user.email != payload.get("email"):
        return None, "This verification link is invalid for this account."

    if user.email_verified:
        return user, "already_verified"
    user.email_verified = True
    db.session.commit()
    return user, None


def verification_url(token):
    from flask import current_app, url_for

    base_url = current_app.config.get("BASE_URL") or request_root_url()
    return f"{base_url}{url_for('auth.verify_email', token=token)}"


def request_root_url():
    from flask import request

    return request.url_root.rstrip("/")


def send_email(to, subject, body):
    """Send one plain-text email via standard SMTP. Returns True when sent.

    Without SMTP configuration the message is logged instead so development and
    demo environments keep working end to end.
    """
    from flask import current_app

    host = current_app.config.get("SMTP_HOST")
    if not host:
        logger.warning("SMTP not configured; email to %s logged instead:\n%s\n%s", to, subject, body)
        return False

    port = int(current_app.config.get("SMTP_PORT") or 587)
    message = EmailMessage()
    message["From"] = current_app.config.get("SMTP_FROM") or "no-reply@trackwise.local"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    use_ssl = port == 465
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if not use_ssl:
            smtp.starttls()
        user = current_app.config.get("SMTP_USER")
        password = current_app.config.get("SMTP_PASSWORD")
        if user and password:
            smtp.login(user, password)
        smtp.send_message(message)
    return True


def send_verification_email(user):
    token = create_verification_token(user)
    url = verification_url(token)
    sent = send_email(
        user.email,
        "Verify your TrackWise account",
        (
            f"Hello {user.name or user.email},\n\n"
            "Please confirm your email address to activate your TrackWise account:\n"
            f"{url}\n\n"
            "This link is single-use and expires in 24 hours. "
            "If you did not expect it, you can ignore this email."
        ),
    )
    return sent, url
