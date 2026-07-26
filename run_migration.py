"""Run database migration with proper environment loading."""
import os
from dotenv import load_dotenv

# Load .env files in same order as config.py
env_files = [
    ".env",
    ".env.local",
]
for f in env_files:
    if os.path.exists(f):
        load_dotenv(f, override=True)
        print(f"Loaded env from {f}")

print(f"DATABASE_URL from env: {os.environ.get('DATABASE_URL', 'NOT SET')[:60]}")

# Now import Flask and run migration
from app import create_app
from flask_migrate import upgrade

# Force using the DATABASE_URL from .env/.env.local as-is by using ProductionConfig
# so we don't fall back to SQLite on machines without psycopg installed locally.
from config import ProductionConfig

app = create_app(config_object=ProductionConfig)

with app.app_context():
    print(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI'][:60]}...")
    print("Running migration...")
    upgrade()
    print("Migration completed successfully!")
