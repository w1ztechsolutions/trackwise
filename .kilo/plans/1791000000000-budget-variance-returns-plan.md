# Plan: Budget Planning, Excel Import, Variance Analysis, and Expenditure Returns

## Current State Summary

| Feature | Status | Key Files |
|---------|--------|-----------|
| Expense Budgets | Implemented (flat monthly per-account only) | `app/models/accounting.py:202`, `app/services/reports/expense_budget.py`, `migrations/versions/20260930_expense_budgets.py` |
| Budget vs Actual Variance | Implemented (expense accounts only) | `app/reports/routes.py:569-656`, `templates/reports.html:816-889`, `tests/test_expense_budgets.py` |
| Excel Export | Implemented (xlsx via raw zip+XML, no openpyxl) | `app/services/reports/xlsx_export.py`, `app/reports/routes.py:500-566` |
| Excel/CSV Import | Partial (CSV paste for bank statements only) | `app/accounting/routes.py:837-910`, `templates/bank_statement_import.html` |
| Journal Entry Reversal | Implemented (balanced opposite entry) | `app/services/accounting_service.py:157-206`, `app/accounting/routes.py:544-563`, `templates/journal_entry_view.html` |
| Sales Credit Notes / Refunds | Implemented (negative receipts + AR reversal) | `app/sales/routes.py:405-486`, `templates/credit_notes.html` |
| Purchase Returns / Bill Credit Notes | **Not implemented** | — |
| Expenditure/Payment Refunds | **Not implemented** | — |

## Architecture Context

- **Framework**: Flask 3.1, SQLAlchemy 2.0, Flask-Login, Flask-WTF (CSRF)
- **Data model split**: `app/models/` for newer modular models (accounting.py, inventory.py, approval.py), `models.py` at root for legacy models (Payment, Bill, Invoice, etc.)
- **Accounting primitives**: `post_entry()`, `reverse_entry()`, `post_opening_balance()` in `app/services/accounting_service.py`. All financial transactions post through these with `assert_period_open()` enforcement and audit logging via `app/services/audit_service.py` (before_flush/after_flush hooks)
- **Account codes**: Cash=1000, AR=1200, Inventory=1400, AP=2100, Tax Payable=2200, Revenue=4000, COGS=5000, Expenses=5100+ (`services/fifo_service.py:28-34`)
- **Dashboard**: `app/dashboard/routes.py` calls `get_profit_loss()` for sales/expenses data, renders Chart.js via `templates/dashboard.html` + `static/js/dashboard.js`
- **Audit**: All financial models tracked in `AUDITED_TABLES` set (`app/services/audit_service.py:10-50`), including `expense_budgets`. Period-close guard rejects mutations to closed periods.
- **Report exports**: Generic `export_report_xlsx` route (`app/reports/routes.py:500-566`) uses `build_report_rows()` in `xlsx_export.py`. Budget variance has a **separate** `export_expense_budget_variance` route.

## Decisions

1. **Budget model**: Replace flat `ExpenseBudget` with a unified `Budget` + `BudgetLineItem` model supporting revenue/expense types. Migrate existing rows. Keep old table read-only during transition.
2. **XLSX parsing**: Use the existing raw `zipfile` + `xml.etree.ElementTree` pattern from `xlsx_export.py` — no new dependencies (openpyxl is not in `requirements.txt`).
3. **Excel template downloads**: Generate template XLSX files using `create_xlsx()` from `xlsx_export.py` — pre-built templates with correct column headers for budgets, bills, suppliers, customers.
4. **Purchase returns**: New `PurchaseReturn` model that optionally links to a `Bill` and posts a reversing journal entry via `reverse_entry()` or `post_entry()`. Mirror the sales credit note pattern (Dr AP / Cr Expense or Dr AP / Cr Cash for refund).
5. **Dashboard charts**: Use existing Chart.js setup. Add a "Budget vs Actual" bar chart showing expense budget vs actual for the current month, plus a line chart for monthly budget utilization trend.
6. **Reports UI integration**: Add an "Expenditure Returns" report page to `reports.html` showing all purchase returns with filtering, and add budget variance to the AP aging report.

## Open Questions (resolved)

- Q: Should budgets support approval workflows?
  A: **No for v1.** Reuse existing approval framework if needed later; budgets set by admin/accountant roles.
- Q: Should Excel import support column mapping?
  A: **Yes.** Two-tier approach: (a) template XLSX download ensures format consistency, (b) column-mapping UI for ad-hoc imports.
- Q: Should purchase returns use approval workflow?
  A: **Yes** — mirror payment approvals. Returns > threshold require admin approval.
- Q: Should expenditure refunds reverse at the Payment level or Bill level?
  A: **Bill level.** If a payment exists, the return creates a new negative AP entry + optional cash refund. Payment-level refund reverses the payment's JE directly.
- Q: Should the dashboard chart pull from budget tables or from the variance service?
  A: **Budget tables via the variance service.** Use `get_expense_budget_variance()` for current month; historical trend via direct budget/actual queries.

## Task List

### Phase 1: Budget Model Expansion

#### 1.1. Create `Budget` and `BudgetLineItem` models
- **File**: `app/models/accounting.py`
- **Schema**:
  - `Budget` table: `id`, `business_id` (FK→businesses, CASCADE), `name` (String), `budget_type` (String — 'revenue'/'expense'), `period_start` (Date), `period_end` (Date), `status` (String — 'draft'/'approved'/'archived'), `created_by`, `created_at`
  - `BudgetLineItem` table: `id`, `budget_id` (FK→budgets, CASCADE), `account_id` (FK→chart_of_accounts, CASCADE), `cost_center_id` (FK→cost_centers, nullable), `amount` (Numeric 14,2), `notes` (Text, nullable)
  - Constraint: unique `(budget_id, account_id, cost_center_id)`
- Export both from `app/models/__init__.py`
- **Migration**: `migrations/versions/20261001_budget_planning.py` (creates tables, backfills from `expense_budgets`, adds `last_closed_period_date` if not present)

#### 1.2. Create budget service layer
- **File**: `app/services/budget_service.py` (new)
- Functions:
  - `create_budget(business_id, name, budget_type, period_start, period_end, lines, created_by=None)` — validates period, account types match budget_type (revenue budget → revenue accounts only; expense budget → expense accounts, excluding COGS code 5000), amounts finite and non-negative
  - `get_budget_lines(budget_id)` — fetch budget with all line items and computed actuals (reuse pattern from `get_expense_budget_variance`)
  - `compute_actuals(business_id, account_ids, cost_center_id, period_start, period_end)` — extracted helper for actual spending/revenue from journal lines (debit - credit for expense, credit - debit for revenue)
  - `get_monthly_budget_vs_actual(business_id, period_start)` — returns current month budgets and actuals for dashboard/chart use (thin wrapper calling `get_expense_budget_variance` + new revenue budget variance)

#### 1.3. Add budget variance route + UI
- **File**: `app/reports/routes.py` — add `GET/POST /reports/budget-variance` route (admin/accountant only)
  - GET: render budget variance page (revenue + expense sections, period selector)
  - POST: create/update budgets (budget_name, budget_type, line items: account_id + amount)
  - Export: `GET /reports/budget-variance/export.xlsx` — extend `build_report_rows()` to handle `budget_variance` type
- **File**: `app/services/reports/xlsx_export.py` — add `budget_variance` case to `build_report_rows()`
- **Template**: `templates/reports.html` — add new `budget_variance` section to the report selector (`<option value="{{ url_for('reports.budget_variance') }}">Budget Variance</option>`) and a template block

#### 1.4. Add Excel template download for budget import
- **File**: `app/reports/routes.py` — add `GET /reports/budget-variance/template.xlsx`
  - Generates a template XLSX with columns: `Account Code`, `Account Name`, `Budget Type`, `Amount`, `Cost Center Code` (optional)
  - Uses `create_xlsx()` from `xlsx_export.py`
  - Pre-fills with active chart of accounts rows (budget type inferred from account type, amount empty)
- **Template**: `templates/reports.html` — add "Download Budget Template" button in the budget variance section
- **Import route**: `POST /reports/budget-variance/import` — accepts XLSX, parses with raw XML approach, validates, creates `Budget` + `BudgetLineItem` records in a single transaction

#### 1.5. Migrate existing expense budgets
- Migration converts each `ExpenseBudget` row → `Budget` (type='expense', name=f"Auto: {account.code} {period_start}") + single `BudgetLineItem` (account_id, amount)
- Old `expense_budgets` table kept but writes disabled; future saves go through new `budget_service.create_budget()`

#### 1.6. Tests
- **File**: `tests/test_budgets.py` (new)
- Cover: create revenue budget (wrong account type rejected), create expense budget (COGS rejected), variance calculation, budget line uniqueness, template download returns valid xlsx, import from xlsx

### Phase 2: Excel Import Enhancement

#### 2.1. Create XLSX parsing utility
- **File**: `app/services/xlsx_import.py` (new)
- `parse_xlsx_file(file_storage)` — reads uploaded XLSX from `request.files`, extracts shared strings + sheet data using `zipfile` + `xml.etree.ElementTree`, returns `(sheet_names, rows_as_dicts)`
- Reuses namespace constants from `xlsx_export.py` (extract common constants to a shared module or duplicate)

#### 2.2. Create import service
- **File**: `app/services/import_service.py` (new)
- Functions:
  - `import_bank_statements(business_id, account_id, rows)` — maps columns: `date`, `amount`, `description`, `reference` → `BankStatement` model
  - `import_journal_entries(business_id, rows)` — maps columns: `date`, `description`, `account_code`, `debit`, `credit` → posts via `post_entry()`
  - `import_suppliers(business_id, rows)` — maps columns: `name`, `email`, `phone`, `address`, `tax_id` → `Supplier` model
  - `import_customers(business_id, rows)` — maps columns: `name`, `email`, `phone`, `address`, `tax_id` → `Customer` model

#### 2.3. Add import routes + column mapping UI
- **File**: `app/accounting/routes.py` — replace/extend `bank_statement_import` to support XLSX file upload (in addition to CSV paste). Add GET route that renders column-mapping form after file upload, POST that processes mapped data.
- **File**: `app/purchases/routes.py` — add `/purchases/import/suppliers` (GET form + POST process)
- **File**: `app/sales/routes.py` — add `/sales/import/customers` (GET form + POST process)
- **File**: `app/accounting/routes.py` — add `/accounting/import/journal-entries` (admin/accountant only)

#### 2.4. Add import templates
- **File**: `templates/import_wizard.html` — generic template with file upload, sheet selection, column mapping table, preview of first 10 rows, submit button
- **File**: `templates/bank_statement_import.html` — modify to add file upload option alongside CSV paste

#### 2.5. Duplicate detection
- For bank statements: check existing `reference` field before importing; flag duplicates, skip them, report count
- For suppliers/customers: check existing `name` + `email` combination; flag duplicates

#### 2.6. Tests
- **File**: `tests/test_imports.py` (new)
- Cover: parse valid xlsx, reject invalid column mapping, duplicate detection, supplier import creates records, journal entry import posts balanced entries

### Phase 3: Variance Analysis Enhancement

#### 3.1. Generalize variance engine
- **File**: `app/services/reports/expense_budget.py` → **refactor to** `app/services/reports/budget_variance.py`
- `get_budget_variance(budget_id)` — works for both revenue and expense budgets, returns line items with budget, actual, variance, percent_used
- `get_expense_budget_variance(business_id, period_start)` — keep as backward-compatible wrapper that delegates to new engine (creates a synthetic Budget from ExpenseBudget records, or reads from new Budget table post-migration)
- `get_period_comparison(business_id, account_ids, periods)` — for period-over-period variance

#### 3.2. Add variance to report exports
- Update `export_expense_budget_variance` route to use new variance engine
- Add budget variance to generic `export_report_xlsx` route via `build_report_rows()`

#### 3.3. Tests
- Extend `tests/test_expense_budgets.py` with revenue variance, period-over-period tests
- New tests in `tests/test_budgets.py` for general revenue/expense variance

### Phase 4: Expenditure Returns (Purchase Returns / Bill Credit Notes)

#### 4.1. Create `PurchaseReturn` model
- **File**: `app/models/accounting.py`
- **Schema**:
  - `PurchaseReturn` table: `id`, `business_id` (FK→businesses, CASCADE), `bill_id` (FK→bills, nullable), `supplier_id` (FK→suppliers, nullable), `return_date` (DateTime), `amount` (Numeric 14,2), `reason` (Text), `return_type` (String — 'credit_note'|'refund'), `is_applied_to_ap` (Boolean, default False), `journal_entry_id` (FK→journal_entries, nullable), `is_reversed` (Boolean, default False), `created_by`, `created_at`
  - Relationship: `bill`, `supplier`, `journal_entry`
  - Add to `AUDITED_TABLES` in `audit_service.py`
- **Migration**: `migrations/versions/20261001_expenditure_returns.py`

#### 4.2. Create return service
- **File**: `app/services/purchase_return_service.py` (new)
- `process_purchase_return(business_id, bill_id, amount, reason, return_type, created_by=None)`:
  - Validates: amount ≤ remaining bill balance (bill.total_amount - sum of approved payments)
  - Creates `PurchaseReturn` record
  - Posts journal entry: Dr Accounts Payable (2100), Credit Expense account (reverses expense) — for credit_note type. For refund type: Dr AP, Credit Cash (1000).
  - Reuses `post_entry()` and `reverse_entry()` from `accounting_service.py`
- `get_purchase_return_by_id(business_id, return_id)` — fetch with relationships for display

#### 4.3. Add purchase returns routes
- **File**: `app/purchases/routes.py`:
  - `GET/POST /purchases/returns/new` — form: bill_id (dropdown of received bills from this supplier), amount (auto-filled from bill total, editable), reason, return_type (credit_note | refund)
  - `GET /purchases/returns` — list all returns with filter by date/supplier
  - `GET /purchases/returns/<id>` — detail view showing original bill, return amount, reversal journal entry
  - `POST /purchases/returns/<id>/reverse` — reverse the return (reverses the reversal JE)

#### 4.4. Add expenditure returns to reports UI
- **File**: `app/reports/routes.py` — add `GET /reports/expenditure-returns` route
  - Lists all purchase returns for the business within a date range
  - Filters by supplier, return_type
  - Shows: return date, supplier, bill number, amount, type, reason, JE link
- **File**: `templates/reports.html` — add new report option to selector: "Expenditure Returns"
- **File**: `app/reports/routes.py` — add `GET /reports/expenditure-returns/export.xlsx` for export
- **File**: `app/services/reports/xlsx_export.py` — add `expenditure_returns` case to `build_report_rows()`

#### 4.5. Wire purchase returns into AP aging
- **File**: `app/services/reports/ap_aging.py` — modify `get_ap_aging()` to subtract purchase returns from outstanding bill balances. Import `PurchaseReturn` model, sum returns by `bill_id`, subtract from bill total before computing outstanding balance.

#### 4.6. Tests
- **File**: `tests/test_purchase_returns.py` (new)
- Cover: create credit note return, reject over-return, refund posts correct JE, AP aging reflects returns, returns page loads, list filters work

### Phase 5: Dashboard Budget vs Actual Charts

#### 5.1. Extend dashboard route
- **File**: `app/dashboard/routes.py` — add budget data to `dashboard()` function
  - Import `get_expense_budget_variance` from `app.services.reports`
  - For current month: fetch budget vs actual for expense accounts (reuse existing function)
  - For last 6 months: query `Budget`/`BudgetLineItem` tables for monthly totals, compute actuals per month
  - Pass `chart_labels`, `chart_budget`, `chart_actual` to template
- Add a budget summary helper: `get_dashboard_budget_summary(business_id, period_start)` in `budget_service.py`

#### 5.2. Add budget chart to dashboard template
- **File**: `templates/dashboard.html`
  - Add new chart card: "Budget vs Actual (Current Month)" — bar chart with budget vs actual per expense account
  - Add new chart card: "Monthly Budget Utilization Trend" — line chart showing % utilization over last 6 months
- **File**: `templates/dashboard.html` — add JSON data block in `{% block scripts %}`:
  ```json
  {
    "labels": {{ chart_labels | tojson }},
    "budget": {{ chart_budget | tojson }},
    "actual": {{ chart_actual | tojson }}
  }
  ```
- **File**: `static/js/dashboard.js` — add Chart.js chart creation for budget vs actual (bar chart) and trend (line chart), matching existing chart style

#### 5.3. Tests
- **File**: `tests/test_dashboard.py` (new or extend existing)
- Cover: dashboard returns 200, budget chart data present in JSON block, budget data reflects set budgets

### Phase 6: Payment Refund Support (Expenditure Refunds)

#### 6.1. Add payment reversal fields
- **File**: `models.py` — `Payment` model: add `is_reversed` (Boolean, default False), `reversal_reason` (String 255, nullable), `reversal_date` (DateTime, nullable)

#### 6.2. Create payment refund service
- **File**: `app/services/accounting_service.py` — add `reverse_payment(business_id, payment_id, reason, created_by=None, reversal_date=None)`
  - Looks up payment, finds the journal entry with `reference_type='Payment'` and `reference_id=payment_id`
  - Calls `reverse_entry()` to post opposite entry
  - Sets `payment.is_reversed = True`, `reversal_reason`, `reversal_date`
  - Raises if already reversed

#### 6.3. Add refund route
- **File**: `app/purchases/routes.py` — `POST /payments/<id>/refund`
  - Form: reason, refund_amount (full or partial)
  - For partial: post a proportional reversing entry (Dr Cash/Cr AP partial)
  - For full: call `reverse_payment()`
  - Requires admin role

#### 6.4. Tests
- Extend `tests/test_accounting.py` or new file
- Cover: full refund reverses payment JE, partial refund posts partial reversal, doubled refund rejected

---

## Affected Boundaries

| Boundary | Change |
|----------|--------|
| `app/models/accounting.py` | Add `Budget`, `BudgetLineItem`, `PurchaseReturn` models |
| `app/models/__init__.py` | Export new models |
| `models.py` | Add `is_reversed`, `reversal_reason`, `reversal_date` to `Payment` |
| `app/services/reports/expense_budget.py` | Rename to `budget_variance.py`, generalize; keep backward compat |
| `app/services/budget_service.py` | **New** — `create_budget`, `get_monthly_budget_vs_actual` |
| `app/services/import_service.py` | **New** — all import type handlers |
| `app/services/xlsx_import.py` | **New** — XLSX parsing |
| `app/services/purchase_return_service.py` | **New** — `process_purchase_return` |
| `app/services/accounting_service.py` | Add `reverse_payment()` |
| `app/services/reports/ap_aging.py` | Subtract purchase returns from bill balances |
| `app/services/reports/xlsx_export.py` | Add `budget_variance` and `expenditure_returns` cases to `build_report_rows()` |
| `app/services/audit_service.py` | Add `purchase_returns`, `budgets`, `budget_line_items`, `payments` to AUDITED_TABLES |
| `app/reports/routes.py` | Add `/reports/budget-variance` (+ import + template download), `/reports/expenditure-returns` (+ export) |
| `app/accounting/routes.py` | Extend bank statement import to accept XLSX files |
| `app/purchases/routes.py` | Add `/purchases/returns/*`, `/payments/<id>/refund`, `/purchases/import/suppliers` |
| `app/sales/routes.py` | Add `/sales/import/customers` |
| `app/dashboard/routes.py` | Add budget vs actual data for charts |
| `templates/dashboard.html` | Add budget vs actual + trend chart cards + JSON data |
| `static/js/dashboard.js` | Add Chart.js chart creation for budget charts |
| `templates/reports.html` | Add budget variance and expenditure returns to report selector + template blocks |
| `templates/import_wizard.html` | **New** — generic import UI with column mapping |
| `templates/purchase_returns.html` | **New** — returns list view |
| `templates/purchase_return_form.html` | **New** — return creation form |
| `migrations/` | 3 new migration files: budgets, expenditure returns, payment reversals |
| `tests/` | New: `test_budgets.py`, `test_imports.py`, `test_purchase_returns.py`, `test_dashboard.py`; modify: `test_expense_budgets.py`, `test_accounting.py` |

## Data Flow

```
Excel File Upload (XLSX)
  → xlsx_import.parse_xlsx_file()
  → Column mapping (user-selected or template-matched)
  → import_service.import_<type>(business_id, rows)
  → Existing models (BankStatement, JournalEntry via post_entry, Supplier, Customer)
  → AuditLog auto-captures changes (existing framework)

Budget Creation (via UI or XLSX import)
  → budget_service.create_budget()
  → Budget + BudgetLineItem records
  → Budget variance computed from JournalLine actuals
  → Dashboard charts via get_monthly_budget_vs_actual()

Purchase Return
  → purchase_return_service.process_purchase_return()
  → PurchaseReturn model record
  → post_entry() with opposite JE (Dr AP / Cr Expense or Dr AP / Cr Cash)
  → AP aging adjusted in get_ap_aging()
  → Revenue/expenditure returns report lists all returns
```

## Failure Modes & Mitigations

| Failure Mode | Mitigation |
|--------------|------------|
| Import creates duplicate records | Check existing references before insert; flag and skip duplicates |
| Budget variance includes deleted journal entries | Filter `is_deleted=False` in variance queries (already done in existing code) |
| Partial refund exceeds original payment | Validate refund_amount ≤ remaining unreversed amount |
| Budget line references wrong account type | Validate account type matches budget_type in `create_budget()` |
| Import column mapping mismatch | Preview step shows mapped data; reject if required fields unmapped |
| Migration data loss when converting ExpenseBudget | Write a data migration that copies rows; keep old table read-only during transition |
| Period closed during import/budgeting | `assert_period_open` and `_guard_closed_periods` already enforced at `post_entry`; budget writes should also check period is open |
| Purchase return over-returns a bill | Validate amount ≤ bill total - approved payments |
| XLSX parsing fails on malformed file | Catch exceptions, return user-friendly error message with guidance |
| Dashboard chart performance on large datasets | Cache budget vs actual in report_tasks (Celery background task) similar to existing report caching |
| Purchase return reversed twice | Check `is_reversed` flag before allowing |
| AP aging excludes returns | Explicitly subtract `PurchaseReturn` amounts from bill balances in `ap_aging.py` |

## Rollout / Migration Path

1. Run migrations in order: budgets → expenditure returns → payment reversals
2. Backfill existing `ExpenseBudget` rows into new `Budget`/`BudgetLineItem` tables via migration
3. Add new models to `AUDITED_TABLES`
4. Deploy import endpoints behind admin/accountant roles; audit log captures all imports
5. Existing `expense_budget_variance` route continues to work via backward-compatible wrapper
6. New budget variance route coexists; old route deprecated but functional
7. No breaking API changes — all new endpoints are additive

## Validation Plan

- `pytest tests/test_expense_budgets.py` — existing budget tests must still pass
- `pytest tests/test_accounting.py` — existing reversal/period tests must pass
- `pytest tests/test_budgets.py` — new budget service tests
- `pytest tests/test_imports.py` — new import tests
- `pytest tests/test_purchase_returns.py` — new return tests
- `pytest tests/test_dashboard.py` — new dashboard tests
- `pytest tests/test_routes.py` — existing route tests must still pass (bank statement import, export tests, credit notes)
- Manual: upload budget template XLSX, verify budgets created
- Manual: download budget template, verify column structure
- Manual: create purchase return, verify AP aging decreases
- Manual: full refund on a payment, verify cash account reversed
- Manual: dashboard shows budget vs actual chart with correct data
- Manual: expenditure returns report loads and filters by supplier/date

## Out of Scope

- Revenue recognition adjustments (already partially implemented via `RevenueRecognitionSchedule`)
- Recurring transactions/templates
- Multi-currency support (budgets/returns assume single currency)
- Mobile/responsive UI improvements (template changes use existing Bootstrap 5 classes)
- Print stylesheets
- Public API exposure
- Approval workflow changes for returns (future enhancement)
