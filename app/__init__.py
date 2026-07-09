import importlib
import os
from flask import Flask, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Determine templates and static directories for both local and Vercel environments
_TEMPLATES_DIR = os.path.join(_PROJECT_ROOT, "..", "templates")
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "..", "static")

# Ensure paths are absolute for Vercel compatibility
if not os.path.exists(_TEMPLATES_DIR):
    # Fallback to relative paths (local development)
    TEMPLATE_FOLDER = "templates"
    STATIC_FOLDER = "static"
else:
    TEMPLATE_FOLDER = os.path.abspath(_TEMPLATES_DIR)
    STATIC_FOLDER = os.path.abspath(_STATIC_DIR)

for _env_path in (os.path.join(os.getcwd(), ".env"), os.path.join(_PROJECT_ROOT, "..", ".env")):
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=False)
        break

from app.models import db as _db
from config import DevelopmentConfig, ProductionConfig, TestingConfig
from .template_filters import register_template_filters


def _has_postgres_driver() -> bool:
    return importlib.util.find_spec("psycopg2") is not None or importlib.util.find_spec("psycopg") is not None

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()


def create_app(config_object=None):
    app = Flask(
        __name__,
        static_folder=STATIC_FOLDER,
        template_folder=TEMPLATE_FOLDER
    )

    app.config.setdefault(
        "SECRET_KEY",
        os.environ.get("SECRET_KEY", "dev-fallback-key"),
    )

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # Determine which config class to use
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        base = ProductionConfig
    elif env == "testing":
        base = TestingConfig
    else:
        base = DevelopmentConfig

    # Apply config class (sets SQLALCHEMY_DATABASE_URI, ENGINE_OPTIONS, etc.)
    app.config.from_object(base)

    # Allow explicit override (e.g. from tests)
    if config_object is not None:
        app.config.from_object(config_object)

    # Fallback: if no DATABASE_URL in env and no config_object provided,
    # ensure we have at least a SQLite URI
    if "SQLALCHEMY_DATABASE_URI" not in app.config or not app.config["SQLALCHEMY_DATABASE_URI"]:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "trackwise.db")

    # If Postgres driver is missing, fall back to SQLite
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgresql") and not _has_postgres_driver():
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "trackwise.db")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    os.makedirs(app.instance_path, exist_ok=True)

    _db.init_app(app)
    migrate.init_app(app, _db)
    login_manager.init_app(app)
    csrf.init_app(app)

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

    app.url_map.strict_slashes = False

    @app.route('/health')
    def health_check():
        """Health check endpoint for container orchestration."""
        from flask import jsonify
        import time

        health_status = {
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': time.time(),
        }

        # Check database connectivity
        try:
            _db.session.execute(_db.text('SELECT 1'))
            health_status['database'] = 'connected'
        except Exception as e:
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
        """Set g.business_id from the current user for multi-tenant scoping."""
        try:
            from flask_login import current_user
            if current_user is not None and current_user.is_authenticated:
                g.business_id = getattr(current_user, 'business_id', None)
            else:
                g.business_id = None
        except Exception:
            g.business_id = None

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
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none';"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app