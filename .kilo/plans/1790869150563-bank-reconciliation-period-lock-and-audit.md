# Bank Reconciliation Period Lock & Audit Plan

## Goal
Add period-lock controls to bank reconciliation and ensure all reconciliation actions are audited.

## Current State
- **Business period close**: `Business.last_closed_period_date` enforced by `_guard_closed_periods` in `audit_service.py` for tables in `PERIOD_DATE_FIELDS`
- **Bank reconciliation**: `BankStatement` model with `is_reconciled`, `journal_entry_id`; routes for import/match/unmatch
- **Audit**: `bank_statements` ∈ `AUDITED_TABLES` → ORM CREATE/UPDATE/DELETE auto-audited; no explicit `record_user_action` for match/unmatch

## Design Decisions (Resolved)

### 1. Period Lock for Bank Reconciliation
**Decision**: Two-layer lock mechanism
- **Layer 1 (General)**: Add `bank_statements` to `PERIOD_DATE_FIELDS` with `statement_date`. This makes the existing business period close (`last_closed_period_date`) block any INSERT/UPDATE on `BankStatement` rows whose `statement_date` falls in a closed period. Covers import + match + unmatch + direct ORM.
- **Layer 2 (Dedicated)**: New `BankReconciliationPeriod` model tracking locked reconciliation periods **per bank account**. Enforces "cannot reconcile a month twice" at the reconciliation-workflow level (independent of the general close date). Unique constraint on `(business_id, account_id, period_end)` prevents duplicate month locks.

Rationale: The general close is business-wide and blocks all financial writes; the dedicated lock is per-account and specifically governs the reconciliation workflow. Both are needed for defense-in-depth and to match the user's explicit "cannot reconcile a month twice" requirement.

### 2. Audit Coverage
- ORM changes to `BankStatement` already audited via existing listeners (`bank_statements` ∈ `AUDITED_TABLES`).
- Add explicit `record_user_action` calls for:
  - `bank_match` / `bank_unmatch` routes (action: `BANK_RECONCILE_MATCH` / `BANK_RECONCILE_UNMATCH`)
  - New reconciliation period lock/unlock routes (action: `BANK_RECON_PERIOD_LOCK` / `BANK_RECON_PERIOD_UNLOCK`)
  - Bank statement import already audited via `commit_import`/`fail_import` in `import_run_service.py` (uses `IMPORT_BANK_STATEMENTS` action)

## Implementation Tasks

### A. Schema & Model Changes
1. **Migration**: Add `BankReconciliationPeriod` table
   - Columns: `id`, `business_id` (FK businesses, cascade), `account_id` (FK chart_of_accounts), `period_end` (Date), `closed_by` (FK users, SET NULL), `closed_at` (DateTime), `reopened_by` (FK users, SET NULL), `reopened_at` (DateTime), `is_locked` (Boolean, default True)
   - Unique constraint: `(business_id, account_id, period_end)`
   - Indexes: `business_id`, `account_id`, `is_locked`
2. **Model**: Add `BankReconciliationPeriod` class in `app/models/accounting.py`
3. **Period Date Fields**: Add `"bank_statements": "statement_date"` to `PERIOD_DATE_FIELDS` in `app/services/audit_service.py`

### B. Service Layer
4. **New service module**: `app/services/reconciliation_period_service.py`
   - `assert_reconciliation_open(business_id, account_id, statement_date)` → raises `ReconciliationPeriodClosedError` if a locked period covers the date
   - `close_reconciliation_period(business_id, account_id, period_end, user_id)` → creates locked row, validates not future, not duplicate, sequential (optional)
   - `reopen_reconciliation_period(business_id, account_id, period_end, user_id)` → admin only, sets `is_locked=False`, records reopened_by/at

### C. Route Changes
5. **`bank_match` / `bank_unmatch`** (`app/accounting/routes.py`):
   - Before commit: call `assert_reconciliation_open(biz_id, stmt.account_id, stmt.statement_date)`
   - Call `record_user_action(biz_id, current_user.id, 'BANK_RECONCILE_MATCH', 'bank_statements', stmt.id, {'journal_entry_id': entry.id})` (and UNMATCH equivalent)
6. **`import_bank_statements`** (`app/services/import_service.py`): call `assert_reconciliation_open` for each imported statement's date (or rely on Layer 1 guard — prefer explicit check for clearer error message)
7. **New routes** (`app/accounting/routes.py`):
   - `GET/POST /accounting/bank-reconciliation/periods/<account_id>` — list/close reconciliation periods for an account
   - `POST /accounting/bank-reconciliation/periods/<account_id>/<period_end>/reopen` — admin only, reopen
   - UI: simple table showing months, status (locked/open), close/reopen actions

### D. Audit Integration
8. **Explicit audit actions** in routes above (see Step 5, 7)
9. **No changes needed** to `_guard_closed_periods` — Layer 1 works automatically once `PERIOD_DATE_FIELDS` is updated

### E. Tests
10. **Period lock tests** (`tests/test_accounting.py`):
    - General close: import/match in closed business period → `PeriodClosedError`
    - Dedicated lock: match in locked reconciliation period → `ReconciliationPeriodClosedError`
    - Duplicate month lock rejected (unique constraint)
    - Reopen (admin) then match again
11. **Audit tests** (`tests/test_reports.py` / `tests/test_accounting.py`):
    - `bank_match` / `bank_unmatch` produce `AuditLog` entries with correct action, record_id, details
    - Reconciliation period lock/unlock audited

### F. Templates
12. **New template**: `templates/bank_reconciliation_periods.html` — list periods, close/reopen buttons
13. **Update**: `bank_reconciliation.html` — link to reconciliation periods per account

## File Impact Map
| File | Change |
|------|--------|
| `migrations/versions/XXXX_add_bank_reconciliation_periods.py` | New |
| `app/models/accounting.py` | Add `BankReconciliationPeriod` model |
| `app/services/audit_service.py` | Add `"bank_statements": "statement_date"` to `PERIOD_DATE_FIELDS` |
| `app/services/reconciliation_period_service.py` | New service module |
| `app/accounting/routes.py` | Modify `bank_match`, `bank_unmatch`; add period lock routes |
| `app/services/import_service.py` | Call `assert_reconciliation_open` in `import_bank_statements` |
| `templates/bank_reconciliation_periods.html` | New template |
| `templates/bank_reconciliation.html` | Add "Periods" link per account |
| `tests/test_accounting.py` | Period lock tests |
| `tests/test_reports.py` / `tests/test_accounting.py` | Audit action tests |

## Validation Plan
1. Run existing test suite — ensure no regressions
2. New tests pass: period lock enforcement, audit records created
3. Manual smoke test:
   - Import statements dated in open period → success
   - Close business period through date → import/match in closed period → blocked
   - Close reconciliation period for account/month → match in that month → blocked
   - Attempt to close same month twice → blocked (unique constraint)
   - Admin reopen → match again allowed
   - Verify `AuditLog` rows for match/unmatch/lock/unlock with correct details

## Risks / Open Questions
- **Sequential close enforcement**: Should `close_reconciliation_period` require periods to be closed in order (e.g., can't close March before February)? Recommend: yes, add optional validation.
- **Import in closed reconciliation period**: Should import be blocked? Recommend: yes (consistency with match), but import might be needed for historical statements. Decision: block via `assert_reconciliation_open` in import service.
- **Period granularity**: `period_end` = last day of month. Users may expect month-based UI. Implement UI that computes month from `period_end` and only allows month-end dates.