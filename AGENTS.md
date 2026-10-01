# Base44 Dev Environment

## Running the app

```bash
docker compose -f docker-compose.base44.yml up -d
```

App is served on host port 3000 (maps to container port 5000).
Health check: `GET /health` returns JSON with database status.

## Architecture

- **Framework:** Flask 3.x with application factory (`app/__init__.py:create_app`)
- **Database:** SQLite at `instance/trackwise.db` (development mode default; no DATABASE_URL needed)
- **Migrations:** Alembic/Flask-Migrate, but the migration chain has branch conflicts that cause `flask db upgrade` to fail on a fresh SQLite DB. The compose startup uses `db.create_all()` + `flask_migrate.stamp(revision='heads')` instead — same approach the project uses for its demo database bootstrap.
- **Redis/Celery:** Disabled (`CELERY_DISABLED=true`); Flask-Limiter falls back to in-memory storage.
- **Stripe:** Optional. App runs without Stripe keys; only needed for paid subscription plans.
- **WeasyPrint:** System libraries (pango, cairo, gdk-pixbuf) installed in Dockerfile.base44 for PDF generation.

## Key files

- `Dockerfile.base44` — runtime image with system deps + pip install
- `docker-compose.base44.yml` — dev compose (bind-mounts source, runs `flask run`)
- `.base44/environment.json` — machine metadata
- `config.py` — Flask config (dev defaults to SQLite, prod requires DATABASE_URL)
- `app/__init__.py` — application factory, blueprint registration, schema repair hooks
- `models.py` (root) — legacy models used by Alembic env.py
- `app/models/` — current models package used by the app

## First-time setup

The compose startup command automatically:
1. Creates all database tables from ORM models (`db.create_all()`)
2. Stamps Alembic to head (`stamp(revision='heads')`)
3. Seeds default subscription plans (`seed_default_plans()`)

To create a user: navigate to `/register` and enter business name, email, and password.

## Secrets

- `SECRET_KEY` — required at boot; a development placeholder is generated automatically.
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` — optional, for subscription payments.

## Notes

- The repo has its own `AGENT.md` with documentation enforcement rules (bug fixes → docs, features → CHANGELOG, etc.). These apply to code changes, not to dev environment setup.
- `app.py` is the legacy entrypoint; `flask run` auto-detects it via the `app = create_app()` module-level variable.
- The dev server does NOT have live reload enabled (Flask's built-in reloader is off in this config). After code changes, run `reload_preview` or restart the container.
