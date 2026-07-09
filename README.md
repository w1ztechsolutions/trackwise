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
- **Production Ready** — Docker, Nginx, Gunicorn, Celery, Redis, structured logging

## Tech Stack

- **Backend:** Flask 3.x, Flask-SQLAlchemy, Flask-Login, Flask-WTF
- **Database:** PostgreSQL (SQLite for development/testing)
- **Migrations:** Flask-Migrate (Alembic)
- **Task Queue:** Celery + Redis
- **Frontend:** Jinja2 templates, Chart.js, vanilla CSS/JS
- **Deployment:** Docker, Docker Compose, Nginx, Gunicorn

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
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/trackwise
# Or for SQLite development:
# DATABASE_URL=sqlite:///instance/trackwise.db
REDIS_URL=redis://localhost:6379/0
```

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

Open http://localhost:5000

### 5. Create an Account

1. Navigate to http://localhost:5000/register
2. Enter your business name, email, and password
3. This creates a new Business + Admin User + Chart of Accounts automatically

## Docker Deployment (Production)

### Prerequisites

- Docker
- Docker Compose

### 1. Configure Environment

```bash
cp .env.example .env
# Set production values:
# SECRET_KEY=<strong-random-key>
# DATABASE_URL=postgresql://trackwise:trackwise_secret@db:5432/trackwise
# REDIS_URL=redis://redis:6379/0
```

### 2. Start the Stack

```bash
docker-compose up -d --build
```

This starts:
- **web** — Flask app via Gunicorn (port 8000)
- **db** — PostgreSQL 16
- **redis** — Redis 7
- **celery-worker** — Background task processor
- **celery-beat** — Scheduled tasks
- **nginx** — Reverse proxy (ports 80/443)

### 3. Run Migrations

```bash
docker-compose exec web flask db upgrade
docker-compose exec web flask shell
>>> from app.services.subscription_service import seed_default_plans
>>> seed_default_plans()
>>> exit()
```

Access the app at http://localhost

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

```
trackwise/
├── app/
│   ├── __init__.py              # Application factory
│   ├── models/                  # Database models
│   │   ├── accounting.py        # Business, ChartOfAccounts, JournalEntry, etc.
│   │   ├── inventory.py         # Product, Warehouse, StockMovement
│   │   └── mixins.py            # BusinessScopedMixin for multi-tenant queries
│   ├── services/
│   │   ├── accounting_service.py
│   │   ├── inventory_service.py
│   │   ├── production_service.py
│   │   ├── subscription_service.py
│   │   └── reports/             # Financial report generators
│   ├── auth/                    # Authentication & RBAC
│   ├── dashboard/               # Dashboard routes
│   ├── inventory/               # Inventory routes
│   ├── purchases/               # Purchase/Bill routes
│   ├── sales/                   # Sales/Invoice routes
│   ├── expenses/                # Expense routes
│   ├── reports/                 # Report routes
│   ├── settings/                # Settings routes
│   ├── production/              # Production routes
│   ├── api/                     # JSON API
│   ├── tasks/                   # Celery tasks
│   ├── celery_app.py            # Celery config
│   ├── logging_config.py        # Structured logging
│   └── template_filters.py      # Jinja2 filters
├── migrations/                  # Alembic migrations
├── deploy/
│   ├── nginx.conf               # Nginx configuration
│   └── gunicorn_config.py       # Gunicorn configuration
├── static/                      # CSS, JS, images
├── templates/                   # Jinja2 templates
├── tests/                       # Test suite
├── models.py                    # Legacy model imports (backward compat)
├── services/                    # Legacy services (fifo_service.py)
├── config.py                    # Configuration classes
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
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
- `GET /api/products` — JSON product list

### Sales & Purchases
- `GET /sales` — Sales checkout
- `GET /purchases` — Purchase entry
- `GET /customers` — Customer list
- `GET /suppliers` — Supplier list
- `GET /invoices` — Invoice list
- `GET /payments` — Payment entry

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

## Multi-Tenancy

Every model includes a `business_id` foreign key. All queries are automatically scoped by the current user's `business_id` via the `BusinessScopedMixin` and `g.business_id` set in `before_request`.

## Subscription Plans

| Plan | Price | Max Users | Features |
|------|-------|-----------|----------|
| Free | $0 | 1 | Reports |
| Starter | $29 | 3 | Reports, Exports, Multi-user |
| Business | $99 | 10 | + API Access |
| Enterprise | $299 | Unlimited | + Priority Support |

## RBAC Roles

| Role | Permissions |
|------|-------------|
| admin | Full access to everything |
| accountant | Financial reports, expenses, settings |
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

## License

Proprietary — W1zTech Solutions

## Support

For issues and feature requests, contact W1zTech Solutions.