import os
import sys

from flask import Flask


def main() -> None:
    # Ensure repo root is on path
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from app import create_app
    from flask_migrate import Migrate
    from alembic.config import Config
    from alembic import command

    # Create app so SQLALCHEMY_DATABASE_URI is available
    app = create_app()

    # Flask-Migrate sets up alembic, but we trigger upgrade via Alembic config
    # Read alembic.ini if present; otherwise fall back to using migrations env.py.
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.dirname(here)
    alembic_ini = os.path.join(repo_root, "alembic.ini")

    cfg = Config(alembic_ini if os.path.exists(alembic_ini) else None)

    # Alembic needs script_location; env.py already uses Flask current_app config.
    # We set script_location explicitly to avoid CLI issues.
    cfg.set_main_option("script_location", os.path.join(repo_root, "migrations"))

    with app.app_context():
        # Alembic will call migrations/env.py which reads SQLALCHEMY_DATABASE_URI from current_app
        command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()

