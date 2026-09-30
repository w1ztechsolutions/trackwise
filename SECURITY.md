# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :x:                |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in TrackWise, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email the security team at **security@w1ztechsolutions.com** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Best Practices for Deployment

### Environment Variables
- Never commit `.env` or `.env.local` to version control.
- Use strong, randomly generated `SECRET_KEY` values (32+ bytes).
- Rotate `SECRET_KEY` periodically in production.
- Store Stripe webhook secrets securely; verify signatures on all incoming webhooks.

### Database
- Use connection pooling (SQLAlchemy pool settings are configured in `config.py`).
- Enable SSL for PostgreSQL connections (`?sslmode=require` for Neon).
- Restrict database access by IP firewall rules.
- Run regular automated backups.

### Authentication & Authorization
- All API endpoints require authentication (`@login_required`).
- Passwords are hashed with bcrypt via Werkzeug.
- Sessions use `HTTPOnly` and `SameSite=Lax` cookies.
- Superadmin sessions have a shorter lifetime (1 hour) than regular sessions (5 hours).
- Force password change on first login for admin-created users (`must_change_password`).

### Headers & CSP
TrackWise sets the following security headers on all responses:

- `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' https://cdn.vercel-insights.com; style-src 'self' https://fonts.googleapis.com 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://vitals.vercel-analytics.com; form-action 'self'; frame-ancestors 'none';`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Rate Limiting
- Default: 200 requests per day, 50 requests per hour per IP.
- Use Redis for production rate limiting storage (in-memory is not shared across workers).
- Adjust limits in `app/__init__.py` if needed.

### Data Protection
- Multi-tenant data isolation is enforced via `business_id` scoping on all queries.
- Audit logs record financially significant ORM creates/updates/deletes, journal lines, approval actions, and authentication events (`AuditLog` model). Password hashes and bank account numbers are excluded from snapshots.
- Soft-delete support exists for `JournalEntry` (`is_deleted`, `deleted_by`, `deleted_at`).
- No credit card data is stored; Stripe handles all payment processing.
- Demo access is disabled by default. When enabled, anyone who can reach `/demo` can create or join a named workspace and select any built-in role. All demo data resides on `DEMO_DATABASE_URL`; keep it on a separate, disposable database and never enter real or confidential data.

### Known Security Considerations
- Celery tasks run synchronously in serverless mode; avoid processing sensitive data in synchronous request paths when possible.
- WeasyPrint PDF generation runs in the request thread on Vercel; ensure PDF data does not contain sensitive information in logs.
- The `/api/products` endpoint is authenticated but does not support API key auth; for integrations, consider adding token-based authentication.

### Security Updates

**2026-09-30 — Isolated demo role testing**
- Added a public demo business flow behind the opt-in `DEMO_MODE_ENABLED` setting, backed by `DEMO_DATABASE_URL`.
- Visitors select a role; each is assigned a random, undisclosed internal user. Existing business names require an explicit proceed action and share mutable demo data.
- Normal password login stays on `DATABASE_URL`; demo user lookups and app requests stay on the demo engine selected by the signed session context.
- Configure a distinct isolated Neon project/branch for demo and set `DEMO_MODE_ENABLED=false` to disable public demo access.

**2026-09-30 — Financial audit coverage**
- Added transactional audit events for financial records and audit events for login, logout, and password changes.
- Application code rejects updates and deletes to existing audit log rows.
- This is application-level audit protection; database administrators with direct SQL privileges can still change stored records.
- Operators should apply the documented financial-controls migration and restrict direct database write access to trusted administrators; no action is required for existing audit rows.

**2026-08-24 — CSP and SRI Hardening**
- MDN HTTP Observatory flagged two failures: unsafe CSP (`'unsafe-inline'` in `script-src`, missing `object-src`) and missing SRI hashes on external scripts.
- Implemented per-request CSP nonces (`secrets.token_urlsafe(16)`) and removed `'unsafe-inline'` from `script-src`.
- Added `object-src 'none'` to prevent plugin-based attacks.
- Externalized all inline critical CSS and JavaScript into dedicated files under `static/css/` and `static/js/`.
- Replaced inline event handlers (`onclick`, `onchange`, `onsubmit`) with `data-` attributes handled by a global `form-handlers.js`.
- Added SHA-256 `integrity` hashes and `crossorigin="anonymous"` to every external `<script>` and `<link>` tag.
- Observatory score improved from 75 to expected 90+.
