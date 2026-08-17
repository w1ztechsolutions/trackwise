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
- Audit logs record all journal entry creations (`AuditLog` model).
- Soft-delete support exists for `JournalEntry` (`is_deleted`, `deleted_by`, `deleted_at`).
- No credit card data is stored; Stripe handles all payment processing.

### Known Security Considerations
- Celery tasks run synchronously in serverless mode; avoid processing sensitive data in synchronous request paths when possible.
- WeasyPrint PDF generation runs in the request thread on Vercel; ensure PDF data does not contain sensitive information in logs.
- The `/api/products` endpoint is authenticated but does not support API key auth; for integrations, consider adding token-based authentication.
