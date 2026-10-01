"""Email verification flow: signup verification, login rejection, confirm/resend."""

from app.services.email_service import (
    confirm_verification_token,
    create_verification_token,
    email_verification_required,
)


def _make_verified_app(app, monkeypatch=None):
    """Force verification on for the duration of a test."""
    app.config["EMAIL_VERIFICATION_FORCED"] = True
    return app


def _create_unverified_user(app, email="new@example.com"):
    from models import db, User
    from werkzeug.security import generate_password_hash

    user = User(
        business_id=app.test_client_business.id,
        email=email,
        password_hash=generate_password_hash("S3cure-pass!"),
        role="viewer",
        is_active=True,
        email_verified=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_verification_not_required_without_smtp(app):
    assert email_verification_required() is False


def test_verification_required_when_forced(app):
    _make_verified_app(app)
    assert email_verification_required() is True


def test_unverified_login_rejected_with_notice(app):
    from models import User
    from app.auth.validators import validate_password_strength

    _make_verified_app(app)
    user = _create_unverified_user(app)
    assert user.email_verified is False

    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "new@example.com", "password": "S3cure-pass!"},
    )
    assert response.status_code == 403
    assert b"Verify your email" in response.data
    # The user was not logged in.
    with client.session_transaction() as sess:
        assert "_user_id" not in sess


def test_verified_login_succeeds(app):
    from models import db, User

    _make_verified_app(app)
    user = _create_unverified_user(app, email="verified@example.com")
    user.email_verified = True
    db.session.commit()

    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "verified@example.com", "password": "S3cure-pass!"},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_confirm_token_verifies_once(app):
    _make_verified_app(app)
    user = _create_unverified_user(app, email="token@example.com")

    token = create_verification_token(user)

    confirmed, error = confirm_verification_token(token)
    assert confirmed is not None and error is None
    assert user.email_verified is True

    # Single-use: the same link answers "already verified" and changes nothing.
    confirmed, error = confirm_verification_token(token)
    assert error == "already_verified"

    # A token minted for a different account is rejected.
    other = _create_unverified_user(app, email="other@example.com")
    confirmed, error = confirm_verification_token(token)
    assert confirmed is None
    assert other.email_verified is False


def test_resend_verification_is_generic(app):
    _make_verified_app(app)
    _create_unverified_user(app, email="resend@example.com")

    client = app.test_client()
    response = client.post(
        "/verify-email/resend",
        data={"email": "resend@example.com"},
    )
    assert response.status_code == 302
    assert b"If that account still needs verification" in response.data
