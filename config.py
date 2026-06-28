"""TrackWise application configuration."""

import os
from datetime import timedelta


def _sqlite_instance_uri(app_instance_path: str) -> str:
    return "sqlite:///" + os.path.join(app_instance_path, "trackwise.db")


def _default_postgres_uri() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://trackwise:trackwise@localhost:5432/trackwise",
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
    }
    REMEMBER_COOKIE_DURATION = timedelta(days=14)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        _sqlite_instance_uri(os.path.join(os.getcwd(), "instance")),
    )


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _default_postgres_uri()
