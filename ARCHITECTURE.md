# TRACKWISE SYSTEM ARCHITECTURE (FLASK SAAS DESIGN)

## 1. OVERVIEW

TrackWise is a modular Flask-based SaaS platform designed for:

- Accounting
- Inventory
- Sales & Purchases
- Production
- Financial reporting

Architecture is built for scalability, modularity, and multi-tenancy.

---

## 2. HIGH-LEVEL ARCHITECTURE

```
User Interface (Web / PWA)
    ↓
Flask Application Layer (Blueprints)
    ↓
Service Layer (Business Logic)
    ↓
Accounting Engine (Core System)
    ↓
Database Layer (PostgreSQL)
```

---

## 3. APPLICATION FACTORY

TrackWise uses the **Flask application factory pattern**:

- `app.py` is a legacy entrypoint for direct execution
- The actual factory is `create_app()` in `app/__init__.py`
- Configuration is loaded from `config.py` based on `FLASK_ENV`
- Blueprints are registered inside `create_app()`

```python
from app import create_app
app = create_app()
```

---

## 4. FLASK APPLICATION STRUCTURE

```
app/
├── __init__.py                  # Application factory
├── celery_app.py                # Celery configuration
├── logging_config.py            # Structured logging
├── template_filters.py          # Jinja2 filters
│
├── models/                      # Database models
│   └── *.py                     # SQLAlchemy models
│
├── services/                    # Business logic layer
│   ├── accounting_service.py
│   ├── inventory_service.py
│   ├── production_service.py
│   ├── subscription_service.py
│   └── reports/                 # Financial report generators
│       └── __init__.py
│
├── auth/                        # Authentication & RBAC
│   └── routes.py
│
├── dashboard/                   # Dashboard routes
│   └── routes.py
│
├── inventory/                   # Inventory routes
│   └── routes.py
│
├── purchases/                   # Purchase/Bill/Payment routes
│   └── routes.py
│
├── sales/                       # Sales/Invoice routes
│   └── routes.py
│
├── expenses/                    # Expense routes (deprecated, redirects to payments)
│   └── routes.py
│
├── reports/                     # Report routes
│   └── routes.py
│
├── settings/                    # Settings routes
│   └── routes.py
│
├── production/                  # Production routes
│   └── routes.py
│
├── api/                         # JSON API
│   ├── __init__.py
│   └── routes.py
│
├── superadmin/                  # Super admin routes
│   └── routes.py
│
├── approvals/                   # Approval workflow routes
│   └── routes.py
│
├── tasks/                       # Celery tasks
│   ├── __init__.py
│   └── report_tasks.py
```

---

## 5. DESIGN PRINCIPLES

### 5.1 Separation of Concerns

- **Routes** handle HTTP requests only
- **Services** handle business logic
- **Accounting engine** handles financial integrity

### 5.2 Service Layer Pattern

```
Route → Service → Database
```

Example — Invoice Creation:
1. Route receives request
2. Service validates and processes
3. Accounting engine posts journal entry

### 5.3 Blueprint Registration

All blueprints are registered in `app/__init__.py`:

| Blueprint | URL Prefix | Purpose |
|-----------|-----------|---------|
| `auth_bp` | `/` | Authentication |
| `dashboard_bp` | `/dashboard` | Main dashboard |
| `inventory_bp` | `/inventory` | Product management |
| `purchases_bp` | `/purchases` | Purchases, bills, payments |
| `sales_bp` | `/sales` | Sales, invoices |
| `expenses_bp` | `/expenses` | Expenses (deprecated, redirects to payments) |
| `reports_bp` | `/reports` | Financial reports |
| `settings_bp` | `/settings` | Configuration |
| `api_bp` | `/api` | JSON API |
| `production_bp` | `/production` | Production batches |
| `superadmin_bp` | `/superadmin` | Platform admin |
| `approvals_bp` | `/approvals` | Approval workflows |

---

## 6. CORE ACCOUNTING FLOW

```
User Action
    ↓
Business Module (Invoice / Expense / Purchase)
    ↓
Accounting Engine
    ↓
Journal Entries (Double Entry)
    ↓
Ledger Update
    ↓
Reports
```

**RULE:** Reports are NEVER manually updated. All reports are derived from journal entries.

---

## 7. DATABASE ARCHITECTURE

### 7.1 Multi-Tenant Design

Every table includes `business_id` for data isolation:

- Ensures data isolation between businesses
- Enables SaaS scalability
- All queries are automatically scoped via `BusinessScopedMixin` and `g.business_id`

### 7.2 Core Tables

#### Accounting Core
- `users`
- `businesses`
- `chart_of_accounts`
- `journal_entries`
- `journal_lines`
- `financial_categories`
- `line_items`

#### Sales
- `customers`
- `invoices`
- `invoice_items`
- `receipts`

#### Purchases
- `suppliers`
- `bills`
- `payments`

#### Inventory
- `products`
- `stock_movements`
- `warehouses`

#### Production
- `production_batches`
- `material_usage`
- `finished_goods_output`

#### Staff & Payments
- `staff`
- `payments`

---

## 8. ACCOUNTING ENGINE

### 8.1 Double Entry Rule

Every transaction must balance: **Debit = Credit**

Examples:

| Transaction | Debit | Credit |
|-------------|-------|--------|
| Expense | Expense Account | Cash/Bank |
| Invoice | Accounts Receivable | Revenue |
| Purchase | Inventory | Accounts Payable |
| Supplier Payment | Accounts Payable | Cash/Bank |
| Staff Payment | Expense Account | Cash/Bank |

### 8.2 Golden Rules

1. Never bypass accounting engine
2. Never store report values
3. Never directly edit ledger
4. Every transaction must balance (Debit = Credit)
5. Every table must include `business_id`

---

## 9. INVENTORY SYSTEM

### 9.1 FIFO Costing

Stock movements use FIFO (First-In, First-Out) costing:

- Purchase layers tracked via `StockTransaction.remaining_quantity`
- Sales consume from oldest layers first
- Accurate COGS calculation per sale

### 9.2 Stock Movements

| Type | Direction | Description |
|------|-----------|-------------|
| Stock In | + | Purchase receipts |
| Stock Out | - | Sales consumption |
| Production Input | - | Raw material usage |
| Production Output | + | Finished goods |

---

## 10. PRODUCTION MODULE

Designed for manufacturing SMEs (e.g., cement block manufacturing):

**Inputs:**
- Cement
- Sand
- Quarry Dust

**Outputs:**
- Finished blocks

The system automatically:
- Updates inventory on material consumption
- Creates accounting entries for production costs
- Tracks batch-level costs

---

## 11. REPORTING ENGINE

All reports are dynamically generated from journal entries:

- Income Statement
- Balance Sheet
- Cash Flow Statement
- Trial Balance
- General Ledger
- AR Aging
- AP Aging

**RULE:** No stored report values. All reports compute from journal entries.

---

## 12. SECURITY ARCHITECTURE

### 12.1 Authentication & Authorization

- bcrypt password hashing
- Flask-Login for session management
- Role-Based Access Control (RBAC)

### 12.2 RBAC Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access to everything |
| `accountant` | Financial reports, payments, settings, accounting |
| `cashier` | Sales, receipts, basic inventory view |
| `storekeeper` | Inventory, purchases, production |
| `viewer` | Read-only dashboards and reports |

### 12.3 Security Headers

The application sets security headers on all responses:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

### 12.4 Rate Limiting

Flask-Limiter is configured with default limits:

- 200 requests per day
- 50 requests per hour

Storage defaults to in-memory; use Redis for production.

---

## 13. BACKGROUND JOBS

### 13.1 Celery Tasks

Used for:

- PDF report generation
- Email sending
- Dashboard precomputation
- Scheduled report processing

### 13.2 Serverless Mode

In serverless environments (Vercel), Celery is disabled by default (`CELERY_DISABLED=true`). Tasks execute synchronously within the request.

---

## 14. CONFIGURATION

### 14.1 Configuration Classes

| Class | Environment | Description |
|-------|-------------|-------------|
| `DevelopmentConfig` | `development` | Debug mode, SQLite fallback |
| `ProductionConfig` | `production` | Secure headers, PostgreSQL |
| `TestingConfig` | `testing` | In-memory SQLite, test settings |

### 14.2 Environment Variables

Key environment variables:

| Variable | Description |
|----------|-------------|
| `FLASK_ENV` | `development`, `production`, or `testing` |
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string (optional) |
| `CELERY_DISABLED` | Disable Celery in serverless (default: `true`) |

---

## 15. SCALABILITY DESIGN

### 15.1 Recommended Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask 3.x |
| Database | PostgreSQL |
| Cache/Queue | Redis |
| Background Jobs | Celery |
| Reverse Proxy | Nginx |
| WSGI Server | Gunicorn |

### 15.2 Deployment Options

- **Vercel**: Serverless with Neon PostgreSQL
- **Railway/Render**: Alternative platforms with full Celery support

---

## 16. FUTURE EXTENSIONS

- Mobile app (React Native / Flutter)
- Bank reconciliation
- OCR receipt scanning
- AI financial insights
- Multi-currency support
- Offline-first PWA mode
- Enhanced API with OpenAPI/Swagger documentation

---

## 17. FINAL VISION

TrackWise becomes:

- A full SME accounting system
- Inventory + production platform
- SaaS ERP-lite solution
- Designed for African small businesses

