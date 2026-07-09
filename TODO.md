# TRACKWISE -- UPGRADE TODO LIST

> Actionable tasks derived from UPGRADE.md (roadmap) and ARCHITECTURE.md (target design).
>
> Current stack: Flask 2.x + SQLAlchemy + SQLite + Jinja2 + Chart.js
> Target stack: Flask Blueprints + PostgreSQL + Redis + Celery + Nginx/Gunicorn

---

## PHASE 0 -- QUICK WINS (IMMEDIATE BUGFIXES)

> Small, safe fixes that improve correctness & security with minimal refactoring.

- [x] 0.1 - Fix record_expense zero-amount bug (services/fifo_service.py:264)
  - Change if amount <= 0 to if amount < 0 (currently allows 0-value expenses)
- [x] 0.2 - Validate empty items_data in record_sale (services/fifo_service.py:98)
  - Add if not items_data: raise ValueError(...) - currently only checked for purchases
- [x] 0.3 - Read SECRET_KEY from environment (app.py:12)
  - Replace hardcoded string with os.environ.get('SECRET_KEY', 'dev-fallback-key')
- [x] 0.4 - Read DATABASE_URL from environment (app.py:13)
  - Replace hardcoded SQLite URI with os.environ.get('DATABASE_URL', 'sqlite:///...')
- [x] 0.5 - Fix dashboard chart month drift (app.py:77)
  - Replace timedelta(days=i*30) with actual calendar month calculation
- [x] 0.6 - Add server-side validation for empty sale items
  - Mirror the validation that already exists in record_purchase

Done criteria: All 6 items above checked, existing tests pass.

---

## PHASE 1 -- FOUNDATION (MVP STABILIZATION)

> Refactor the monolithic Flask app into a modular, testable structure with PostgreSQL support.

### 1.1 -- Project Restructuring

- [x] 1.1.1 -- Create application factory pattern
  - Move app.py logic into app/__init__.py (create_app() function)
  - Move existing models into app/models/ package
  - Move existing services into app/services/ package
  - Create config.py with class-based configuration (Dev, Test, Prod)
- [x] 1.1.2 -- Split monolithic app.py into Blueprints
  - Create app/dashboard/ blueprint
  - Create app/inventory/ blueprint (products, stock valuation)
  - Create app/purchases/ blueprint (purchase orders)
  - Create app/sales/ blueprint (sales checkout)
  - Create app/expenses/ blueprint (expense logging)
  - Create app/reports/ blueprint (P&L reporting)
  - Create app/settings/ blueprint (tax rate, seed data)
  - Create app/api/ blueprint (existing /api/products JSON endpoint)
- [x] 1.1.3 -- Move seed data out of app.py
  - Create seed.py at project root (or app/seed.py)
- [x] 1.1.4 -- Move Jinja2 template filters into a dedicated module
  - Create app/template_filters.py for currency and datetime filters
  - Register filters in create_app()

### 1.2 -- Database Upgrade (SQLite to PostgreSQL)

- [x] 1.2.1 -- Add PostgreSQL adapter to dependencies
  - Add psycopg2-binary to requirements.txt
  - Add flask-migrate for schema migrations
- [x] 1.2.2 -- Create configuration classes
  - config.py: Config (base), DevelopmentConfig (SQLite), ProductionConfig (PostgreSQL), TestingConfig (SQLite :memory:)
- [x] 1.2.3 -- Add connection pooling
  - Configure SQLALCHEMY_ENGINE_OPTIONS with pool settings for PostgreSQL
- [x] 1.2.4 -- Initialize Alembic/Flask-Migrate
  - flask db init then flask db migrate -m "initial models"
  - Create initial migration from existing models

### 1.3 -- Testing Infrastructure

- [x] 1.3.1 -- Expand unit tests for existing FIFO service
  - Add test for cross-FIFO-layer sales (multiple batches consumed)
  - Add test for selling exact quantity that equals total inventory
  - Add test for empty database state (zero products, no sales)
  - Add test for date range filtering in get_profit_loss()
  - Add test for negative/unreasonable inputs
- [x] 1.3.2 -- Add integration (route) tests
  - Test app.test_client() GET/POST for each blueprint
  - Test flash messages on success/error
  - Test redirect behavior
- [x] 1.3.3 -- Set up test configuration
  - Create conftest.py with pytest fixtures (if switching to pytest)
  - Or add Flask test setup to existing unittest structure

### 1.4 -- Security Hardening

- [x] 1.4.1 -- Add Flask-Login authentication
  - Create User model with business_id, hashed password (bcrypt), role
  - Create login/logout routes in app/auth/ blueprint
  - Add @login_required decorator to all existing route Blueprints
- [x] 1.4.2 -- Add CSRF protection
  - Add Flask-WTF to requirements.txt
  - Add {{ form.hidden_tag() }} or {{ csrf_token }} to all forms
  - Import and initialize CSRFProtect in create_app()
- [x] 1.4.3 -- Add role-based access control structure
  - Define roles: admin, accountant, cashier, storekeeper, viewer
  - Create decorator: @role_required('admin', 'accountant')
  - Apply to sensitive routes (settings, seed data, tax rate changes)

### 1.5 -- UI/UX Improvements

- [x] 1.5.1 -- Add pagination to list views
  - Sales history, purchase history, expense log
  - Use SQLAlchemy .paginate() on backend
  - Add page navigation controls in templates
- [x] 1.5.2 -- Add mobile-responsive layout
  - Introduce collapsible sidebar (hamburger menu on < 768px)
  - Make KPI grid single-column on mobile
  - Make tables horizontally scrollable on small screens
- [x] 1.5.3 -- Add loading states
  - Disable submit buttons on form submission with spinner
  - Show loading overlay for Chart.js render delay

Phase 1 done criteria:
- [x] app/ package structure with Blueprints in place
- [x] All existing functionality works (dashboard, inventory, purchases, sales, expenses, reports, settings)
- [x] PostgreSQL migration tested locally (initial Alembic migration created and verified)
- [x] Test suite passes (19/19, including login-required routes with LOGIN_DISABLED in test config)
- [x] Login required to access any route
- [x] CSRF tokens on all forms
- [x] Mobile-responsive sidebar + loading states

---

## PHASE 2 -- ACCOUNTING ENGINE (CRITICAL)

> Introduce double-entry accounting as the immutable core of all financial transactions.

### 2.1 -- Accounting Core Models

- [x] 2.1.1 -- Create Business model
  - Fields: id, name, tax_id, currency, created_at
  - Every other table will reference business_id
- [x] 2.1.2 -- Create ChartOfAccounts model
  - Fields: id, business_id, code (e.g. "1000"), name, type (asset/liability/equity/income/expense), is_active, parent_id (hierarchical)
  - Seed standard accounts: Cash, Bank, Accounts Receivable, Inventory, Accounts Payable, Revenue, COGS, Rent Expense, etc.
- [x] 2.1.3 -- Create JournalEntry model
  - Fields: id, business_id, entry_date, reference_type (Invoice/Purchase/Receipt/etc.), reference_id, description, created_by, created_at
- [x] 2.1.4 -- Create JournalLine model
  - Fields: id, journal_entry_id, account_id (FK to chart_of_accounts), debit_amount, credit_amount
  - Constraint: For each entry, sum(debits) = sum(credits)

### 2.2 -- Accounting Engine Service

- [x] 2.2.1 -- Create app/services/accounting_service.py
  - post_entry(business_id, date, description, lines, reference_type, reference_id) -- core journal entry function
  - Validation: debits must equal credits
  - Validation: all accounts must be active
  - Returns the created JournalEntry
- [x] 2.2.2 -- Create Ledger view/reporting query
  - SQL/view: SELECT account_id, SUM(debit) - SUM(credit) AS balance FROM journal_lines GROUP BY account_id
  - Not a stored table -- always computed from journal lines

### 2.3 -- Migrate Existing Transactions to Double-Entry

- [x] 2.3.1 -- Wire record_sale into accounting engine
  - On sale: Dr Accounts Receivable (or Cash), Cr Revenue; Dr COGS, Cr Inventory
  - Maintain existing FIFO COGS logic -- add journal posting on top
- [x] 2.3.2 -- Wire record_purchase into accounting engine
  - On purchase: Dr Inventory, Cr Accounts Payable (or Cash)
- [x] 2.3.3 -- Wire record_expense into accounting engine
  - On expense: Dr Expense Account, Cr Cash (or Bank)

### 2.4 -- Accounting Data Integrity

- [x] 2.4.1 -- Add balance verification endpoint
  - Endpoint or script to verify sum(debits) = sum(credits) for all entries
- [x] 2.4.2 -- Add audit logging
  - Create app/models/audit_log.py: id, business_id, user_id, action, table_name, record_id, old_values, new_values, timestamp
  - Log all create/update/delete on financial records

Phase 2 done criteria:
- [x] Chart of accounts seeded with standard SME accounts
- [x] Journal entry + line models created
- [x] post_entry() function implemented and tested
- [x] All 3 existing transaction types (sale, purchase, expense) post double-entry journals
- [x] No transaction can be created that breaks Debit = Credit
- [x] Audit log records all financial changes

---

## PHASE 3 -- INVENTORY SYSTEM

> Enhance inventory beyond FIFO tracking with warehouse support and full stock movement control.

### 3.1 -- Inventory Models

- [x] 3.1.1 -- Add Warehouse model
  - Fields: id, business_id, name, location, is_active
- [x] 3.1.2 -- Update Product model
  - Add warehouse_id (optional), category, unit_of_measure, barcode, is_active
  - Keep existing FIFO layer logic intact
- [x] 3.1.3 -- Create StockMovement model (replaces/enhances StockTransaction)
  - Fields: id, business_id, product_id, warehouse_id, type (IN/OUT/TRANSFER/ADJUSTMENT), quantity, unit_cost, reference_type, reference_id, created_by, timestamp
  - Migrate existing StockTransaction data if needed


### 3.2 -- Inventory Services

- [x] 3.2.1 -- Create app/services/inventory_service.py
  - adjust_stock() -- manual stock adjustment with accounting entry
  - transfer_stock() -- move stock between warehouses
  - get_valuation_by_warehouse() -- valuation per location

- [x] 3.2.2 -- Create physical inventory / stock count feature

  - Count entry and variance posting
  - Auto-generates accounting entry for discrepancies

Phase 3 done criteria:
- [x] Warehouse CRUD in UI
- [x] Product shows warehouse assignment
- [x] Stock transfers between warehouses work end-to-end
- [x] Inventory adjustment with accounting entry


---

## PHASE 4 -- SALES & PURCHASES

> Formalize customer/supplier management, invoicing, and payment tracking.

### 4.1 -- Customer & Supplier Models

- [x] 4.1.1 -- Create Customer model
  - Fields: id, business_id, name, phone, email, address, credit_limit, opening_balance, is_active
- [x] 4.1.2 -- Create Supplier model
  - Fields: id, business_id, name, phone, email, address, payment_terms, opening_balance, is_active


### 4.2 -- Sales Module

- [x] 4.2.1 -- Create Invoice model

  - Fields: id, business_id, customer_id, invoice_number (auto-generated), invoice_date, due_date, subtotal, tax_amount, total_amount, status (draft/issued/paid/cancelled), notes
- [x] 4.2.2 -- Create InvoiceItem model

  - Fields: id, invoice_id, product_id, description, quantity, unit_price, line_total
- [x] 4.2.3 -- Create Receipt model

  - Fields: id, business_id, customer_id, invoice_id (nullable), receipt_date, amount, payment_method (cash/bank/mobile money), reference, notes
- [x] 4.2.4 -- Migrate existing Sale/SaleItem to Invoice flow
  - Sales now generate an Invoice + optional Receipt
  - Auto-posts to accounting: Dr AR (or Cash), Cr Revenue


### 4.3 -- Purchases Module

- [x] 4.3.1 -- Create Bill model (supplier invoice)

  - Fields: id, business_id, supplier_id, bill_number, bill_date, due_date, subtotal, tax_amount, total_amount, status (draft/received/paid/cancelled)
- [x] 4.3.2 -- Create BillItem model

  - Fields: id, bill_id, product_id, description, quantity, unit_cost, line_total
- [x] 4.3.3 -- Create Payment model (money paid to supplier)

  - Fields: id, business_id, supplier_id, bill_id (nullable), payment_date, amount, payment_method, reference
- [x] 4.3.4 -- Migrate existing Purchase/PurchaseItem to Bill flow
  - Purchases now generate a Bill
  - Auto-posts to accounting: Dr Inventory, Cr AP


### 4.4 -- UI Pages

- [x] 4.4.1 -- Customer list + detail page
  - Customer CRUD entry point and list view are available under /customers
- [x] 4.4.2 -- Supplier list + detail page
  - Supplier CRUD entry point and list view are available under /suppliers
- [x] 4.4.3 -- Invoice creation form (replaces current sales form)
  - Invoice creation form is available under /invoices with customer and item selection
- [x] 4.4.4 -- Receipt / payment entry forms
  - Receipt/payment entry is available under /payments with cash, bank, and mobile money options

Phase 4 done criteria:
- [x] Customer and supplier CRUD complete
- [x] Invoices created from sales, Bills created from purchases
- [x] Payment/Receipt entry posts to accounting
- [x] Old Sale/Purchase models deprecated or migrated
- [x] AR/AP balances visible in customer/supplier detail

---

## PHASE 5 -- PRODUCTION SYSTEM

> Cement block manufacturing module -- raw material consumption to finished goods output.

### 5.1 -- Production Models

- [x] 5.1.1 -- Create ProductionBatch model
  - Fields: id, business_id, batch_number (auto), production_date, product_id (finished good), quantity_produced, status (planned/in-progress/completed/cancelled), notes, created_by
- [x] 5.1.2 -- Create MaterialUsage model
  - Fields: id, production_batch_id, product_id (raw material), quantity_consumed, unit_cost_at_consumption
- [x] 5.1.3 -- Create FinishedGoodOutput model
  - Fields: id, production_batch_id, product_id, quantity, unit_cost (calculated from total material cost / quantity)

### 5.2 -- Production Service

- [x] 5.2.1 -- Create app/services/production_service.py
  - create_batch() -- starts a new production batch
  - consume_material() -- deducts raw material from inventory (FIFO) and records usage
  - complete_batch() -- calculates finished good cost, creates finished good stock, posts accounting entries
  - cancel_batch() -- reverses material consumption

### 5.3 -- Production Accounting Integration

- [x] 5.3.1 -- Wire material consumption to accounting
  - Dr Work-in-Progress (WIP) Inventory, Cr Raw Materials Inventory
- [x] 5.3.2 -- Wire batch completion to accounting
  - Dr Finished Goods Inventory, Cr Work-in-Progress (WIP)

### 5.4 -- Production UI

- [x] 5.4.1 -- Production batch list + detail page
- [x] 5.4.2 -- New batch form (select product, enter planned quantity)
- [x] 5.4.3 -- Material consumption entry (select raw materials, enter quantities)
- [x] 5.4.4 -- Batch completion confirmation (shows cost summary)

Phase 5 done criteria:
- [x] Full production cycle works: create batch, consume materials, complete, stock updated
- [x] COGS of finished goods calculated from actual material costs
- [x] Accounting entries posted for WIP and FG movements
- [x] Production batch history visible in UI

---

## PHASE 6 -- REPORTING ENGINE

> All reports dynamically derived from journal entries -- no stored report values.

### 6.1 -- Report Queries

- [x] 6.1.1 -- Income Statement (app/services/reports/income_statement.py)
  - Revenue accounts (credit balances) - COGS = Gross Profit
  - Less operating expenses = Net Income
  - Accept business_id, start_date, end_date parameters
- [x] 6.1.2 -- Balance Sheet (app/services/reports/balance_sheet.py)
  - Assets (debit balances): Cash, AR, Inventory, Fixed Assets
  - Liabilities (credit balances): AP, Loans, Tax Payable
  - Equity (credit balances): Retained Earnings, Capital
  - Verify: Assets = Liabilities + Equity
- [x] 6.1.3 -- Cash Flow Statement (app/services/reports/cash_flow.py)
  - Operating activities (net income, changes in AR/AP/inventory)
  - Investing activities (asset purchases)
  - Financing activities (loans, capital)
- [x] 6.1.4 -- Trial Balance (app/services/reports/trial_balance.py)
  - All accounts with debit/credit totals
  - Verify: Total Debits = Total Credits
- [x] 6.1.5 -- General Ledger (app/services/reports/general_ledger.py)
  - Per-account detail: all journal lines with running balance
- [x] 6.1.6 -- AR Aging (app/services/reports/ar_aging.py)
  - Customer balances grouped by aging buckets (0-30, 31-60, 61-90, 90+ days)
- [x] 6.1.7 -- AP Aging (app/services/reports/ap_aging.py)
  - Supplier balances grouped by aging buckets

### 6.2 -- Report UI

- [x] 6.2.1 -- Redesign Reports page (templates/reports.html)
  - Tabbed or dropdown navigation between report types
  - Date range filter for all reports
  - Print-friendly CSS
- [x] 6.2.2 -- Add Balance Sheet chart (asset/liability/equity breakdown)
- [x] 6.2.3 -- Add Cash Flow chart (operating vs investing vs financing)
- [x] 6.2.4 -- Export to PDF (via WeasyPrint or similar)
  - Background job for PDF generation

Phase 6 done criteria:
- [x] All 7 report types implemented
- [x] Income Statement matches (or improves on) current P&L output
- [x] Balance Sheet balances (Assets = Liabilities + Equity)
- [x] Trial Balance validates (Debits = Credits)
- [x] Reports page reworked with navigation between report types

---

## PHASE 7 -- SAAS READINESS

> Multi-tenant architecture, subscription management, and production deployment.

### 7.1 -- Multi-Tenant Enforcement

- [ ] 7.1.1 -- Add business_id to all existing models
  - Product, StockTransaction, Purchase, PurchaseItem, Sale, SaleItem, Expense, Setting
  - Foreign key to new Business table
- [ ] 7.1.2 -- Add automatic business_id filtering
  - Create SQLAlchemy query mixin or flask.g hook for business_id
  - Every query auto-filters by current business
- [ ] 7.1.3 -- Create business onboarding flow
  - Registration form: business name, tax ID, currency, admin user details
  - Auto-creates Business + Admin User + seed Chart of Accounts

### 7.2 -- Subscription & Billing

- [ ] 7.2.1 -- Create subscription plans
  - Define Plan model: name, price, max_users, features (JSON)
  - Plans: Free (1 user), Starter (3 users), Business (10 users), Enterprise (unlimited)
- [ ] 7.2.2 -- Create Subscription model
  - Fields: id, business_id, plan_id, status (active/trialing/cancelled/expired), start_date, renewal_date
- [ ] 7.2.3 -- Add payment gateway integration
  - Mobile money (MPesa/Airtel Money) - primary payment method for African SMEs
  - Stripe/PayPal as secondary option

### 7.3 -- Production Deployment

- [ ] 7.3.1 -- Add Redis + Celery
  - Redis for caching (frequent report queries, dashboard KPIs)
  - Celery for background tasks: PDF generation, email sending, report pre-computation
- [ ] 7.3.2 -- Configure Nginx + Gunicorn (deploy/nginx.conf, deploy/gunicorn_config.py)
- [ ] 7.3.3 -- Create Docker setup
  - Dockerfile for Flask app
  - docker-compose.yml with app, PostgreSQL, Redis, Celery worker
- [ ] 7.3.4 -- Add health check endpoint (GET /health)
  - Returns DB connectivity, queue status, version
- [ ] 7.3.5 -- Add structured logging
  - Use Python's logging with JSON formatter for production log aggregation

### 7.4 -- Access Control & Audit

- [ ] 7.4.1 -- Full RBAC implementation
  - Permissions per role: can_create_invoice, can_approve_purchase, can_view_reports, etc.
  - Admin panel for user management
- [ ] 7.4.2 -- Audit trail UI
  - Searchable audit log filtered by business, user, action, date range

Phase 7 done criteria:
- [ ] New business can sign up and get isolated environment
- [ ] All queries scoped by business_id
- [ ] Subscription management functional (plan change, renewal)
- [ ] Docker Compose brings up full stack
- [ ] Nginx + Gunicorn serving in production mode
- [ ] RBAC enforced on all routes

---

## FUTURE / STRETCH GOALS

> From ARCHITECTURE.md section 14 -- not in phased roadmap but worth tracking.

- [ ] Mobile app (React Native or Flutter frontend)
- [ ] Bank reconciliation (import bank statements, match transactions)
- [ ] OCR receipt scanning (auto-capture expense data from photos)
- [ ] AI financial insights (anomaly detection, cash flow predictions)
- [ ] Multi-currency (FX rate handling, reporting in base currency)
- [ ] Offline-first PWA (service worker + IndexedDB for intermittent connectivity)
- [ ] WhatsApp notifications (invoice reminders, payment confirmations via WhatsApp Business API)
- [ ] Barcode scanning (for inventory receiving and sales checkout via device camera)

---

## APPENDIX: FILE MIGRATION MAP

> Mapping current monolithic files to their target Blueprint locations.

| Current File | Target Location (Phase 1) |
|---|---|
| app.py | Split into app/__init__.py + Blueprints under app/dashboard/, app/inventory/, app/purchases/, app/sales/, app/expenses/, app/reports/, app/settings/, app/auth/ |
| models.py | app/models/__init__.py + app/models/product.py, app/models/accounting.py, etc. |
| services/fifo_service.py (FIFO core) | app/services/inventory_service.py (Phase 3 expands it) |
| services/fifo_service.py (P&L/valuation) | app/services/reports/ (Phase 6) |
| services/fifo_service.py (tax) | app/services/accounting_service.py (Phase 2) |
| templates/ | app/*/templates/*/ (per Blueprint) or keep shared under app/templates/ |
| static/ | Keep shared under app/static/ |
| tests/test_fifo.py | tests/test_services/ + tests/test_routes/ |
| seed_demo_data() | seed.py or app/seed.py |

---

## GOLDEN RULES (from UPGRADE.md)

1. Never bypass accounting engine - all financial transactions go through accounting_service.post_entry()
2. Never store report values - reports are always computed from journal entries
3. Never directly edit ledger - no raw SQL updates to journal lines
4. Every transaction must balance - Debit = Credit, enforced at database level
5. Every table must include business_id - non-negotiable for multi-tenancy
