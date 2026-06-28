import os
from pathlib import Path

ROOT = Path("c:/Users/wisdo/Desktop/projects/trackwise")

# 1) config.py
config_py = '''\
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


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _default_postgres_uri()
'''
(ROOT / "config.py").write_text(config_py, encoding="utf-8")
print("wrote config.py")

# 2) requirements.txt additions, without disturbing order much
req_path = ROOT / "requirements.txt"
text = req_path.read_text(encoding="utf-8")
lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]
# normalize duplicates
norm = []
seen = set()
for ln in lines:
    key = ln.strip().lower()
    if key not in seen:
        seen.add(key)
        norm.append(ln.strip())

additions = ["flask-migrate", "psycopg[binary]"]
for item in additions:
    if item.lower() not in seen:
        norm.append(item)
        seen.add(item.lower())

req_path.write_text("\n".join(norm) + "\n", encoding="utf-8")
print("updated requirements.txt")
print("\n".join(norm))
