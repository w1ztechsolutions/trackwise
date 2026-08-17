# Environment Variables Reference

This document describes all environment variables used by TrackWise, their purposes, required/optional status, and valid values.

---

## Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_ENV` | Yes | `development` | Environment mode: `development`, `production`, or `testing`. |
| `SECRET_KEY` | Yes | Random (dev) | Flask secret key for session signing. Must be set explicitly in production. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `INSTANCE_PATH` | No | Auto | Path for Flask instance folder (SQLite DB, session files). On Vercel, set to `/tmp/instance`. |

---

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes (prod) | SQLite (dev) | Database connection string. Examples: `postgresql+psycopg://user:pass@localhost:5432/trackwise`, `sqlite:///instance/trackwise.db`, or Neon pooled URL. |

### Notes
- `postgresql://` URLs are automatically converted to `postgresql+psycopg://` by the app.
- Neon connection parameters like `channel_binding` are stripped automatically.
- If `DATABASE_URL` is missing and `FLASK_ENV=production`, the app raises `RuntimeError`.
- If `DATABASE_URL` starts with `postgresql` but no psycopg driver is installed, the app falls back to SQLite.

---

## Redis & Celery

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `memory://` | Redis connection string for Flask-Limiter and Celery. Example: `redis://default:password@host.upstash.io:port`. Leave empty to disable Celery. |
| `CELERY_DISABLED` | No | `true` | Set to `true` to disable Celery (serverless mode). Set to `false` to enable async background tasks. |

### Notes
- On Vercel, Celery is disabled by default. Tasks run synchronously during requests.
- For production with background jobs, use an external worker service (Railway, Render, or a dedicated Celery worker).

---

## Stripe (Subscriptions)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | Yes (payments) | — | Stripe secret API key. Use `sk_test_...` for testing, `sk_live_...` for production. |
| `STRIPE_PUBLISHABLE_KEY` | Yes (payments) | — | Stripe publishable key for client-side integration. |
| `STRIPE_WEBHOOK_SECRET` | Yes (payments) | — | Stripe webhook signing secret for verifying incoming webhook events. |

### Notes
- If Stripe keys are not configured, subscription features are effectively disabled but the app still runs.
- Webhooks must be configured in the Stripe dashboard to point to your `/stripe-webhook` endpoint.

---

## PDF Generation

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEASYPRINT_CACHEDIR` | No | `/tmp/weasyprint-cache` | Cache directory for WeasyPrint PDF generation. Use `/tmp` on Vercel/serverless. |

### Notes
- WeasyPrint requires system libraries (glibc, libffi, libxml2, libpng). These are pre-installed on Vercel.
- For local development on Windows, ensure GTK dependencies are available or use WSL.

---

## Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `memory://` | Used by Flask-Limiter. In-memory storage is not shared across workers. Use Redis for production. |

### Notes
- Default limits are hardcoded in `app/__init__.py`: 200 requests/day, 50 requests/hour.
- To adjust limits, modify the `default_limits` parameter in `Limiter()` initialization.

---

## Local Development

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_APP` | No | Auto | Not required. TrackWise uses the application factory pattern (`app:create_app`). `flask run` works without it. |

---

## Environment File Precedence

The application loads `.env` files in the following order (later files override earlier ones):

1. `{project_root}/.env`
2. `{project_root}/.env.local`
3. `{cwd}/.env`
4. `{cwd}/.env.local`

### Recommendations
- Commit `.env.example` to version control.
- Add `.env` and `.env.local` to `.gitignore`.
- Use `.env.local` for machine-specific overrides (local DB credentials, etc.).
- Use `.env` for shared team configuration.
