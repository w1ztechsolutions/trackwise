"""TrackWise application configuration."""

import importlib.util
import os
from datetime import timedelta

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

for _env_path in (os.path.join(os.getcwd(), ".env"), os.path.join(_PROJECT_ROOT, ".env")):
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=False)
        break


def _sqlite_instance_uri(app_instance_path: str) -> str:
    return "sqlite:///" + os.path.join(app_instance_path, "trackwise.db")


def _has_postgres_driver() -> bool:
    return importlib.util.find_spec("psycopg2") is not None or importlib.util.find_spec("psycopg") is not None


def _normalize_database_uri(raw_uri: str) -> str:
    if raw_uri.startswith("postgresql://"):
        return raw_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_uri


def _default_database_uri() -> str:
    if os.environ.get("DATABASE_URL"):
        return _normalize_database_uri(os.environ["DATABASE_URL"])

    if os.environ.get("FLASK_ENV") == "production":
        if _has_postgres_driver():
            raise RuntimeError(
                "Production FLASK_ENV requires DATABASE_URL to be set. "
                "Hardcoded credentials are not supported."
            )
        raise RuntimeError(
            "Production FLASK_ENV requires DATABASE_URL and psycopg/psycopg2 to be installed."
        )

    return _sqlite_instance_uri(os.path.join(os.getcwd(), "instance"))


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
    SQLALCHEMY_DATABASE_URI = _default_database_uri()


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
