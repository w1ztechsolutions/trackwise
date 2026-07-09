"""
Database schema verification script.
Checks if the Neon PostgreSQL database has the latest schema (Phase 7 SaaS tables) applied.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from sqlalchemy import inspect, text


def verify_database_schema():
    """Verify the database schema against expected tables from latest migration."""
    app = create_app()
    
    with app.app_context():
        # Get database URI (masked for security)
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f"Database Engine: {db.engine.dialect.name}")
        print(f"Database URI: {db_uri[:50]}..." if db_uri else "No database URI configured")
        print("-" * 60)
        
        # Get inspector for table introspection
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        print(f"Found {len(existing_tables)} tables in database:")
        for t in sorted(existing_tables):
            print(f"  - {t}")
        print("-" * 60)
        
        # Check for Phase 7 SaaS tables (plans, subscriptions)
        saas_tables = ['plans', 'subscriptions']
        print("Phase 7 SaaS tables check:")
        for t in saas_tables:
            exists = t in existing_tables
            status = "[OK] EXISTS" if exists else "[MISSING]"
            print(f"  {t}: {status}")
        print("-" * 60)
        
        # Check alembic_version table for current migration revision
        print("Alembic migration status:")
        try:
            if 'alembic_version' in existing_tables:
                # Get column names to find the version column
                columns = inspector.get_columns('alembic_version')
                col_names = [c['name'] for c in columns]
                print(f"  alembic_version columns: {col_names}")
                # Usually the column is just named 'version' in standard alembic
                if 'version' in col_names:
                    result = db.session.execute(text("SELECT version FROM alembic_version")).scalar()
                    print(f"  Current revision: {result}")
                else:
                    # Get all data from the table
                    result = db.session.execute(text("SELECT * FROM alembic_version")).fetchone()
                    print(f"  Current revision data: {result}")
            else:
                print("  No alembic_version table found (database may be pre-migration)")
        except Exception as e:
            print(f"  Error checking alembic version: {e}")
        finally:
            db.session.rollback()  # Reset any transaction state
        print("-" * 60)
        
        # Count records in key tables
        print("Record counts (sample data check):")
        for t in ['businesses', 'users', 'products', 'sales', 'purchases', 
                  'journal_entries', 'chart_of_accounts', 'plans', 'subscriptions']:
            if t in existing_tables:
                try:
                    count = db.session.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                    print(f"  {t}: {count} records")
                    db.session.commit()  # Commit after each query for Postgres
                except Exception as e:
                    print(f"  {t}: Error - {e}")
                    db.session.rollback()
            else:
                print(f"  {t}: Table not found")
        print("-" * 60)
        
        # Determine if database is "updated" (has latest schema)
        has_latest_schema = all(t in existing_tables for t in saas_tables)
        
        if has_latest_schema:
            print("[OK] DATABASE STATUS: UPDATED (has Phase 7 SaaS schema)")
        else:
            print("[X] DATABASE STATUS: PREVIOUS (missing Phase 7 SaaS schema)")
        
        return has_latest_schema


if __name__ == '__main__':
    verify_database_schema()