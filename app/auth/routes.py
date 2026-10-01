from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user
from sqlalchemy.exc import IntegrityError
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
    from app.database import PRODUCTION_CONTEXT, select_database

    demo_mode_enabled = current_app.config.get('DEMO_MODE_ENABLED', False)
    demo_available = (
        demo_mode_enabled
        and current_app.extensions.get("trackwise_demo_engine") is not None
    )

    if request.method == 'POST':
        select_database(PRODUCTION_CONTEXT)
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template(
                'auth.html',
                show_nav=False,
                demo_available=demo_available,
            )

        user = User.query.filter_by(email=email).first()

        if user and user.is_active:
            try:
                valid_password = check_password_hash(user.password_hash, password)
            except ValueError:
                valid_password = False

            if valid_password:
                from app.services.email_service import email_verification_required

                if email_verification_required() and not user.email_verified:
                    from app.services.audit_service import record_user_action
                    record_user_action(
                        user.business_id,
                        user.id,
                        'LOGIN_UNVERIFIED',
                        'authentication',
                        record_id=user.id,
                    )
                    db.session.commit()
                    return render_template(
                        'verify_email_notice.html',
                        show_nav=False,
                        email=user.email,
                    ), 403

                from flask_login import login_user
                session.permanent = True
                login_user(user)
                from app.services.audit_service import record_user_action
                record_user_action(
                    user.business_id,
                    user.id,
                    'LOGIN',
                    'authentication',
                    record_id=user.id,
                )
                db.session.commit()

                if user.must_change_password:
                    flash('Please change your password before continuing.', 'warning')
                    return redirect(url_for('auth.change_password'))

                return redirect(url_for('dashboard.dashboard'))

        from app.services.audit_service import record_user_action
        record_user_action(
            user.business_id if user else None,
            user.id if user else None,
            'LOGIN_FAILED',
            'authentication',
            record_id=user.id if user else None,
            details={'email': email},
        )
        db.session.commit()
        flash('Invalid credentials or inactive account.', 'danger')

    return render_template(
        'auth.html',
        show_nav=False,
        demo_available=demo_available,
    )


def _demo_database_is_enabled():
    return (
        current_app.config.get("DEMO_MODE_ENABLED", False)
        and current_app.extensions.get("trackwise_demo_engine") is not None
    )


def _render_demo_entry(business_name="", role="viewer", status=200):
    from app.services.demo_accounts import DEMO_ROLES

    return render_template(
        "demo_entry.html",
        show_nav=False,
        business_name=business_name,
        selected_role=role,
        demo_roles=DEMO_ROLES,
    ), status


def _render_existing_demo_business(workspace, role):
    from app.models import Business
    from app.services.demo_accounts import DEMO_ROLES

    session["demo_pending_business_id"] = workspace.business_id
    session["demo_pending_role"] = role
    business = db.session.get(Business, workspace.business_id)
    return render_template(
        "demo_business_exists.html",
        show_nav=False,
        business_name=business.name if business else workspace.normalized_name,
        role_label=dict(DEMO_ROLES)[role],
    )


def _sign_in_demo_user(user, role):
    from app.services.audit_service import record_user_action

    session.permanent = True
    login_user(user, fresh=True)
    record_user_action(
        user.business_id,
        user.id,
        "DEMO_LOGIN",
        "authentication",
        record_id=user.id,
        details={"role": role},
    )
    db.session.commit()
    flash("You are in the demo workspace. Its data is shared and may be reset.", "info")
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/demo", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def demo_entry():
    if not _demo_database_is_enabled():
        abort(404)

    from app.database import DEMO_CONTEXT, select_database
    from app.services.demo_accounts import (
        DEMO_ROLES,
        create_demo_workspace,
        find_demo_workspace,
        normalize_business_name,
    )

    if request.method == "GET":
        return _render_demo_entry()

    select_database(DEMO_CONTEXT)
    session.pop("demo_pending_business_id", None)
    session.pop("demo_pending_role", None)
    business_name = request.form.get("business_name", "")
    role = request.form.get("role", "").strip().lower()

    if role not in {allowed_role for allowed_role, _ in DEMO_ROLES}:
        flash("Choose one of the available demo roles.", "danger")
        return _render_demo_entry(business_name, status=400)

    display_name, normalized_name = normalize_business_name(business_name)
    if not display_name or len(display_name) > 200:
        flash("Enter a business name between 1 and 200 characters.", "danger")
        return _render_demo_entry(business_name, role, status=400)

    workspace = find_demo_workspace(normalized_name)
    if workspace is not None:
        return _render_existing_demo_business(workspace, role)

    try:
        _, user = create_demo_workspace(display_name, normalized_name, role)
    except IntegrityError:
        db.session.rollback()
        workspace = find_demo_workspace(normalized_name)
        if workspace is None:
            raise
        return _render_existing_demo_business(workspace, role)

    return _sign_in_demo_user(user, role)


@auth_bp.route("/demo/proceed", methods=["POST"])
@limiter.limit("20 per hour")
def demo_proceed():
    if not _demo_database_is_enabled():
        abort(404)

    from app.database import DEMO_CONTEXT, select_database
    from app.models import DemoWorkspace
    from app.services.demo_accounts import DEMO_ROLES, create_demo_user

    select_database(DEMO_CONTEXT)
    business_id = session.pop("demo_pending_business_id", None)
    role = session.pop("demo_pending_role", None)
    allowed_roles = {allowed_role for allowed_role, _ in DEMO_ROLES}
    workspace = DemoWorkspace.query.filter_by(business_id=business_id).one_or_none()
    if workspace is None or role not in allowed_roles:
        flash("That demo workspace selection expired. Please enter the business name again.", "warning")
        return redirect(url_for("auth.demo_entry"))

    user = create_demo_user(workspace.business_id, role)
    db.session.commit()
    return _sign_in_demo_user(user, role)


@auth_bp.route("/demo/change-business", methods=["POST"])
@limiter.limit("20 per hour")
def demo_change_business():
    if not _demo_database_is_enabled():
        abort(404)
    session.pop("demo_pending_business_id", None)
    session.pop("demo_pending_role", None)
    return redirect(url_for("auth.demo_entry"))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    from flask_login import current_user

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
        from app.services.audit_service import record_user_action
        record_user_action(
            current_user.business_id,
            current_user.id,
            'PASSWORD_CHANGED',
            'authentication',
            record_id=current_user.id,
        )
        db.session.commit()

        flash('Password changed successfully.', 'success')
        return redirect(url_for('dashboard.dashboard'))

    return render_template('change_password.html')


@auth_bp.route('/logout')
def logout():
    from flask_login import current_user, logout_user
    from app.database import DATABASE_CONTEXT_KEY

    if current_user.is_authenticated:
        from app.services.audit_service import record_user_action
        record_user_action(
            current_user.business_id,
            current_user.id,
            'LOGOUT',
            'authentication',
            record_id=current_user.id,
        )
        db.session.commit()
    logout_user()
    session.pop(DATABASE_CONTEXT_KEY, None)
    db.session.remove()
    return redirect(url_for('auth.login'))
