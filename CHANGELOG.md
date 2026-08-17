# Changelog

All notable changes to TrackWise are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
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

### Changed
- `.gitignore` — Removed `/docs/` entry so documentation is tracked by git
- `README.md` — Corrected project structure to reflect actual `app/models/` submodule layout
- `ARCHITECTURE.md` — Updated RBAC table: `accountant` role now references "accounting" instead of deprecated "expenses"
- `docs/API.md` — Expanded with authentication details, CORS notes, and improved endpoint documentation
- `docs/bugs_and_fixes.md` — Marked Bug 10 (`/register` 404) as resolved/deprecated

### Fixed
- `.gitignore` was ignoring the entire `docs/` directory, preventing documentation from being version-controlled
- Multi-tenant data isolation: users can no longer see or manipulate records from another business; dashboard, inventory, sales, purchases, and valuation queries are now scoped by `business_id`

### Security
- Added `SECURITY.md` with vulnerability reporting process and deployment security best practices

---

## [1.1.0] - 2026-08-16

### Added
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

### Changed
- Payment model: renamed `payment_method` to `payment_mode`, added expanded payment modes (cash, bank_transfer, mobile_money, cheque, card)
- Dashboard: replaced Expenses table with Payments table
- Seed data: added financial categories and line items

### Fixed
- Accounting integration for supplier payments (Debit AP, Credit Cash)
- Accounting integration for staff/expense payments (Debit Expense, Credit Cash)

---

## [1.0.1] - 2026-07-21

### Added
- Superadmin CLI command: `flask create-superadmin` for bootstrapping platform administrators
- Superadmin blueprint templates (`sa_login.html`, `sa_dashboard.html`, `sa_businesses.html`, `sa_business_form.html`, `sa_admins.html`, `sa_admin_form.html`, `sa_users.html`)
- Superadmin mobile hamburger navigation with overlay and slide-in sidebar
- CSP header updates to allow `cdn.jsdelivr.net` styles and `cdn.vercel-insights.com` scripts
- Bootstrap Icons integration for superadmin dashboard KPI cards

### Changed
- `ProductionConfig` now exposes `SECRET_KEY` as a class attribute (fixes session initialization in production)
- KPI card grid layout changed from fixed 5-column to `repeat(auto-fit, minmax(180px, 1fr))` for responsive behavior

### Fixed
- RuntimeError: No secret key set in production (Bug 1)
- BuildError: `auth.register` endpoint does not exist (Bug 2)
- Missing superadmin templates causing 500 errors (Bug 3)
- Superadmin login returning "Invalid credentials" with correct credentials due to missing superadmin user (Bug 4)
- Database schema mismatch: missing `created_by_superadmin_id` and `must_change_password` columns (Bug 5)
- Superadmin dashboard KPI icons not rendering (Bug 6)
- Main dashboard KPI cards overflowing with large numbers (Bug 7)
- Superadmin mobile navigation has no hamburger menu (Bug 8)
- Content Security Policy blocking Bootstrap Icons and Vercel Analytics (Bug 9)

---

## [1.0.0] - 2026-07-09

### Added
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

## [Unreleased]

### Planned
- Mobile app (React Native / Flutter)
- Bank reconciliation
- OCR receipt scanning
- AI financial insights
- Multi-currency support
- Offline-first PWA mode
- Enhanced API documentation with OpenAPI/Swagger
