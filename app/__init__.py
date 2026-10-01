import secrets
import click
import importlib
import os
from flask import Flask, g, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from sqlalchemy import create_engine

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
from config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    _normalize_database_uri,
)
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


def ensure_accounting_columns():
    """Repair legacy schemas missing accounting soft-delete and fiscal-year columns."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
    except Exception:
        return

    try:
        biz_cols = {c["name"] for c in inspector.get_columns("businesses")}
        if "fiscal_year_start" not in biz_cols:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS fiscal_year_start VARCHAR(5) DEFAULT '01-01'"))
    except Exception:
        db.session.rollback()

    try:
        je_cols = {c["name"] for c in inspector.get_columns("journal_entries")}
        if "is_deleted" not in je_cols:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"))
                connection.execute(text("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS deleted_by INTEGER"))
                connection.execute(text("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"))
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

    demo_database_uri = app.config.get("DEMO_DATABASE_URL")
    normalized_demo_uri = None
    if app.config.get("DEMO_MODE_ENABLED"):
        if not demo_database_uri:
            raise RuntimeError(
                "DEMO_MODE_ENABLED requires DEMO_DATABASE_URL to point to an isolated demo database."
            )
        normalized_demo_uri = _normalize_database_uri(demo_database_uri)
        production_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        from app.database import database_identity
        if database_identity(normalized_demo_uri) == database_identity(production_uri):
            raise RuntimeError(
                "DEMO_DATABASE_URL must identify a different database endpoint and name from DATABASE_URL."
            )

    _db.init_app(app)
    if normalized_demo_uri:
        demo_options = {"pool_pre_ping": True, "pool_recycle": 120}
        if "neon.tech" in normalized_demo_uri:
            demo_options.update({
                "pool_size": 2,
                "max_overflow": 3,
                "pool_timeout": 30,
                "connect_args": {"connect_timeout": 10},
            })
        app.extensions["trackwise_demo_engine"] = create_engine(
            normalized_demo_uri,
            **demo_options,
        )
    from app.database import install_database_routing
    install_database_routing()
    # Audit listeners are bound to the session class, so they are installed after
    # install_database_routing() has settled which Session subclass this factory
    # builds. See models.AuditedSQLAlchemy for the equivalent init_app hook.
    from app.services.audit_service import install_audit_listeners
    install_audit_listeners(_db.session)
    migrate.init_app(app, _db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        ensure_required_user_columns()
        ensure_required_sales_columns()
        ensure_accounting_columns()

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
    from .accounting import accounting_bp as _accounting_bp
    from .imports import imports_bp as _imports_bp

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
    app.register_blueprint(_accounting_bp)
    app.register_blueprint(_imports_bp)

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
    def _set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def _set_business_context():
        try:
            from flask_login import current_user
            if current_user is not None and current_user.is_authenticated:
                g.business_id = getattr(current_user, 'business_id', None)
                _db.session.info['audit_actor_id'] = current_user.id
            else:
                g.business_id = None
                _db.session.info.pop('audit_actor_id', None)
        except Exception:
            _db.session.rollback()
            g.business_id = None
            _db.session.info.pop('audit_actor_id', None)

    from app.services.period_service import PeriodClosedError

    @app.errorhandler(PeriodClosedError)
    def _handle_period_close_error(error):
        return str(error), 409

    @app.teardown_request
    def _clear_audit_actor(error):
        _db.session.info.pop('audit_actor_id', None)

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
        csp_nonce = getattr(g, "csp_nonce", "")
        try:
            if request.endpoint in ("static",):
                show_nav = False
        except Exception:
            show_nav = True
        return dict(show_nav=show_nav, csp_nonce=csp_nonce)

    @app.after_request
    def set_security_headers(response):
        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://cdn.vercel-insights.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://vitals.vercel-analytics.com; form-action 'self'; frame-ancestors 'none'; object-src 'none';"
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


def create_demo_migration_app():
    """Create a CLI-only app whose primary database is the isolated demo DB."""
    demo_database_uri = DevelopmentConfig.DEMO_DATABASE_URL
    if not demo_database_uri:
        raise RuntimeError(
            "DEMO_DATABASE_URL must be configured before bootstrapping the demo database."
        )

    normalized_demo_uri = _normalize_database_uri(demo_database_uri)
    production_uri = DevelopmentConfig.SQLALCHEMY_DATABASE_URI
    from app.database import database_identity

    if database_identity(normalized_demo_uri) == database_identity(production_uri):
        raise RuntimeError(
            "Refusing demo bootstrap because DEMO_DATABASE_URL identifies the production database."
        )

    class DemoMigrationConfig:
        SQLALCHEMY_DATABASE_URI = normalized_demo_uri
        SQLALCHEMY_ENGINE_OPTIONS = DevelopmentConfig.SQLALCHEMY_ENGINE_OPTIONS
        DEMO_MODE_ENABLED = False
        DEMO_DATABASE_URL = demo_database_uri

    app = create_app(DemoMigrationConfig)

    @app.cli.command("demo-db-bootstrap")
    def demo_database_bootstrap_command():
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from flask_migrate import stamp
        from sqlalchemy import inspect, text

        if database_identity(
            _db.engine.url.render_as_string(hide_password=True)
        ) != database_identity(normalized_demo_uri):
            raise click.ClickException(
                "Refusing demo bootstrap because the active database is not DEMO_DATABASE_URL."
            )

        inspector = inspect(_db.engine)
        existing_tables = set(inspector.get_table_names())
        mapped_tables = set(_db.metadata.tables)
        unexpected_tables = existing_tables - mapped_tables - {"alembic_version"}
        if unexpected_tables:
            raise click.ClickException(
                "Refusing bootstrap because the demo database contains unmapped tables: "
                + ", ".join(sorted(unexpected_tables))
            )

        quote = _db.engine.dialect.identifier_preparer.quote
        nonempty_tables = []
        with _db.engine.connect() as connection:
            for table_name in sorted(existing_tables & mapped_tables):
                count = connection.execute(
                    text(f"SELECT count(*) FROM {quote(table_name)}")
                ).scalar_one()
                if count:
                    nonempty_tables.append(table_name)
        if nonempty_tables:
            raise click.ClickException(
                "Refusing bootstrap because demo application data already exists in: "
                + ", ".join(nonempty_tables)
            )

        migrations_dir = os.path.join(_PROJECT_ROOT, "..", "migrations")
        _db.drop_all()
        _db.create_all()
        stamp(directory=migrations_dir, revision="heads")

        with _db.engine.connect() as connection:
            current_heads = set(MigrationContext.configure(connection).get_current_heads())
            actual_tables = set(inspect(connection).get_table_names())
        expected_heads = set(ScriptDirectory(migrations_dir).get_heads())
        missing_tables = mapped_tables - actual_tables
        if current_heads != expected_heads or missing_tables:
            raise click.ClickException(
                "Demo bootstrap verification failed: "
                f"heads_match={current_heads == expected_heads}, "
                f"missing_tables={', '.join(sorted(missing_tables)) or '(none)'}."
            )

        click.echo(
            "Demo schema created from ORM metadata and stamped at Alembic head(s): "
            + ", ".join(sorted(current_heads))
        )

    return app
