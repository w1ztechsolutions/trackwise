# Fix Excel Import Data Loss and Audit Logging Gaps

## Context

A review of the XLSX import pipeline and the audit trail found nine import defects
(E1–E8) and four audit defects (A1–A4). All were reproduced by execution, not inferred
from reading. Baseline test state: **200 passed, 4 failed** (the 4 failures are A4).

The two worst are silent: E1 discards every data row of a valid workbook and reports
"no data rows", and E2 overwrites columns that share a header name. A1 means the audit
trail currently asserts budget imports that never happened.

Full findings with reproduction evidence are in the review transcript. This plan is the
implementation path.

### Decisions taken (confirmed with user)

| # | Decision |
|---|---|
| D1 | Persist per-import records in a new `import_runs` table, not only `audit_logs.details` |
| D2 | `resolve_columns` gains the alias fallback its docstring already promises (E4) |
| D3 | Audit **both** successful and failed import attempts (A1) |
| D4 | Date order is a per-import choice, defaulted from the device locale (E6) |
| D5 | Staged row contents are purged on commit; only counts/errors persist (retention) |

**Residual risk from D2 that the design must defuse:** fallback removes the user's
ability to force a field off. The wizard's "Not mapped" option becomes a no-op for
optional fields. The plan introduces an explicit `__ignore__` sentinel so opting out
remains possible and is distinguishable from "leave on auto-detect".

---

## Phase 0 — New schema (D1)

### 0.1 Model

Add `ImportRun` to `app/models/accounting.py` beside `AuditLog` (line 143), and export it
from `app/models/__init__.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `business_id` | FK `businesses.id`, not null, indexed | tenant scope |
| `user_id` | FK `users.id` `ondelete=SET NULL`, null | |
| `actor_name` / `actor_email` | String(120), null | mirrors `AuditLog` snapshot semantics (ADR-0009) |
| `entity` | String(50), not null | `bank_statements`, `journal_entries`, `suppliers`, `customers`, `budgets` |
| `filename` | String(255), null | original upload name |
| `status` | String(20), not null | `staged` → `committed` \| `failed` |
| `column_map` | Text, null | JSON `{field: header}` |
| `date_order` | String(3), null | `MDY` \| `DMY` |
| `account_id` | FK `chart_of_accounts.id`, null | bank statements only |
| `row_count` / `imported_count` / `duplicate_count` / `error_count` | Integer, not null, default 0 | |
| `errors` | Text, null | JSON list of `{row: int, message: str}`, retained permanently |
| `staged_rows` | Text, null | JSON of parsed records; **purged on commit** |
| `created_at` / `completed_at` | DateTime | UTC, matching `AuditLog.timestamp` default |

Indexes on `business_id` and on `(business_id, status)`.

### 0.2 Migration

New file `migrations/versions/20261001_import_runs.py`, `down_revision = "20261001_payment_reversals"`
(current single head — confirm with `alembic heads` before writing). Follows the style of
`20260930_audit_actor_snapshots.py`. `downgrade()` drops the table.

### 0.3 ADR

`docs/adr/ADR-0013-import-run-records-and-server-side-row-staging.md` (next free number;
ADR-0012 exists). Must cover:

- Why `audit_logs.details` alone was insufficient (no rejected-row recovery, no lifecycle).
- Why `import_runs` is deliberately **not** added to `AUDITED_TABLES` — it is an
  operational log, not a financial record; auditability comes from the explicit
  `IMPORT_*` / `IMPORT_*_FAILED` entries in `audit_logs`. Adding it would make the
  bulk-mutation guard block the legitimate purge path.
- Server-side staging vs. the client-supplied JSON `payload` (E7).
- Locale-derived date order and why it is overridable (D4).
- Extend/supersede ADR-0009's scope note: report-view auditing is unchanged.

---

## Phase 1 — Parser fixes (E1, E2, E3, E6)

All in `app/services/xlsx_import.py`.

### E1 — cells without an `r` attribute lose the whole row

`_column_index` (line 27) returns `-1` for a missing/empty reference. `_read_worksheet`
(line 140) stores the cell under key `-1`, `highest` stays `-1`, the row renders as `[]`,
and `parse_xlsx_file` (line 185) drops it as blank.

Fix in `_read_worksheet`: iterate with `enumerate` and fall back to the positional index
when `r` is absent or yields a negative index.

```python
for position, cell in enumerate(row.findall(f'{{{_MAIN_NS}}}c')):
    reference = cell.get('r')
    index = _column_index(reference) if reference else position
    if index < 0:
        index = position
    values[index] = _cell_value(cell, shared_strings)
    highest = max(highest, index)
```

### E2 — duplicate header names silently overwrite

`parse_xlsx_file` (line 187) builds each record with a dict comprehension keyed on the
header, so a repeated header collapses. `Name, Amount, Amount` yielded
`{'Name': 'Acme', 'Amount': 250}` — the first `Amount` vanished.

Fix: disambiguate headers before use. After stripping, walk the header list and append
` (2)`, ` (3)`, … to repeats, preserving first-occurrence names. Do this once and reuse
the result for both record keys and the value list so positions stay aligned. Blank
headers keep the existing `column_N` fallback (line 188).

### E3 — `OverflowError` on large numeric cells in a date column

`parse_date` line 206 returns `EXCEL_EPOCH + timedelta(days=int(value))` unguarded for
`Decimal` input, unlike the string path at line 218. `parse_date(Decimal('1e30'))` raises
`OverflowError: Python int too large to convert to C int` → uncaught 500.

Fix: route the `Decimal` branch through the same guarded conversion as the numeric-string
branch (catch `OverflowError`/`ValueError`, return `None`).

### E6 — locale-driven date order (D4)

`parse_date(value, date_order='MDY')`:

- Keep unambiguous forms first regardless of order: `%Y-%m-%d`, `%Y/%m/%d`.
- `MDY` → then `%m/%d/%Y`, `%d-%m-%Y`, `%m-%d-%Y`.
- `DMY` → then `%d/%m/%Y`, `%d-%m-%Y`, `%m-%d-%Y`.
- `date_order=None`/unknown → fall back to `MDY`.
- Guard the final serial conversion against `OverflowError`.

Call sites thread the value from the `ImportRun` row (Phase 3). Every
`parse_date` caller must be updated; there is no safe default to keep it implicit, so
audit the full call list with `rg 'parse_date'` before finishing.

**Device-locale detection (client side, `templates/import_wizard.html`):** add a
`date_order` select with `auto` / `mdy` / `dmy`. On load, resolve `auto` in JS:

```js
const parts = new Intl.DateTimeFormat(undefined,
  { year: 'numeric', month: '2-digit', day: '2-digit' })
  .formatToParts(new Date(2001, 1, 3)); // 3 Feb 2001
const first = parts.find(p => p.type === 'day' || p.type === 'month');
select.value = first.type === 'day' ? 'dmy' : 'mdy';
```

Guard for no-`Intl`/no-`formatToParts`: leave `auto`, which the server resolves to `MDY`.
Render a small "first date parsed as …" hint next to the selector using the first
date-mapped value, so a locale/file mismatch (UK device, US export) is visible before
import. **Locale is a default, not a guarantee — the override must stay.**

---

## Phase 2 — Mapping resolution (E4, D2)

`app/services/import_service.py:40`.

Current behaviour iterates only `column_map`, so any field the user leaves blank never
falls back to its aliases — contradicting its own docstring. Routes build `column_map`
from non-empty form fields only (`app/accounting/routes.py:982`, `:1051`;
`app/sales/routes.py:80`; `app/purchases/routes.py` equivalent), so clearing the
*Reference* select silently disabled bank-statement de-duplication.

New signature: `resolve_columns(rows, column_map=None, defaults=FIELD_MAP)`.

For each `(field, aliases)` in the default map:
1. explicit non-empty `column_map[field]` that resolves to a real header → use it;
2. explicit `IGNORE_FIELD` sentinel (`'__ignore__'`) → leave unresolved, no fallback;
3. otherwise → first alias matching a header, case-insensitively.

Remove the `column_map or FIELD_MAP` idiom at lines 92, 138, 227, 269 — the defaults are
now a parameter, so a partial `column_map` no longer discards alias knowledge.

Update the `templates/import_wizard.html` copy at line 51 ("Unmapped optional columns are
ignored") to describe auto-detect plus the explicit ignore option, and render
`__ignore__` as a distinct, labelled choice rather than overloading the empty value.

---

## Phase 3 — Server-side staging and import records (E7, E8, D1, D5)

### 3.1 New service `app/services/import_run_service.py`

- `stage_import(business_id, user_id, entity, filename, rows, column_map, date_order, account_id=None) -> ImportRun`
  — inserts with `status='staged'`, `row_count=len(rows)`, `staged_rows=json.dumps(rows, default=str)`.
- `load_staged(business_id, run_id) -> ImportRun` — 404/abort unless `status == 'staged'`
  and `business_id` matches the caller. **Enforce tenant scope here**; this is a new
  IDOR surface.
- `complete_import(run, result, status)` — writes counts and `errors`, sets
  `status`/`completed_at`, and sets `staged_rows = None` (D5).
- `purge_stale_staged_runs(older_than_hours=24)` — deletes only `status='staged'` rows
  past the cutoff. Never touches committed/failed rows.

### 3.2 Rework the two-step routes

Affected: `app/accounting/routes.py:845-1081` (bank statements, journal entries),
`app/sales/routes.py:44-112`, `app/purchases/routes.py:269-333`.

- **Step 1 (upload)** — parse, `stage_import(...)`, redirect to the wizard carrying only
  `import_run_id`. Remove the `payload=json.dumps(...)` hidden field
  (`accounting/routes.py:958`, `:1034`; `sales/routes.py:65`).
- **Step 2 (map/import)** — read `import_run_id`, call `load_staged(...)`, read rows
  from the server. **Reject any request carrying `payload`** with a flash telling the user
  to re-upload, so a stale bookmark cannot silently import client-supplied data.
- On success/failure call `complete_import(...)` in the same transaction as the data
  write, then `record_user_action(...)`:
  - committed → action `IMPORT_<ENTITY>`, details `{filename, row_count, imported,
    duplicates, error_count}`
  - failed → action `IMPORT_<ENTITY>_FAILED`, details `{filename, error}`
- Run `purge_stale_staged_runs()` opportunistically at step 1.

The result dict from `import_service` stays as-is; only persistence and reporting change.

### 3.3 Budget import (E8 + A1)

`app/reports/routes.py:846-889`.

- **Remove `@audit_report_access(...)` from `budget_variance_import`.** This is the A1
  root cause: the decorator commits unconditionally after the view returns, so the
  failure branch's rollback is followed by a successful-looking `BUDGET_IMPORT` row.
  Confirmed: POSTing `bad.xlsx` produced
  `[('BUDGET_IMPORT', 'reports', '{"report_type": "budget_variance_import"}')]`.
- Add explicit `record_user_action` in **both** the `except` branch
  (`BUDGET_IMPORT_FAILED`) and the `else` branch (`BUDGET_IMPORT`) (D3), each committed
  with the run row.
- Create/close an `ImportRun` with `entity='budgets'`. Budgets are all-or-nothing today
  (`_budget_import_rows` raises on the first bad row, `reports/routes.py:697`), so
  `error_count` is 0 or 1 — do not add partial-commit semantics to budgets.
- `_budget_import_rows` uses fixed headers (`BUDGET_IMPORT_COLUMNS`, line 664), so it has
  no column-map step and needs no staging — but it does need a run row for auditing.

### 3.4 Guard the remaining decorator calls

`audit_report_access` (`reports/routes.py:63-88`) still wraps ~19 report views. Change it
to return early without auditing when `response.status_code >= 400`, so a view that
aborts cannot still commit an audit row. Do not otherwise restructure it; the
commit-on-render wart is out of scope.

### 3.5 Rejected-row recovery (E8)

`_flash_import_result` (`accounting/routes.py:1000-1009`) and the inline duplicates in
`sales/routes.py:92-98` and `purchases/routes.py` flash only the first 5 errors and
discard the rest on redirect. Raise the inline cap to 10, and append a link to a
download of the full rejected-row list.

New blueprint `app/imports/` with one route:

- `GET /imports/<int:run_id>/errors` → XLSX of `{Row, Error}` built with the existing
  writer in `app/services/reports/xlsx_export.py`.

Scoped to `current_user.business_id`; 404 on mismatch. Add `imports_bp` to
`app/__init__.py` alongside the other blueprint registrations.

### 3.6 Journal single-line groups (E5)

`app/services/import_service.py:159`. `flush()` returns silently when
`len(current_lines) < 2`, so a one-line entry produced
`{'imported': 0, 'duplicates': 0, 'errors': []}` — rendered as a green "Imported 0 rows"
with no explanation.

Fix: append an explicit error naming the entry description. Verified safe: `current_key`
is only ever set immediately before a line is appended, so `current_lines` is non-empty
whenever `flush()` runs.

---

## Phase 4 — Audit service hygiene (A3, A4)

### A4 — audit listeners are process-global and break 4 tests

`install_audit_listeners()` (`audit_service.py:339-345`) registers on
`sqlalchemy.orm.Session` itself, so the guard applies to every session in the process.
Consequence: `tests/test_fifo.py` fails 4 tests in `setUp` at line 56
(`Setting.query.delete()` — `settings` is in `AUDITED_TABLES`), because that file builds
a private Flask app instead of using the `tests/conftest.py` `app` fixture.

Two changes:
1. Attach listeners to the app's scoped session, not the global class:
   `event.listen(app.extensions['sqlalchemy'].session, "before_flush", _before_flush)`.
   Note for the implementer: `do_orm_execute` needs `propagate=True` on a scoped-session
   target — verify the bulk-mutation guard still raises, and that
   `tests/test_accounting.py::test_bulk_mutations_of_audited_records_are_rejected`
   (line 329) still passes.
2. Remove the module-import side effect at `accounting_service.py:14-18`; install from
   `create_app` only (`app/__init__.py:242-243`).
3. Migrate `tests/test_fifo.py` to the shared `app` fixture from `tests/conftest.py`.

### A3 — inconsistent import root

`audit_service.py:352` uses `from models import db`; the rest of the codebase uses
`from app.models import db`. Works only because the top-level `models.py` shim exists.
Change it to `app.models` and confirm no dual-`db` split.

---

## Phase 5 — Tests

Baseline **200 passed, 4 failed**; target **all green**.

`tests/test_imports.py` — regression tests, one per finding:
- E1 workbook whose rows omit `r` → records present and correct
- E2 duplicate headers → distinct keys, no lost value
- E3 `parse_date(Decimal('1e30'))` → `None`, no raise
- E4 partial `column_map` → unmapped fields still alias-resolve; `__ignore__` suppresses
- E5 single-line journal group → error reported, `imported == 0`
- E6 `parse_date('01/02/2026', 'MDY')` → Jan 2; `'DMY'` → Feb 1
- E7 step-2 request carrying `payload` is rejected
- A2 each of the five importers writes `IMPORT_*` / `IMPORT_*_FAILED` with filename and counts

`tests/test_import_runs.py` (new):
- stage → load → complete lifecycle; `staged_rows` is `None` after commit
- cross-tenant `load_staged` is refused
- `purge_stale_staged_runs` deletes only stale `staged` rows
- `GET /imports/<id>/errors` returns XLSX; cross-tenant 404

`tests/test_accounting.py` / `tests/test_reports.py`:
- failed budget import writes `BUDGET_IMPORT_FAILED` and **not** `BUDGET_IMPORT`
- `audit_report_access` does not commit an audit row for a 4xx/5xx view

Existing route-flow tests (`test_imports.py:235-363`) will need their payloads updated to
`import_run_id`.

---

## Phase 6 — Documentation (required by `AGENT.md`)

- `docs/bugs_and_fixes.md` — new entries **Bug 32** onward, one per finding E1–E8 and
  A1–A4, in the mandated format (symptom / root cause / fix / files changed).
- `CHANGELOG.md` `[Unreleased]` — `Added` (`import_runs` table, rejected-row download,
  `purge-stale-import-runs`), `Changed` (import wizard auto-detect + date order, imports
  audited on failure), `Fixed` (E1–E8, A1–A4).
- `docs/adr/ADR-0013-import-run-records-and-server-side-row-staging.md` — Phase 0.3.
- `README.md` — new route `GET /imports/<int:run_id>/errors` and the `imports` blueprint.
- `docs/API.md` — no JSON API surface changes; the new route is HTML/XLSX. Confirm and
  leave unchanged.
- Update `docs/DATA_EXPORT_IMPORT.md:30`, which documents the paste-CSV path as
  deliberately naive — the CSV branch at `app/accounting/routes.py:858-922` is untouched
  by this plan; add a note that file uploads are `.xlsx` only.
- Verify none of these are caught by `.gitignore` (AGENT.md rule 12).

---

## Risks

| Risk | Mitigation |
|---|---|
| Two-step staging breaks in-flight wizard sessions after deploy | Old `payload`-based POSTs are explicitly rejected with a re-upload flash, not a 500 |
| New `import_runs` table on large production datasets | Table starts empty; no backfill, no data migration |
| Moving listeners off the global `Session` could silently disable auditing | `test_accounting.py` audit tests are the gate; run them first after the A4 change |
| Scoping `do_orm_execute` to a scoped session needs `propagate=True` | Flagged in Phase 4; verify guard tests immediately |
| Locale default is wrong for cross-border files | Selector shows the first parsed date and is overridable (Phase 1) |
| D2 fallback could auto-map an unintended column | Aliases are explicit and narrow; `__ignore__` escape hatch; mapping table is user-visible |

## Out of scope

- `.xls` and uploaded-CSV support (today `.xlsx` only, `SUPPORTED_EXTENSIONS`).
- Multi-sheet selection — `parse_xlsx_file` returns `sheet_names` but the wizard always
  reads sheet 0.
- The paste-CSV branch at `app/accounting/routes.py:858-922` (naive `split(',')`, no
  quoting) — a separate, larger fix.
- All-or-nothing import mode for bank statements / parties (E8 addresses recovery of
  rejected rows, not rollback of good ones).
- `MAX_CONTENT_LENGTH` tuning; staging removes the payload size problem but the initial
  upload is still limited.
- Restructuring `audit_report_access` beyond the `status_code >= 400` guard.

## Validation

```
pytest                                        # expect all green, was 200 passed / 4 failed
pytest tests/test_imports.py -v
pytest tests/test_import_runs.py -v
pytest tests/test_accounting.py -v            # audit guard still fires
flask db heads                                # confirm single head before writing migration
flask db upgrade                             # against a scratch DB, not production
```

No lint or typecheck tooling is configured in this repo (`CONTRIBUTING.md:174` mentions
`flake8` as guidance only); do not introduce it as part of this work.
