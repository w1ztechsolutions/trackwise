import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from models import db as _db
from .template_filters import register_template_filters


def create_app(config_object=None):
    app = Flask(__name__)

    # Default config is driven by environment variables.
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

    # Allow overriding config object (e.g. for tests)
    if config_object is not None:
        app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize db
    _db.init_app(app)

    # Register Jinja filters
    register_template_filters(app)

    # Register Blueprints
    from .dashboard import dashboard_bp as _dashboard_bp
    from .inventory import inventory_bp as _inventory_bp
    from .purchases import purchases_bp as _purchases_bp
    from .sales import sales_bp as _sales_bp
    from .expenses import expenses_bp as _expenses_bp
    from .reports import reports_bp as _reports_bp
    from .settings import settings_bp as _settings_bp
    from .api import api_bp as _api_bp


    app.register_blueprint(_dashboard_bp)
    app.register_blueprint(_inventory_bp)
    app.register_blueprint(_purchases_bp)
    app.register_blueprint(_sales_bp)
    app.register_blueprint(_expenses_bp)
    app.register_blueprint(_reports_bp)
    app.register_blueprint(_settings_bp)
    app.register_blueprint(_api_bp)

    return app

