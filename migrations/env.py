"""
Flask-Migrate / Alembic environment configuration.
"""
import logging
import os
import sys
from alembic import context
from sqlalchemy import engine_from_config, pool
from flask import current_app

# Add the project root to sys.path so that `models` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import db  # noqa: E402


config = context.config
target_metadata = db.metadata
logger = logging.getLogger(__name__)


def get_url():
    return current_app.config.get("SQLALCHEMY_DATABASE_URI")


def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    cfg = config.get_section(config.config_ini_section)
    url = get_url()
    cfg["sqlalchemy.url"] = url

    # Use a single-connection approach for Neon serverless Postgres
    # to avoid connection pool exhaustion during migrations
    is_neon = "neon.tech" in (url or "")
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 10} if is_neon else {},
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()