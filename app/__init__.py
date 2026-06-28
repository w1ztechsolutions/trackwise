import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from models import db as _db
from config import DevelopmentConfig, ProductionConfig, TestingConfig
from .template_filters import register_template_filters

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()


def create_app(config_object=None):
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    app.config.setdefault(
        "SECRET_KEY",
        os.environ.get("SECRET_KEY", "dev-fallback-key"),
    )

    default_sqlite = "sqlite:///" + os.path.join(app.instance_path, "trackwise.db")
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("DATABASE_URL", default_sqlite),
    )

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

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

    app.register_blueprint(_auth_bp)
    app.register_blueprint(_dashboard_bp)
    app.register_blueprint(_inventory_bp)
    app.register_blueprint(_purchases_bp)
    app.register_blueprint(_sales_bp)
    app.register_blueprint(_expenses_bp)
    app.register_blueprint(_reports_bp)
    app.register_blueprint(_settings_bp)
    app.register_blueprint(_api_bp)

    app.url_map.strict_slashes = False

    @app.route('/legacy-redirect')
    def _unused_legacy():
        from flask import redirect, url_for
        return redirect(url_for('dashboard.dashboard'))

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return _db.session.get(User, int(user_id))


    return app
