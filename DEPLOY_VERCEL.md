# Deploying TrackWise to Vercel

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **PostgreSQL Database**: We recommend [Neon Serverless Postgres](https://neon.tech) (free tier available)
3. **Redis** (Optional): For background tasks, use [Upstash Redis](https://upstash.com) or set `CELERY_DISABLED=true`

## Quick Start

### 1. Set up PostgreSQL (Neon)

1. Go to [neon.tech](https://neon.tech) and create a project
2. Get your connection string (looks like `postgresql://...` or `postgresql+psycopg://...`)
3. Note: Neon uses pooling, so use the pooled connection string for better performance

### 2. Configure Environment Variables in Vercel

In your Vercel project settings, add these environment variables:

| Variable | Value | Required |
|----------|-------|----------|
| `FLASK_ENV` | `production` | Yes |
| `SECRET_KEY` | Random string (e.g., `python -c "import secrets; print(secrets.token_hex(32)}"`) | Yes |
| `DATABASE_URL` | Your Neon connection string | Yes |
| `DEMO_MODE_ENABLED` | `true` to expose the public role-based demo | No |
| `DEMO_DATABASE_URL` | Connection string for a separate demo-only Neon database | Only when demo is enabled |
| `INSTANCE_PATH` | `/tmp/instance` | Optional (auto-set for serverless) |
| `STRIPE_SECRET_KEY` | Your Stripe secret key | Yes (for payments) |
| `STRIPE_PUBLISHABLE_KEY` | Your Stripe publishable key | Yes |
| `STRIPE_WEBHOOK_SECRET` | Your Stripe webhook secret | Yes |
| `REDIS_URL` | Upstash Redis URL (optional) | No - leave empty to disable Celery |
| `CELERY_DISABLED` | `true` | Optional (defaults to true) |
| `WEASYPRINT_CACHEDIR` | `/tmp/weasyprint-cache` | Optional |

To enable public demo access, create a separate Neon project/database and configure both demo variables above. Bootstrap that empty database before enabling the demo:

```bash
flask --app 'app:create_demo_migration_app' demo-db-bootstrap
```

Run this command in an environment that has the production and demo URLs configured. The demo-only app factory checks that the database identities differ and refuses to bootstrap a demo database containing application rows or unmapped tables. Do not point `DEMO_DATABASE_URL` at the production database.

### 3. Deploy to Vercel

```bash
# Install Vercel CLI if not installed
npm install -g vercel

# Deploy
vercel

# Or deploy to production
vercel --prod
```

Alternatively, connect your GitHub repository to Vercel through the dashboard.

## Database Migration

After deployment, run migrations:

```bash
# Using Vercel CLI
vercel --prod
vercel env pull .env

# Then run migration
flask db upgrade
# Or
python scripts/migrate.py upgrade
```

## Handling Background Tasks

The Celery integration is designed to gracefully degrade in serverless mode:

- **Default**: Celery is disabled (`CELERY_DISABLED=true`)
- Tasks execute synchronously within the request
- For PDF generation, use Vercel Background Functions (up to 300s)

If you want to enable background processing with external Redis:

1. Create an Upstash Redis instance
2. Set `REDIS_URL` to your Upstash connection string
3. Set `CELERY_DISABLED=false`

**Note**: You'll still need a separate worker process to process Celery tasks. Consider:
- Render cron jobs for scheduled tasks
- Trigger.dev for serverless background jobs
- Upstash for simple async processing

## WeasyPrint PDF Generation

WeasyPrint generates PDFs server-side. In Vercel's serverless environment:

- Cache directory is set to `/tmp/weasyprint-cache` (ephemeral)
- PDFs are generated on-demand
- For persistent PDF storage, integrate with S3-compatible storage (e.g., Supabase Storage)

## Static Files and Templates

The application is configured to serve static files from the `/static` directory and templates from `/templates`. These work out-of-the-box with Vercel.

## Troubleshooting

### Build Errors
- Ensure `psycopg[binary]` is in requirements.txt
- Check that all dependencies are compatible with Linux (Vercel's build environment)

### Database Connection Issues
- Verify `DATABASE_URL` is correct
- For Neon, use the pooled connection string
- Check that SSL mode is enabled (`?sslmode=require`)

### Celery Tasks Not Running
- Celery is disabled by default in serverless
- Tasks will run synchronously during requests
- For proper async, use external worker service

## Alternative: Railway or Render

If you need full Celery support with persistent workers, consider:

- **Railway**: PostgreSQL, Redis, persistent worker support
- **Render**: Similar to Heroku, proper background worker support

Both platforms offer more flexibility for traditional Flask applications with background tasks.
