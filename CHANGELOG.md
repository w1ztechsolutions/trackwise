# Changelog

All notable changes to TrackWise are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- XLSX downloads for income statement, balance sheet, cash flow, trial balance, general ledger, cashbook, AR/AP aging, and audit trail reports
- Transaction audit coverage for business demo-workspace registry and subscription records, excluding stored payment-provider identifiers
- Audited ORM records can no longer be changed through bulk update/delete statements that bypass per-record audit events
- Transaction-level audit events for accounting, sales, purchasing, inventory movements, approvals, and user authentication actions
- Journal entry reversal workflow that posts a balanced counter-entry and retains the original entry
- Business-scoped period close through date with guards against writes to closed periods
- Time-based straight-line revenue deferral schedules for posted invoice sales
- Opt-in demo signup using a dedicated database, visitor-selected role, and generated internal user; repeat business names offer proceed-or-change flow
- Per-request ORM database routing keeps demo sessions on `DEMO_DATABASE_URL` and standard password login on `DATABASE_URL`
- `flask --app 'app:create_demo_migration_app' demo-db-bootstrap` for safely creating the current schema on an empty isolated demo database
- `.env.example` and `DEPLOY_VERCEL.md` guidance for the separate demo database configuration
- `demo_workspaces` registry with a unique normalized business name to prevent duplicate demo workspaces
- `docs/MIGRATION_2026-09_financial_controls.md` — rollout and migration guidance for accounting controls
- `docs/MIGRATION_2026-09_demo_workspace_database.md` — separate Neon demo database setup and isolation behavior
- `AGENT.md` — AI documentation enforcement rules for bug fixes, features, and architecture changes
- `SECURITY.md` — Security policy and deployment best practices
- `docs/OPERATIONS.md` — Operations runbook for utility scripts and common procedures
- `docs/ENVIRONMENT.md` — Environment variable reference
- `docs/DATABASE.md` — Database schema reference
- `docs/RELEASES.md` — Release process and versioning guide
- `docs/missing_documentation_audit.md` — Comprehensive documentation gap audit
- `LICENSE` — Proprietary license file
- Accounting blueprint (`app/accounting/`) with Chart of Accounts management and manual journal entries
- Bank reconciliation module (`/accounting/bank-reconciliation/*`) with register, statement import, match/unmatch, and unreconciled report
- `BankStatement` model for reconciliation line items
- Accounting soft-delete support (`is_deleted`, `deleted_by`, `deleted_at` on `journal_entries`)
- Fiscal year start configuration on `Business` model
- `fiscal_year_start` column migration for `businesses` table
- Invoice-to-sales linkage via `invoice_id` column on `sales` table
- `post_opening_balance()` service method for COA opening balances
- **Cashbook report** (`/reports/cashbook`) — chronological register of all Cash (1000) and Bank (1100) transactions with running balances, summary cards (opening/total receipts/total payments/closing), and date-range filtering
- `get_cashbook()` service in `app/services/reports/cashbook.py`
- `cashbook()` route in `app/reports/routes.py`
- Cashbook UI block in `templates/reports.html` with date-range filter and pagination
- `test_cashbook` unit test in `tests/test_reports.py`

### Changed

- Periods can be reopened by administrators only; the action requires confirmation and is audit-logged
- Manual user creation is unavailable in demo sessions; demo users are generated only by role selection in the demo entry flow
- Demo entry and duplicate-workspace pages now use a standalone responsive layout, local styles, and no application navigation
- Demo database bootstrap now uses ORM metadata and stamps Alembic heads through a demo-only app factory, avoiding production startup side effects and a legacy migration chain that is not fresh-install compatible
- AR/AP aging now subtracts linked receipts and approved bill payments as of the report date
- Income statement and dashboard tax figures are labelled as estimates and use the current business's configured rate
- Financial reports and ledger balance checks exclude soft-deleted journal entries
- Approval request creation moved from route modules into `app/services/approval_service.py`
- `.gitignore` — Removed `/docs/` entry so documentation is tracked by git
- `README.md` — Corrected project structure to reflect actual `app/models/` submodule layout
- `ARCHITECTURE.md` — Updated RBAC table: `accountant` role now references "accounting" instead of deprecated "expenses"
- `docs/API.md` — Expanded with authentication details, CORS notes, and improved endpoint documentation
- `docs/bugs_and_fixes.md` — Marked Bug 11 (`/register` 404) as resolved/deprecated

### Fixed

- Demo data seeding now assigns the active business to sample products and transactions, scopes cleanup/tax settings per workspace, and uses workspace-unique SKUs (see Bug 31)
- Removed extra Jinja block terminators that prevented the Inventory, Sales, and Payments pages from rendering in demo and production sessions (see Bug 30)
- Saved or system-preferred light mode is now applied before page stylesheets load, preventing a dark-theme flash during navigation (see Bug 29)
- Light-theme pages now use higher-contrast muted text, borders, status badges, and chart colors; the Dashboard chart's Chart.js asset integrity is corrected and updates its colors when the theme changes (see Bug 28)
- Removed an unmatched template block that prevented the Purchases page from rendering (see Bug 27)
- Starter-account picker controls, account details, and selected-account preview now have higher contrast in dark mode, with explicit readable colors in light mode (see Bug 26)
- Bootstrap CSS/JavaScript integrity hashes now match pinned CDN assets so Chart of Accounts dialogs open from their buttons instead of rendering inline; the starter-account picker is scrollable and full-screen on small screens (see Bug 25)
- Fresh demo database setup no longer fails on legacy migration assumptions about `uq_settings_key` and the absent `material_usages` table (see Bug 22)
- Audit coverage now records financial record create/update/delete operations and relevant login, logout, password, and approval changes (see Bug 14)
- Journal entries can be corrected by posting a reasoned reversal instead of deleting history (see Bug 16)
- AR/AP aging no longer reports gross invoice/bill amounts after linked payments (see Bug 15)
- Closed accounting periods reject postings and edits dated in the closed range (see Bug 17)
- Income statement tax estimates are tenant-scoped and are not presented as statutory tax provision (see Bug 18)
- Journal entry details render and expose reversal metadata (see Bug 19)
- Financial reports exclude soft-deleted journal entries (see Bug 21)
- `.gitignore` was ignoring the entire `docs/` directory, preventing documentation from being version-controlled
- Multi-tenant data isolation: users can no longer see or manipulate records from another business; dashboard, inventory, sales, purchases, and valuation queries are now scoped by `business_id`
- Bank reconciliation page: `bank_statements` table missing from database (Bug 12)

### Security

- Demo role switching is hidden and unavailable unless explicitly enabled; staging setup requires an intentional seed command and must not target production
- Audit event coverage includes authentication and permission-related user changes; ORM changes to existing audit records are rejected
- Added `SECURITY.md` with vulnerability reporting process and deployment security best practices
- CSP hardened: removed `'unsafe-inline'` from `script-src`, added per-request nonces, and added `object-src 'none'`
- SRI added to all external `<script>` and `<link>` tags (Chart.js, Bootstrap, Vercel Insights, Google Fonts, Bootstrap Icons)
- Inline event handlers replaced with `data-` attributes and external JS listeners to eliminate inline code dependencies

---

## [1.1.0] - 2026-08-16

### Added for [1.1.0]

- Payments Hub: unified payment management system
  - FinancialCategory and LineItem models for structured expense categorization
  - Staff model for employee/salary payments
  - Extended Payment model with category, line item, payee type, and description fields
  - `_post_payment_accounting()` service method for automatic journal entry creation
  - `/payments` route with full CRUD for supplier and staff payments
  - Dashboard integration with Recent Payments table
  - `/expenses` route deprecated and redirects to `/payments`
- Database migration script (`scripts/migrate.py`) for Payments Hub schema changes
- Comprehensive Payments Hub documentation (`docs/PAYMENTS_HUB.md`)

### Changed for [1.1.0]

- Payment model: renamed `payment_method` to `payment_mode`, added expanded payment modes (cash, bank_transfer, mobile_money, cheque, card)
- Dashboard: replaced Expenses table with Payments table
- Seed data: added financial categories and line items

### Fixed for [1.1.0]

- Accounting integration for supplier payments (Debit AP, Credit Cash)
- Accounting integration for staff/expense payments (Debit Expense, Credit Cash)

---

## [1.0.1] - 2026-07-21

### Added for [1.0.1]

- Superadmin CLI command: `flask create-superadmin` for bootstrapping platform administrators
- Superadmin blueprint templates (`sa_login.html`, `sa_dashboard.html`, `sa_businesses.html`, `sa_business_form.html`, `sa_admins.html`, `sa_admin_form.html`, `sa_users.html`)
- Superadmin mobile hamburger navigation with overlay and slide-in sidebar
- CSP header updates to allow `cdn.jsdelivr.net` styles and `cdn.vercel-insights.com` scripts
- Bootstrap Icons integration for superadmin dashboard KPI cards

### Changed for [1.0.1]

- `ProductionConfig` now exposes `SECRET_KEY` as a class attribute (fixes session initialization in production)
- KPI card grid layout changed from fixed 5-column to `repeat(auto-fit, minmax(180px, 1fr))` for responsive behavior

### Fixed for [1.0.1]

- RuntimeError: No secret key set in production (Bug 1)
- BuildError: `auth.register` endpoint does not exist (Bug 2)
- Missing superadmin templates causing 500 errors (Bug 3)
- Superadmin login returning "Invalid credentials" with correct credentials due to missing superadmin user (Bug 4)
- Database schema mismatch: missing `created_by_superadmin_id` and `must_change_password` columns (Bug 5)
- Superadmin dashboard KPI icons not rendering (Bug 6)
- Main dashboard KPI cards overflowing with large numbers (Bug 7)
- Superadmin mobile navigation has no hamburger menu (Bug 8)
- Content Security Policy blocking Bootstrap Icons and Vercel Analytics (Bug 9)
- `/register` route returns 404 (Bug 10)

---

## [1.0.0] - 2026-07-09

### Added for [1.0.0]

- Initial production release
- Double-entry accounting engine with journal entries and ledger
- FIFO inventory costing with multi-warehouse support
- Sales and purchase management (invoices, bills, receipts, payments)
- Production system with raw material consumption and finished goods output
- Financial reports: Income Statement, Balance Sheet, Cash Flow, Trial Balance, General Ledger, AR/AP Aging
- Multi-tenant SaaS architecture with `business_id` scoping
- Role-based access control (admin, accountant, cashier, storekeeper, viewer)
- Subscription management (Free, Starter, Business, Enterprise plans)
- Vercel serverless deployment support
- Nginx + Gunicorn production setup
- Celery + Redis background task processing
- Structured JSON logging
- Health check endpoint (`/health`)
- Vercel deployment support (`DEPLOY_VERCEL.md`)
- Comprehensive test suite (FIFO, accounting, reports, inventory, production)

---

## [Unreleased v2]

### Planned

- Mobile app (React Native / Flutter)
- Bank reconciliation
- OCR receipt scanning
- AI financial insights
- Multi-currency support
- Offline-first PWA mode
- Enhanced API documentation with OpenAPI/Swagger
