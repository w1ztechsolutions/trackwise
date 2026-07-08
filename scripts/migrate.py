"""
Database migration script for TrackWise.

For a fresh Neon Postgres database, this script:
1. Creates all tables from the current SQLAlchemy models (db.create_all())
2. Stamps the alembic migration chain as up-to-date so future flask db migrate
   commands will work correctly.

For existing databases, use `flask db upgrade` normally.
"""

import os
import sys


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from app import create_app
    from flask_migrate import Migrate, stamp
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect, text

    app = create_app()

    here = os.path.abspath(os.path.dirname(__file__))
    alembic_ini = os.path.join(repo_root, "alembic.ini")
    cfg = Config(alembic_ini if os.path.exists(alembic_ini) else None)
    cfg.set_main_option("script_location", os.path.join(repo_root, "migrations"))

    with app.app_context():
        from models import db
        from app.models import db as app_db

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        app_tables = [t for t in existing_tables if t != "alembic_version"]

        if not app_tables:
            # Fresh database: create all tables from models and stamp as migrated
            print("No application tables found. Creating all tables from models...")
            db.create_all()
            print("Tables created successfully.")

            # Stamp the latest migration revision
            stamp(revision="head")
            print("Alembic migration chain stamped as up-to-date.")
        else:
            # Existing database: run Alembic migrations normally
            print(
                f"Found {len(app_tables)} existing tables. Running Alembic migrations..."
            )
            command.upgrade(cfg, "head")
            print("Migrations completed successfully.")


if __name__ == "__main__":
    main()