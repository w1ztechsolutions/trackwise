"""TrackWise application configuration."""

import importlib.util
import os
from datetime import timedelta

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Load .env files in order of precedence (later files override earlier ones)
for _env_path in [
    os.path.join(_PROJECT_ROOT, ".env"),
    os.path.join(_PROJECT_ROOT, ".env.local"),
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), ".env.local"),
]:
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)


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
    DEMO_MODE_ENABLED = os.environ.get("DEMO_MODE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    DEMO_DATABASE_URL = os.environ.get("DEMO_DATABASE_URL")
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=5)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SUPERADMIN_SESSION_LIFETIME = timedelta(hours=1)

    # Uploads: reject oversized requests before buffering (413).
    MAX_CONTENT_LENGTH = int(os.environ.get("UPLOAD_MAX_BYTES", 10 * 1024 * 1024))

    # Email verification (standard SMTP; credentials come from the environment).
    SMTP_HOST = os.environ.get("SMTP_HOST") or None
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER") or None
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or None
    SMTP_FROM = os.environ.get("SMTP_FROM") or None
    BASE_URL = os.environ.get("BASE_URL") or None
    EMAIL_VERIFICATION_FORCED = os.environ.get("EMAIL_VERIFICATION_REQUIRED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    EMAIL_TOKEN_MAX_AGE = int(os.environ.get("EMAIL_TOKEN_MAX_AGE", 24 * 60 * 60))

    # Stripe webhook signing secret (webhook deliveries are rejected without it).
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET") or None


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _get_pool_options(is_neon=_is_neon(os.environ.get("DATABASE_URL")))
    SESSION_COOKIE_SECURE = False


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
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _get_pool_options(is_neon=_is_neon(os.environ.get("DATABASE_URL")))
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        if not self.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate a strong random key (e.g. via 'python -c \"import secrets; print(secrets.token_hex(32))\"') "
                "and set it as the SECRET_KEY environment variable."
            )
