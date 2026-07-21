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


def _strip_neon_incompatible_params(uri: str) -> str:
    """Remove parameters not supported by psycopg 3.x from the connection URI.

    - channel_binding is a libpq parameter, not recognised by psycopg 3.x
    """
    if "?" not in uri:
        return uri
    base, query = uri.split("?", 1)
    params = query.split("&")
    allowed = [p for p in params if not p.startswith("channel_binding=")]
    if allowed:
        return base + "?" + "&".join(allowed)
    return base


def _normalize_database_uri(raw_uri: str) -> str:
    if raw_uri.startswith("postgresql://"):
        uri = raw_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        uri = _strip_neon_incompatible_params(uri)
        return uri
    return raw_uri


def _is_neon(uri: str | None) -> bool:
    return uri is not None and "neon.tech" in uri


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


def _get_pool_options(is_neon: bool = False) -> dict:
    """Return SQLAlchemy engine pool options tuned for the target database.

    Neon (serverless Postgres) has lower connection limits and tighter
    idle timeouts than a dedicated Postgres instance.
    """
    if is_neon:
        return {
            "pool_pre_ping": True,
            "pool_recycle": 120,       # 2 min – well under Neon's 5 min idle timeout
            "pool_size": 2,            # Neon free tier ~10 conn limit
            "max_overflow": 3,         # burst = 5 total
            "pool_timeout": 30,
        }
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
    }


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
    REMEMBER_COOKIE_DURATION = timedelta(days=14)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _get_pool_options(is_neon=_is_neon(os.environ.get("DATABASE_URL")))


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    # Use a fixed deterministic key for tests
    SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key-for-testing-only")
    # Always use SQLite in-memory for tests to ensure isolation
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}  # disable pooling for in-memory SQLite tests
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _get_pool_options(is_neon=_is_neon(os.environ.get("DATABASE_URL")))

    def __init__(self):
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate a strong random key (e.g. via 'python -c \"import secrets; print(secrets.token_hex(32))\"') "
                "and set it as the SECRET_KEY environment variable."
            )
