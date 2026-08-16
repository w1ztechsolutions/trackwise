import click
import importlib
import os
from flask import Flask, g, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from dotenv import load_dotenv

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:  # pragma: no cover
    Limiter = None  # type: ignore[assignment]

    def get_remote_address(*args, **kwargs):
        return "127.0.0.1"

    class _LimiterFallback:
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, app):
            return None

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    Limiter = _LimiterFallback

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_TEMPLATES_DIR = os.path.join(_PROJECT_ROOT, "..", "templates")
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "..", "static")

if not os.path.exists(_TEMPLATES_DIR):
    TEMPLATE_FOLDER = "templates"
    STATIC_FOLDER = "static"
else:
    TEMPLATE_FOLDER = os.path.abspath(_TEMPLATES_DIR)
    STATIC_FOLDER = os.path.abspath(_STATIC_DIR)

for _env_path in [
    os.path.join(_PROJECT_ROOT, "..", ".env"),
    os.path.join(_PROJECT_ROOT, "..", ".env.local"),
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), ".env.local"),
]:
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)

from app.models import db as _db
from config import DevelopmentConfig, ProductionConfig, TestingConfig
from .template_filters import register_template_filters

# Shared database handle so app-level startup checks can safely inspect and repair
# legacy PostgreSQL schemas without depending on routes importing a different module.
db = _db


def _has_postgres_driver() -> bool:
    return importlib.util.find_spec("psycopg2") is not None or importlib.util.find_spec("psycopg") is not None

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)


def ensure_required_user_columns():
    """Repair legacy database schemas that are missing required `users` columns."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        return

    if not columns:
        return

    required_columns = {
        "name": "VARCHAR(120)",
        "must_change_password": "BOOLEAN NOT NULL DEFAULT FALSE",
        "custom_tasks": "TEXT",
        "role": "VARCHAR(20) NOT NULL DEFAULT 'viewer'",
        "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
    }

    for column_name, column_def in required_columns.items():
        if column_name in columns:
            continue
        try:
            with db.engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column_name} {column_def}"))
        except Exception:
            db.session.rollback()


def ensure_required_sales_columns():
    """Repair legacy PostgreSQL schemas that are missing the optional sales invoice linkage."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        if not inspector.has_table("sales"):
            return
        columns = {column["name"] for column in inspector.get_columns("sales")}
    except Exception:
        return

    if "invoice_id" in columns:
        return

    try:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS invoice_id INTEGER"))
            connection.execute(text("ALTER TABLE sales ADD CONSTRAINT IF NOT EXISTS fk_sales_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id)"))
    except Exception:
        db.session.rollback()


def create_app(config_object=None):
    app = Flask(
        __name__,
        static_folder=STATIC_FOLDER,
        template_folder=TEMPLATE_FOLDER
    )

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    if os.environ.get("INSTANCE_PATH"):
        app.instance_path = os.environ.get("INSTANCE_PATH")

    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        base = ProductionConfig
    elif env == "testing":
        base = TestingConfig
    else:
        base = DevelopmentConfig

    app.config.from_object(base)

    if config_object is not None:
        app.config.from_object(config_object)

    if "SQLALCHEMY_DATABASE_URI" not in app.config or not app.config["SQLALCHEMY_DATABASE_URI"]:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "trackwise.db")

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgresql") and not _has_postgres_driver():
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "trackwise.db")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    _db.init_app(app)
    migrate.init_app(app, _db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        ensure_required_user_columns()
        ensure_required_sales_columns()

    register_template_filters(app)

    from .dashboard import dashboard_bp as _dashboard_bp
    from .inventory import inventory_bp as _inventory_bp
    from .purchases import purchases_bp as _purchases_bp
    from .sales import sales_bp as _sales_bp
    from .expenses import expenses_bp as _expenses_bp
    from .reports import reports_bp as _reports_bp
    from .settings import settings_bp as _settings_bp
    from .api import api_bp as _api_bp
    from .auth import auth_bp as _auth_bp
    from .production import production_bp as _production_bp
    from .superadmin import superadmin_bp as _superadmin_bp
    from .approvals import approvals_bp as _approvals_bp

    app.register_blueprint(_auth_bp)
    app.register_blueprint(_dashboard_bp)
    app.register_blueprint(_inventory_bp)
    app.register_blueprint(_purchases_bp)
    app.register_blueprint(_sales_bp)
    app.register_blueprint(_expenses_bp)
    app.register_blueprint(_reports_bp)
    app.register_blueprint(_settings_bp)
    app.register_blueprint(_api_bp)
    app.register_blueprint(_production_bp)
    app.register_blueprint(_superadmin_bp)
    app.register_blueprint(_approvals_bp)

    app.url_map.strict_slashes = False

    @app.route('/health')
    def health_check():
        from flask import jsonify
        import time

        health_status = {
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': time.time(),
        }

        try:
            _db.session.execute(_db.text('SELECT 1'))
            health_status['database'] = 'connected'
        except Exception as e:
            _db.session.rollback()
            health_status['database'] = 'disconnected'
            health_status['status'] = 'degraded'
            health_status['database_error'] = str(e)

        return jsonify(health_status)

    @app.route('/legacy-redirect')
    def _unused_legacy():
        from flask import redirect, url_for
        return redirect(url_for('dashboard.dashboard'))

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return _db.session.get(User, int(user_id))

    @app.before_request
    def _set_business_context():
        try:
            from flask_login import current_user
            if current_user is not None and current_user.is_authenticated:
                g.business_id = getattr(current_user, 'business_id', None)
            else:
                g.business_id = None
        except Exception:
            _db.session.rollback()
            g.business_id = None

    @app.before_request
    def _enforce_https():
        if app.testing or os.environ.get('FLASK_ENV') == 'development':
            return
        if request.path.startswith('/static') or request.path == '/health':
            return
        if request.headers.get('X-Forwarded-Proto', 'http') == 'https':
            return
        if request.is_secure:
            return
        return redirect(request.url.replace('http://', 'https://', 1), code=301)

    @app.context_processor
    def _inject_nav():
        show_nav = True
        try:
            if request.endpoint in ("static",):
                show_nav = False
        except Exception:
            show_nav = True
        return dict(show_nav=show_nav)

    @app.after_request
    def set_security_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' https://cdn.vercel-insights.com; style-src 'self' https://fonts.googleapis.com 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://vitals.vercel-analytics.com; form-action 'self'; frame-ancestors 'none';"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.cli.command("create-superadmin")
    @click.argument("email")
    @click.argument("name")
    @click.argument("password")
    def create_superadmin_command(email, name, password):
        from app.models import SuperAdmin

        existing = SuperAdmin.query.filter_by(email=email).first()
        if existing:
            click.echo(f"SuperAdmin with email '{email}' already exists.")
            return

        sa = SuperAdmin(email=email, name=name)
        sa.set_password(password)
        _db.session.add(sa)
        _db.session.commit()
        click.echo(f"SuperAdmin created: {email} ({name})")

    @app.teardown_appcontext
    def _teardown_db(error):
        if error:
            _db.session.rollback()
        _db.session.remove()

    return app
