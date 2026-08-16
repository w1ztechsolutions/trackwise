# Changelog

All notable changes to TrackWise are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Vercel serverless deployment support- Nginx + Gunicorn production setup
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

