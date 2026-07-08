# TRACKWISE UPGRADE ROADMAP (FLASK SAAS EVOLUTION)

## 1. PURPOSE
TrackWise is evolving from a simple Flask expense tracker into a full SME business management system with:

- Double-entry accounting
- Inventory management
- Production system (cement block manufacturing)
- Multi-tenant SaaS support
- Financial reporting engine

---

## 2. CURRENT STATE (MVP)

### What Exists
- **Flask + SQLAlchemy application** with SQLite database
- **FIFO inventory costing engine** — purchase layers tracked via `StockTransaction.remaining_quantity`; sales consume from oldest layers first for accurate COGS
- **Product management** with SKU, description, stock quantity, low-stock threshold, and default selling price
- **Purchase order entry** — multi-item purchase intake with supplier, date, notes, and automatic FIFO layer creation
- **Sales checkout** — multi-item sales with real-time stock validation, auto COGS calculation via FIFO, and tax computation
- **Expense tracking** — categorized operating expenses (rent, utilities, salaries, marketing, etc.)
- **Profit & Loss reporting** — date-range filterable income statement with gross profit, pre-tax profit, tax provision, and net profit
- **Dashboard** — KPI cards (revenue, COGS, gross profit, expenses, net profit), Chart.js line chart (sales vs expenses, 6-month view), inventory valuation summary, low-stock alerts, and recent activity tables
- **Reports page** — full income statement with operating expense doughnut chart (Chart.js) and inventory asset valuation
- **Settings** — configurable flat tax rate, seed demo data feature
- **Inventory valuation report** — calculates current stock asset value using remaining FIFO cost layers
- **Unit tests** (`tests/test_fifo.py`) — 3 test cases covering product creation, FIFO inventory + full P&L scenario, and insufficient inventory rejection
- **Dark-themed glassmorphism UI** — fixed sidebar navigation, custom CSS with CSS variables, responsive flash messages with auto-dismiss, modals, and custom scrollbars

### Known Gaps & Technical Debt

| Area | Limitation |
|------|-----------|
| **Security** | No authentication/authorization (anyone with server access sees all financial data); hardcoded `SECRET_KEY`; no CSRF protection |
| **Database** | SQLite (not production-safe for concurrent SME usage); no connection pooling |
| **Architecture** | Monolithic `app.py` (routes + seed data interleaved); no Blueprints; no application factory pattern |
| **Accounting** | Single-entry tracking only (no double-entry, no journal entries, no chart of accounts, no ledger) |
| **Inventory** | No warehouse/multi-location support; no batch/lot tracking beyond FIFO layers |
| **Sales/Purchases** | No formal invoicing; no payment tracking; no customer/supplier accounts receivable/payable |
| **Production** | Not yet built (cement block manufacturing is a future phase) |
| **Reporting** | Only P&L statement; no Balance Sheet, Cash Flow, Trial Balance, or general ledger reports. Reports compute from direct queries rather than derived from journal entries |
| **Multi-tenancy** | Single-tenant only; no `business_id` isolation |
| **Testing** | Only 3 unit tests; no integration tests (no route/endpoint testing with `app.test_client()`); no edge-case coverage for empty DB, date range filtering, or cross-FIFO-layer sales |
| **UI/UX** | No mobile responsiveness; no pagination on list views; no loading states on form submission |

## 3. UPGRADE GOAL

Transform TrackWise into:

> SME Accounting + Inventory + Production + Reporting SaaS Platform

---

## 4. PHASED ROADMAP

### PHASE 1 — FOUNDATION (MVP STABILIZATION)
- Refactor Flask into Blueprints
- Introduce service layer
- Add PostgreSQL
- Clean separation of concerns

---

### PHASE 2 — ACCOUNTING ENGINE (CRITICAL)
Introduce double-entry accounting:

Every transaction must generate:

- Debit entry
- Credit entry

Modules:
- Chart of Accounts
- Journal Entries
- Ledger Posting

RULE:
No direct updates to reports or balances.

---

### PHASE 3 — INVENTORY SYSTEM
- Stock tracking (in/out movements)
- Product management
- Warehouse support
- Stock valuation

---

### PHASE 4 — SALES & PURCHASES
- Customers
- Suppliers
- Invoices
- Receipts
- Purchase orders
- Payment vouchers

---

### PHASE 5 — PRODUCTION SYSTEM
(Designed for cement block businesses)

- Production batches
- Raw material consumption
- Finished goods output
- Automatic stock updates
- Accounting integration

---

### PHASE 6 — REPORTING ENGINE
All reports must be derived from journal entries:

- Income Statement
- Balance Sheet
- Cash Flow Statement
- Trial Balance
- Ledgers
- Customer statements
- Supplier statements

RULE:
No stored report values.

---

### PHASE 7 — SAAS READINESS
- Multi-tenant architecture (business_id isolation)
- Role-based access control
- Subscription system
- Audit logging

---

## 5. GOLDEN RULES

1. Never bypass accounting engine  
2. Never store report values  
3. Never directly edit ledger  
4. Every transaction must balance (Debit = Credit)  
5. Every table must include business_id  

---

## 6. FINAL VISION

TrackWise evolves into:

- SME Accounting System
- Inventory Platform
- Production Management System
- Lightweight ERP for African businesses
- Scalable SaaS product
