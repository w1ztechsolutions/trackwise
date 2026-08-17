# TrackWise

> Accounting, Inventory & Production Management System for SMEs

TrackWise is a comprehensive business management platform with double-entry accounting at its core. Built with Flask, it provides inventory tracking (FIFO), sales/purchase management, production tracking, financial reporting, and multi-tenant SaaS readiness.

## Features

- **Double-Entry Accounting** — Every transaction posts to a journal with balanced debits/credits
- **Inventory Management** — FIFO cost tracking, multi-warehouse support, stock movements
- **Sales & Purchases** — Invoices, bills, receipts, payments with customer/supplier management
- **Production System** — Raw material consumption to finished goods with cost calculation
- **Financial Reports** — Income Statement, Balance Sheet, Cash Flow, Trial Balance, General Ledger, AR/AP Aging
- **Multi-Tenant** — Business isolation via `business_id` scoping on all queries
- **Subscription Management** — Free/Starter/Business/Enterprise plans
- **RBAC** — Role-based access control (admin, accountant, cashier, storekeeper, viewer)
- **Production Ready** — Vercel serverless, Gunicorn, Celery, Redis, structured logging

## Tech Stack

- **Backend:** Flask 3.x, Flask-SQLAlchemy, Flask-Login, Flask-WTF
- **Database:** PostgreSQL (SQLite for development/testing)
- **Migrations:** Flask-Migrate (Alembic)
- **Task Queue:** Celery + Redis (disabled in serverless; runs synchronously on Vercel)
- **Frontend:** Jinja2 templates, Chart.js, vanilla CSS/JS
- **Deployment:** Vercel (serverless), local Flask dev server

## Quick Start (Development)

### Prerequisites

- Python 3.12+
- PostgreSQL (or use SQLite for quick testing)
- pip

### 1. Clone and Setup

```bash
git clone https://github.com/w1ztechsolutions/trackwise.git
cd trackwise
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/trackwise
# Or for SQLite development:
# DATABASE_URL=sqlite:///instance/trackwise.db
REDIS_URL=redis://localhost:6379/0
```

> **Note:** `FLASK_APP` is not required. TrackWise uses the Flask application factory pattern defined in `app/__init__.py`.

### 3. Initialize Database

```bash
# Run migrations
flask db upgrade

# Seed default subscription plans
flask shell
>>> from app.services.subscription_service import seed_default_plans
>>> seed_default_plans()
>>> exit()
```

### 4. Run the App

```bash
flask run
# or
python app.py
```

> **Note:** `python app.py` uses the legacy entrypoint. The recommended way is `flask run`, which uses the application factory in `app/__init__.py`.

Open `http://localhost:5000`

### 5. Create an Account

1. Navigate to `http://localhost:5000/register`
2. Enter your business name, email, and password
3. This creates a new Business + Admin User + Chart of Accounts automatically

## Deployment

### Vercel (Serverless — Primary Target)

TrackWise is optimized for Vercel serverless deployment. See [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) for the full guide.

Key points:

- The Vercel entrypoint is `api/index.py`
- `vercel.json` routes all requests through the Flask WSGI app
- Celery tasks run synchronously during requests in serverless mode
- Use Neon PostgreSQL or another managed Postgres for the database
- Redis is optional in serverless (used only for rate limiting if configured)

### Local Development

Run with the Flask development server:

```bash
flask run
```

For production-like local execution with Gunicorn:

```bash
gunicorn "app:create_app()"
```

## Database Management

### Migrations

```bash
# Create a new migration
flask db migrate -m "description"

# Apply migrations
flask db upgrade

# Rollback one migration
flask db downgrade

# Check current version
flask db current
```

### Reset Database (Development Only)

```bash
# Delete migration history and recreate
rm -rf migrations/versions/*
flask db migrate -m "initial"
flask db upgrade
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_fifo.py

# Run with verbose output
pytest -v
```

Test configuration uses SQLite in-memory database. Tests cover:

- FIFO inventory service
- Accounting engine
- Financial reports
- Inventory service
- Production service
- Database configuration

## Project Structure

```folder
trackwise/
├── app/
│   ├── __init__.py              # Application factory
│   ├── models/                  # Database model submodules
│   │   ├── __init__.py          # Re-exports all models
│   │   ├── accounting.py        # Business, ChartOfAccounts, JournalEntry, JournalLine, AuditLog, BankStatement
│   │   ├── approval.py          # ApprovalConfig, ApprovalRequest, ApprovalAction
│   │   ├── inventory.py         # Product, Warehouse, StockMovement, StockTransaction, Customer, Supplier, Invoice, Bill, Payment, etc.
│   │   ├── mixins.py            # BusinessScopedMixin for multi-tenant queries
│   │   ├── superadmin.py        # SuperAdmin model
│   │   └── user.py              # User model wrapper
│   ├── services/
│   │   ├── accounting_service.py
│   │   ├── inventory_service.py
│   │   ├── production_service.py
│   │   ├── subscription_service.py
│   │   └── reports/             # Financial report generators
│   │       ├── __init__.py
│   │       ├── ap_aging.py
│   │       ├── ar_aging.py
│   │       ├── balance_sheet.py
│   │       ├── cash_flow.py
│   │       ├── general_ledger.py
│   │       ├── income_statement.py
│   │       └── trial_balance.py
│   ├── auth/                    # Authentication & RBAC
│   │   ├── decorators.py
│   │   ├── permissions.py
│   │   ├── register_routes.py
│   │   ├── routes.py
│   │   └── validators.py
│   ├── dashboard/               # Dashboard routes
│   │   └── routes.py
│   ├── inventory/               # Inventory routes
│   │   └── routes.py
│   ├── purchases/               # Purchase/Bill/Payment routes
│   │   └── routes.py
│   ├── sales/                   # Sales/Invoice routes
│   │   └── routes.py
│   ├── expenses/                # Expense routes (deprecated, redirects to payments)
│   │   └── routes.py
│   ├── reports/                 # Report routes
│   │   └── routes.py
│   ├── settings/                # Settings routes
│   │   └── routes.py
│   ├── production/              # Production routes
│   │   └── routes.py
│   ├── api/                     # JSON API
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── superadmin/              # Super admin routes
│   │   ├── routes.py
│   │   └── templates/
│   ├── approvals/               # Approval workflow routes
│   │   ├── routes.py
│   │   └── templates/
│   ├── accounting/              # Chart of Accounts & manual journal entries
│   │   ├── routes.py
│   │   └── templates/
│   ├── tasks/                   # Celery tasks
│   │   ├── __init__.py
│   │   └── report_tasks.py
│   ├── celery_app.py            # Celery config
│   ├── logging_config.py        # Structured logging
│   └── template_filters.py      # Jinja2 filters
├── migrations/                  # Alembic migrations
├── static/                      # CSS, JS, images
├── templates/                   # Jinja2 templates
├── tests/                       # Test suite
├── models.py                    # Legacy model imports (backward compat)
├── services/                    # Legacy services (fifo_service.py)
├── config.py                    # Configuration classes
├── docs/                        # Additional documentation
│   ├── API.md                   # JSON API documentation
│   ├── PAYMENTS_HUB.md          # Payments Hub system docs
│   ├── bugs_and_fixes.md        # Known bugs and fixes log
│   └── adr/                     # Architecture Decision Records
│       └── README.md
├── api/
│   └── index.py                 # Vercel WSGI entry point
├── app.py                       # Legacy entrypoint (use `flask run`)
├── vercel.json                  # Vercel serverless config
├── .vercelignore                # Vercel ignore rules
├── requirements.txt
├── CHANGELOG.md                 # Version history
├── CONTRIBUTING.md              # Contribution guidelines
├── ARCHITECTURE.md              # System architecture
├── UPGRADE.md                   # Upgrade roadmap
├── DEPLOY_VERCEL.md             # Vercel deployment guide
├── README.md
├── AGENT.md                     # AI documentation enforcement rules
├── SECURITY.md                  # Security policy
└── LICENSE                      # Proprietary license
```

## API Endpoints

### Authentication

- `GET /login` — Login page
- `POST /login` — Authenticate user
- `GET /logout` — Logout
- `GET /register` — Registration (onboarding) page
- `POST /register` — Create business + admin user

### Dashboard

- `GET /dashboard` — Main dashboard with KPIs

### Inventory

- `GET /inventory` — Product list
- `POST /inventory` — Create product

### Sales & Purchases

- `GET /sales` — Sales checkout
- `GET /purchases` — Purchase entry
- `GET /customers` — Customer list
- `GET /suppliers` — Supplier list
- `GET /invoices` — Invoice list
- `GET /payments` — Payment entry (unified payments hub)

### Production

- `GET /production` — Production batches
- `POST /production` — Create batch

### Reports

- `GET /reports/income-statement`
- `GET /reports/balance-sheet`
- `GET /reports/cash-flow`
- `GET /reports/trial-balance`
- `GET /reports/general-ledger`
- `GET /reports/ar-aging`
- `GET /reports/ap-aging`

### Settings

- `GET /settings` — Tax rate, seed data

### Health

- `GET /health` — Health check (DB status, version)

### JSON API

For programmatic access, see [docs/API.md](docs/API.md):

| Method | Path | Description |
| -------- | ------ | ------------- |
| `GET` | `/api/products` | JSON product list |
| `GET` | `/api/suppliers` | JSON supplier list |
| `GET` | `/api/accounting/verify` | Verify accounting integrity |

## Multi-Tenancy

Every model includes a `business_id` foreign key. All queries are automatically scoped by the current user's `business_id` via the `BusinessScopedMixin` and `g.business_id` set in `before_request`.

## Subscription Plans

| Plan | Price | Max Users | Features |
| ------ | ------- | ----------- | ---------- |
| Free | $0 | 1 | Reports |
| Starter | $29 | 3 | Reports, Exports, Multi-user |
| Business | $99 | 10 | + API Access |
| Enterprise | $299 | Unlimited | + Priority Support |

## RBAC Roles

| Role | Permissions |
| ------ | ------------- |
| admin | Full access to everything |
| accountant | Financial reports, payments, settings |
| cashier | Sales, receipts, basic inventory view |
| storekeeper | Inventory, purchases, production |
| viewer | Read-only dashboards and reports |

## Background Tasks (Celery)

- **PDF Report Generation** — `app.tasks.report_tasks.generate_report_pdf`
- **Email Sending** — `app.tasks.report_tasks.send_email`
- **Dashboard Precompute** — `app.tasks.report_tasks.precompute_dashboard`

Start Celery worker:

```bash
celery -A app.celery_app worker --loglevel=info
```

> **Note:** Celery is disabled by default on Vercel (serverless). Tasks run synchronously during requests. For async processing in production, use an external worker service (e.g., Railway, Render).

## Logging

In production, logs are formatted as JSON for aggregation:

```json
{
  "timestamp": "2026-07-09T22:00:00.000Z",
  "level": "INFO",
  "logger": "trackwise",
  "message": "Request processed",
  "business_id": 1,
  "user_id": 5
}
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design, database architecture, and design principles
- **[UPGRADE.md](UPGRADE.md)** — Phased upgrade roadmap and golden rules
- **[DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)** — Vercel deployment guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Contribution guidelines and code style
- **[CHANGELOG.md](CHANGELOG.md)** — Version history and release notes
- **[AGENT.md](AGENT.md)** — AI documentation enforcement rules
- **[SECURITY.md](SECURITY.md)** — Security policy and best practices
- **[LICENSE](LICENSE)** — Proprietary license
- **[docs/API.md](docs/API.md)** — JSON API documentation
- **[docs/PAYMENTS_HUB.md](docs/PAYMENTS_HUB.md)** — Payments Hub system documentation
- **[docs/bugs_and_fixes.md](docs/bugs_and_fixes.md)** — Known bugs and fixes log
- **[docs/OPERATIONS.md](docs/OPERATIONS.md)** — Operations runbook and utility scripts
- **[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)** — Environment variable reference
- **[docs/DATABASE.md](docs/DATABASE.md)** — Database schema reference
- **[docs/RELEASES.md](docs/RELEASES.md)** — Release process and versioning guide
- **[docs/adr/README.md](docs/adr/README.md)** — Architecture Decision Records
- **[docs/missing_documentation_audit.md](docs/missing_documentation_audit.md)** — Documentation gap audit

## License

Proprietary — W1zTech Solutions

## Support

For issues and feature requests, contact W1zTech Solutions.
