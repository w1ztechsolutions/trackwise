# Bugs and Fixes Log

## Bug 1: RuntimeError — No Secret Key Set

**Date:** 2026-07-21  
**Severity:** High (app fails to start)  
**Environment:** Production (`FLASK_ENV=production`)

**Symptom:**

```bash
RuntimeError: The session is unavailable because no secret key was set. 
Set the secret_key on the application to something unique and secret.
```

**Root cause:**

- `.env` sets `FLASK_ENV=production`, activating `ProductionConfig`.
- `DevelopmentConfig` had `SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())`.
- `ProductionConfig` had no `SECRET_KEY` class attribute — only an `__init__` check.
- `app.config.from_object()` does not call `__init__`, so `SECRET_KEY` was never set.

**Fix:**

- Added `SECRET_KEY = os.environ.get("SECRET_KEY")` to `ProductionConfig` in `config.py`.
- `__init__` still raises `RuntimeError` if `SECRET_KEY` is missing, preserving security in production.

**Files changed:**

- `config.py`

---

## Bug 2: BuildError — `auth.register` Endpoint Does Not Exist

**Date:** 2026-07-21  
**Severity:** High (login page crashes)  
**Environment:** All

**Symptom:**

```bash
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 
'auth.register'. Did you mean 'auth.create_user' instead?
```

**Root cause:**

- `templates/auth.html` contained `<a href="{{ url_for('auth.register') }}">Register</a>`.
- The public registration route was removed in favor of `auth.create_user` (`/users/create`).
- The template was not updated after the route rename.

**Fix:**

- Changed `url_for('auth.register')` to `url_for('auth.create_user')` in `templates/auth.html`.
- Also fixed `templates/register.html` which had the same stale reference.

**Files changed:**

- `templates/auth.html`
- `templates/register.html`

---

## Bug 3: Missing Superadmin Templates — `sa_login.html`

**Date:** 2026-07-21  
**Severity:** High (superadmin login returns 500)  
**Environment:** All

**Symptom:**

- Navigating to `/superadmin/login` returns a server error.
- Template lookup fails because `sa_login.html` does not exist in `app/superadmin/templates/`.

**Root cause:**

- The app references `render_template('sa_login.html')` in `app/superadmin/routes.py`.
- The template was expected in the blueprint's `template_folder='templates'` (i.e., `app/superadmin/templates/`), but was missing.

**Fix:**

- Created missing superadmin templates:
  - `app/superadmin/templates/sa_login.html`
  - `app/superadmin/templates/sa_dashboard.html`
  - `app/superadmin/templates/sa_businesses.html`
  - `app/superadmin/templates/sa_business_form.html`
  - `app/superadmin/templates/sa_admins.html`
  - `app/superadmin/templates/sa_admin_form.html`
  - `app/superadmin/templates/sa_users.html`

**Files changed:**

- Created 7 new template files under `app/superadmin/templates/`

---

## Bug 4: Superadmin Login Returns "Invalid Credentials" With Correct Credentials

**Date:** 2026-07-21  
**Severity:** High (cannot access superadmin panel)  
**Environment:** All

**Symptom:**

- Submitting correct superadmin email and password flashes "Invalid super admin credentials."
- No `super_admins` rows exist in the database.

**Root cause:**

- No superadmin user was ever created in the database.
- There was no built-in mechanism to create one.

**Fix:**

- Added `flask create-superadmin` CLI command in `app/__init__.py`.
- Created default superadmin: `admin@trackwise.app` / `TrackWiseSA2026!`.
- Command format: `flask create-superadmin <email> <name> <password>`.

**Files changed:**

- `app/__init__.py`

---

## Bug 5: Database Schema Mismatch — Missing Columns After Failed Migration

**Date:** 2026-07-21  
**Severity:** High (app crashes on dashboard queries)  
**Environment:** Neon PostgreSQL

**Symptom:**

```bash
psycopg.errors.UndefinedColumn: column businesses.created_by_superadmin_id does not exist
```

**Root cause:**

- Alembic migration `85d9ae31c828` (phase_8_role_hierarchy_and_approvals) added `created_by_superadmin_id` to `businesses` and `must_change_password` to `users`.
- The migration failed with `DuplicateTable` on `super_admins` and did not complete.
- Alembic version was stuck at `a907d24e2ef5`, so the missing columns were never created.

**Fix:**

- Added missing columns directly via SQLAlchemy:

  ```python
  ALTER TABLE businesses ADD COLUMN IF NOT EXISTS created_by_superadmin_id INTEGER
  ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE NOT NULL
  ```

- Updated alembic version to `85d9ae31c828`.

**Files changed:**

- Database schema updated (not code files)

---

## Bug 6: Superadmin Dashboard KPI Icons Not Rendering

**Date:** 2026-07-21  
**Severity:** Medium (UI missing visual elements)  
**Environment:** Superadmin dashboard

**Symptom:**

- Superadmin dashboard KPI cards show only text, no icons.

**Root cause:**

- `sa_dashboard.html` did not include any icon elements in the KPI cards.
- Bootstrap Icons library was loaded but unused in the dashboard template.

**Fix:**

- Added `<i class="bi bi-building">`, `<i class="bi bi-people">`, and `<i class="bi bi-person-lines-fill">` to the respective KPI cards in `sa_dashboard.html`.

**Files changed:**

- `app/superadmin/templates/sa_dashboard.html`

---

## Bug 7: Main Dashboard KPI Cards Overflow With Large Numbers

**Date:** 2026-07-21  
**Severity:** Medium (poor UX on desktop and mobile)  
**Environment:** Main dashboard

**Symptom:**

- KPI cards use `grid-template-columns: repeat(5, 1fr)` (fixed 5 columns).
- When financial figures become large (e.g., "MWK 12,450,000"), cards shrink and text overflows or becomes unreadable.

**Root cause:**

- Fixed column count does not adapt to content width.
- Breakpoints only reduce columns at specific widths, leaving intermediate widths with cramped cards.
- Changed `.kpi-grid` to `repeat(auto-fit, minmax(180px, 1fr))`.
- Cards now expand to fit content and wrap to new rows automatically.
- Updated both inline CSS in `templates/base.html` and external `static/css/style.css`.

**Files changed:**

- `templates/base.html`
- `static/css/style.css`

---

## Bug 8: Superadmin Mobile Navigation Has No Hamburger Menu

**Date:** 2026-07-21  
**Severity:** Medium (unusable on phones)  
**Environment:** Superadmin on mobile viewports

**Symptom:**

- On phones, the 240px fixed sidebar is always off-screen with no visible toggle.
- Users cannot access navigation without resizing to desktop.

**Root cause:**

- `sa_base.html` had no mobile sidebar toggle, overlay, or slide-in CSS.
- The main app had these patterns, but superadmin did not inherit them.

**Fix:**

- Added hamburger toggle button (`.sa-toggle`) with overlay (`.sidebar-overlay`).
- Added mobile CSS: sidebar hidden by default on `max-width: 768px`, slides in when toggled.
- JavaScript toggles `.open` class on sidebar and overlay; clicking overlay or nav links closes sidebar.

**Files changed:**

- `app/superadmin/templates/sa_base.html`

---

## Bug 9: Cross-business data leak through unscoped page and API queries

**Date:** 2026-08-17  
**Severity:** Critical  
**Environment:** All multi-tenant users

**Symptom:**
> A user logged into one business could see inventory, customer, supplier, and financial records belonging to a different business.

**Root cause:**

- Several route handlers and dashboard queries listed products, customers, suppliers, invoices, purchases, expenses, bills, and payment data without an explicit `business_id` filter.
- The app set the tenant context at request time in `g.business_id`, but multiple lists ignored it and read across the full table.
- Inventory valuation and some duplicate checks also used global queries, enabling cross-tenant visibility and accidental name collisions.

**Fix:**

- Scoped all dashboard, inventory, sales, purchases, and warehouse listing queries to the authenticated user’s business.
- Added business ownership checks before update/delete actions on product records.
- Added a regression test covering a second business user that confirms only their own business data is visible.
- Restricted all inventory valuation queries to the active business as well.

**Files changed:**

- `app/dashboard/routes.py`
- `app/inventory/routes.py`
- `app/sales/routes.py`
- `app/purchases/routes.py`
- `services/fifo_service.py`
- `tests/test_routes.py`

---

## Bug 10: Content Security Policy Blocks Bootstrap Icons and Vercel Analytics

**Date:** 2026-07-21  
**Severity:** Medium (styles and analytics fail to load)  
**Environment:** All pages

**Symptom:**

- Superadmin pages render without Bootstrap styling.
- Browser console shows CSP violations for `cdn.jsdelivr.net` styles and `cdn.vercel-insights.com` scripts.

**Root cause:**

- `Content-Security-Policy` header in `app/__init__.py` did not include `cdn.jsdelivr.net` in `style-src` or `cdn.vercel-insights.com` in `script-src`.

**Fix:**

- Updated CSP header:
  - `style-src`: added `https://cdn.jsdelivr.net`
  - `script-src`: added `https://cdn.vercel-insights.com`

**Files changed:**

- `app/__init__.py`

---

## Bug 11: `/register` Route Returns 404

**Date:** 2026-07-21  
**Severity:** Low (broken link)  
**Environment:** All

**Symptom:**

- Navigating to `/register` returns 404 Not Found.

**Root cause:**

- The public `/register` route was removed when user creation moved to admin-only `/users/create`.
- No redirect or replacement route was configured.

**Status:** Known limitation. Users must be created by an admin via Settings → Users.

**Files changed:** None

---

## Bug 12: Bank Reconciliation Page Returns 500 — `bank_statements` Table Does Not Exist

**Date:** 2026-08-17  
**Severity:** High (feature completely unavailable)  
**Environment:** Production / Development (Neon PostgreSQL)

**Symptom:**

```bash
psycopg.errors.UndefinedTable: relation "bank_statements" does not exist
LINE 3: FROM bank_statements 
             ^

File "/var/task/app/accounting/routes.py", line 414, in bank_recon
    ).count()
```

Navigating to `/accounting/bank-reconciliation` returns HTTP 500.

**Root cause:**

- The `BankStatement` model and migration `20260817_add_bank_statements` were present in the codebase.
- The database had not received this migration. `alembic_version` only contained `7f8a9b0c1d2e` and `20260816_add_invoice_id_to_sales`.
- Additionally, the migration tree had **multiple heads** (`7f8a9b0c1d2e` and `20260816_add_invoice_id_to_sales`), which caused `flask db upgrade` to fail with: `Multiple head revisions are present`.
- Because the migration could not run, the `bank_statements` table and its indexes were never created.

**Fix:**

- Created the `bank_statements` table directly via SQL with the schema matching `app/models/accounting.py`:

  ```sql
  CREATE TABLE bank_statements (
      id SERIAL PRIMARY KEY,
      business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
      account_id INTEGER NOT NULL REFERENCES chart_of_accounts(id),
      statement_date TIMESTAMP NOT NULL,
      description VARCHAR(255) NOT NULL,
      amount NUMERIC(14, 2) NOT NULL,
      reference VARCHAR(100),
      is_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
      journal_entry_id INTEGER REFERENCES journal_entries(id),
      created_at TIMESTAMP NOT NULL DEFAULT NOW()
  );
  ```

- Created required indexes:

  ```sql
  CREATE INDEX ix_bank_statements_business_id ON bank_statements (business_id);
  CREATE INDEX ix_bank_statements_account_id ON bank_statements (account_id);
  CREATE INDEX ix_bank_statements_is_reconciled ON bank_statements (is_reconciled);
  ```

- Inserted migration version `20260817_add_bank_statements` into `alembic_version` so future upgrades remain consistent.
- Resolved the multiple-head migration tree by creating merge migration `20260817_merge_heads` with `down_revision` pointing to `7f8a9b0c1d2e`, `0015`, and `20260817_add_bank_statements`. This allows `flask db upgrade` to run cleanly.

- Verified the exact failing query now succeeds:

  ```python
  BankStatement.query.filter_by(business_id=2, account_id=3, is_reconciled=False).count()
  ```

**Files changed:**

- `migrations/versions/20260817_merge_heads.py` — new merge migration
- Database schema updated (not code files)
- `migrations/versions/20260817_add_bank_statements.py` — existing migration now tracked in `alembic_version`

---

## Bug 13: MDN HTTP Observatory Flags Unsafe CSP and Missing SRI

**Date:** 2026-08-24  
**Severity:** High (security scan failures, -25 grade penalty)  
**Environment:** Production (`trackwise-chi.vercel.app`)

**Symptom:**

- MDN HTTP Observatory score: 75/100 (Grade B)
- **Content Security Policy (CSP)** test failed (-20 points)
- **Subresource Integrity (SRI)** test failed (-5 points)

**Root cause:**

- `script-src` included `'unsafe-inline'`, allowing arbitrary inline JavaScript execution.
- No `object-src` restriction was present.
- External scripts loaded from CDNs lacked `integrity` and `crossorigin` attributes.
- Inline `<style>` blocks and inline `<script>` blocks relied on `'unsafe-inline'` to function.

**Fix:**

- Added per-request CSP nonce generation in `app/__init__.py` via `_set_csp_nonce` and injected `csp_nonce` into all templates.
- Removed `'unsafe-inline'` from `script-src`; added `'nonce-{nonce}'` and `object-src 'none'`.
- Externalized inline critical CSS into `static/css/critical.css`.
- Externalized inline scripts into dedicated files under `static/js/` (`speed-insights-init.js`, `sa-sidebar.js`, `dashboard.js`, `inventory.js`, `journal-entry-form.js`, `journal-entries.js`, `payments.js`, `purchases.js`, `sales.js`).
- Replaced all inline event handlers (`onclick`, `onchange`, `onsubmit`) with `data-` attributes handled by `static/js/form-handlers.js`.
- Added SHA-256 `integrity` hashes and `crossorigin="anonymous"` to all external `<script>` and `<link>` tags (Chart.js, Bootstrap, Vercel Insights, Google Fonts, Bootstrap Icons).

**Security:** Yes — fixes two HTTP security header failures flagged by MDN Observatory.

**Files changed:**

- `app/__init__.py`
- `templates/base.html`
- `templates/dashboard.html`
- `templates/inventory.html`
- `templates/journal_entry_form.html`
- `templates/journal_entries.html`
- `templates/payments.html`
- `templates/purchases.html`
- `templates/sales.html`
- `templates/bank_reconcile.html`
- `templates/chart_of_accounts.html`
- `templates/customers.html`
- `templates/document_receipt.html`
- `templates/invoices.html`
- `templates/reports.html`
- `templates/settings.html`
- `templates/suppliers.html`
- `app/superadmin/templates/sa_base.html`
- `app/superadmin/templates/sa_login.html`
- `static/css/critical.css`
- `static/js/dashboard.js`
- `static/js/form-handlers.js`
- `static/js/inventory.js`
- `static/js/journal-entries.js`
- `static/js/journal-entry-form.js`
- `static/js/payments.js`
- `static/js/purchases.js`
- `static/js/sa-sidebar.js`
- `static/js/sales.js`
- `static/js/speed-insights-init.js`

---

## Bug 14: Financial Changes Were Not Consistently Audited

**Date:** 2026-09-30 | **Severity:** Critical (financial auditability) | **Environment:** All

**Symptom:**

Financial source records and authentication actions could be changed without a complete, actor-attributed audit trail.

**Root cause:**

Audit events were limited and did not consistently cover financial source records, journal lines, approval actions, or authentication actions. Existing audit rows were also mutable through the ORM.

**Fix:**

- Added transactional create/update/delete auditing for financially significant records and explicit login, logout, and password-change events.
- Resolved tenant attribution for journal lines and approval actions through their parent records.
- Excluded password hashes and bank account numbers from snapshots and reject ORM updates/deletes to existing audit rows.

**Security:** Yes — the audit trail records authentication and financial changes. This is application-level protection; direct database administrators can still alter rows.

**Files changed:**

- `app/services/audit_service.py`
- `app/__init__.py`
- `app/auth/routes.py`
- `app/models/accounting.py`
- `tests/test_accounting.py`

---

## Bug 15: AR/AP Aging Included Settled Amounts

**Date:** 2026-09-30 | **Severity:** High (receivables/payables reporting) | **Environment:** All

**Symptom:**

The aging reports could show original invoice or bill amounts after linked receipts or approved payments had reduced the open balance.

**Root cause:**

Aging used gross source-document amounts instead of allocating linked movements through the report's as-of date.

**Fix:**

Allocate linked receipts and approved bill payments dated on or before the report date against each document before bucketing the remaining balance. Pending payments and future-dated movements are excluded.

**Files changed:**

- `app/services/reports/aging_utils.py`
- `app/services/reports/ar_aging.py`
- `app/services/reports/ap_aging.py`
- `tests/test_reports.py`

---

## Bug 22: Fresh Demo Database Could Not Follow the Legacy Migration Chain

**Date:** 2026-09-30
**Severity:** High (demo database cannot be initialized)
**Environment:** Fresh PostgreSQL demo database

**Symptom:**

The migration chain failed on a clean demo database. The legacy migration expected a `uq_settings_key` constraint name that was not present, then failed with `relation "material_usages" does not exist`.

**Root cause:**

The historical migration assumes a database created with a particular PostgreSQL-generated constraint name and assumes `material_usages` exists, although no migration in the chain creates that table. The migration is already part of the deployed history and must not be edited in place.

**Fix:**

Added a demo-only bootstrap factory and command. It verifies the target is distinct from production, refuses non-empty or unmapped schemas, creates the current ORM metadata on an empty demo database, and stamps the current Alembic head(s). Subsequent demo upgrades can use Alembic through the same demo-only factory.

**Files changed:**

- `app/__init__.py`
- `.env.example`
- `DEPLOY_VERCEL.md`
- `docs/MIGRATION_2026-09_demo_workspace_database.md`
- `docs/ENVIRONMENT.md`
- `docs/OPERATIONS.md`
- `README.md`
- `CHANGELOG.md`
- `docs/DATABASE.md`
- `docs/adr/ADR-0012-fresh-demo-database-bootstrap.md`

---

## Bug 23: Demo Pages Inherited App Navigation and Bootstrap-Only Styling

**Date:** 2026-09-30
**Severity:** Medium
**Environment:** All, especially mobile browsers

**Symptom:**

The demo forms displayed the signed-in application navigation, which could obscure the form on mobile. Warning and action layout also relied on Bootstrap utility and alert classes.

**Root cause:**

The demo page render paths did not disable the shared app navigation, and the templates used external Bootstrap styles that were blocked by invalid integrity hashes.

**Fix:**

Made both demo screens standalone by hiding application navigation and replaced Bootstrap-dependent layout pieces with responsive, locally styled components.

**Files changed:**

- `app/auth/routes.py`
- `templates/demo_entry.html`
- `templates/demo_business_exists.html`
- `static/css/style.css`
- `tests/test_demo_accounts.py`

---

## Bug 25: Chart of Accounts Dialogs Rendered Inline

**Date:** 2026-09-30
**Severity:** High (account management UI unusable)
**Environment:** All browsers loading the shared Bootstrap layout

**Symptom:**

The Add Account, Edit Account, Opening Balance, and starter-account picker dialogs appeared as page content, including at the bottom of the Chart of Accounts page, instead of opening only after their buttons were clicked.

**Root cause:**

The Bootstrap 5.3.0 stylesheet and bundle URLs in the shared base template had incorrect Subresource Integrity hashes. Browsers rejected both assets, so modal hiding, layout, and click behavior were unavailable.

**Fix:**

Replaced the two incorrect hashes with hashes verified against the exact pinned CDN assets. Renamed the starter-account action and dialog title to make the button-triggered workflow clear. Made the picker scrollable and full-screen on small screens so its account list remains usable on mobile.

**Files changed:**

- `templates/base.html`
- `templates/chart_of_accounts.html`
- `templates/coa_seeder_modal.html`
- `CHANGELOG.md`

---

## Bug 26: Starter Account Picker Controls Had Low Contrast in Dark Mode

**Date:** 2026-09-30
**Severity:** Medium (reduced usability)
**Environment:** Chart of Accounts starter-account picker in dark mode

**Symptom:**

Gray subcategory buttons and account details were difficult to distinguish from the dark modal background.

**Root cause:**

The picker relied on Bootstrap's muted outline-secondary styling and generic muted text colors, which had insufficient contrast against the dark modal surface.

**Fix:**

Added picker-scoped dark-theme colors for subcategory controls, account labels, account codes, checkboxes, and the selected-accounts preview. Added explicit light-theme colors to preserve readability when switching themes.

**Files changed:**

- `static/css/style.css`
- `CHANGELOG.md`

---

## Bug 27: Purchases Page Failed to Render

**Date:** 2026-09-30
**Severity:** High (purchases workflow unavailable)
**Environment:** Purchases page template

**Symptom:**

Opening `/purchases` raised a Jinja `TemplateSyntaxError` for an unexpected `endblock`.

**Root cause:**

The template closed its `scripts` block and then contained an extra `endblock` tag.

**Fix:**

Removed the unmatched closing tag so the Purchases page renders normally.

**Files changed:**

- `templates/purchases.html`
- `CHANGELOG.md`

---

## Bug 28: Light Theme Pages Had Low Contrast and Dashboard Chart Did Not Load

**Date:** 2026-09-30
**Severity:** Medium (reduced readability and missing dashboard visualization)
**Environment:** Light theme on Chart of Accounts, Bank Reconciliation, and Dashboard

**Symptom:**

Muted text, status badges, card boundaries, and table headers were difficult to read against the white page background. The dashboard chart was blank because the browser rejected the pinned Chart.js script.

**Root cause:**

The light-theme palette used low-contrast gray and semantic colors, while the page background and cards were both white. Chart.js had an invalid Subresource Integrity hash, and the dashboard's chart script ran before its deferred Chart.js dependency.

**Fix:**

Introduced a soft slate page background with white cards, increased muted text and border contrast, and added readable light-theme status badge colors. Corrected the Chart.js integrity hash, deferred the dashboard chart script so it runs after its dependency, and made chart labels and grid lines respond to light/dark theme changes.

**Files changed:**

- `templates/base.html`
- `templates/dashboard.html`
- `static/css/critical.css`
- `static/css/style.css`
- `static/js/dashboard.js`
- `CHANGELOG.md`

---

## Bug 29: Light Theme Flashed Dark During Page Navigation

**Date:** 2026-09-30
**Severity:** Medium (visual disruption during navigation)
**Environment:** Pages using the shared base template

**Symptom:**

When light mode was selected, navigating to another page briefly displayed the dark theme before switching to light.

**Root cause:**

The saved theme was read by `main.js` at the end of the document, after stylesheets and initial page rendering had already started.

**Fix:**

Initialize the stored or system-preferred theme in the document head before stylesheets load. The page-end theme controller now synchronizes the toggle state with that early choice and only persists a choice when the user changes it.

**Files changed:**

- `templates/base.html`
- `static/js/main.js`
- `CHANGELOG.md`

---

## Bug 30: Inventory, Sales, and Payments Templates Failed to Render

**Date:** 2026-09-30
**Severity:** High (core operational routes unavailable)
**Environment:** Inventory, Sales, and Payments pages in demo and production sessions

**Symptom:**

Opening `/inventory`, `/sales`, or `/payments` raised a Jinja `TemplateSyntaxError` instead of rendering the page.

**Root cause:**

Each template contained an extra `{% endblock %}` after its `scripts` block had already been closed.

**Fix:**

Removed the unmatched block terminators and added a demo-database regression test that opens all three pages after entering a demo workspace.

**Files changed:**

- `templates/inventory.html`
- `templates/sales.html`
- `templates/payments.html`
- `tests/test_demo_accounts.py`
- `CHANGELOG.md`

---

## Bug 16: Posted Journal Entries Had No Reversal Workflow

**Date:** 2026-09-30 | **Severity:** Critical (financial history integrity) | **Environment:** All

**Symptom:**

Users had no supported way to correct a posted journal entry while retaining its original record and audit history.

**Root cause:**

There was no reversal operation, and journal-line validation did not reject several invalid line shapes.

**Fix:**

Post a separately identified, balanced counter-entry with a required reason, link it to the original, and retain the original entry. Validate non-zero lines, finite non-negative amounts, and mutually exclusive debit/credit values.

**Files changed:**

- `app/services/accounting_service.py`
- `app/models/accounting.py`
- `app/accounting/routes.py`
- `templates/journal_entries.html`
- `templates/journal_entry_view.html`
- `tests/test_accounting.py`
- `tests/test_routes.py`

---

## Bug 17: Closed Accounting Periods Accepted New or Changed Transactions

**Date:** 2026-09-30 | **Severity:** Critical (period integrity) | **Environment:** All

**Symptom:**

Transactions dated in an already-reviewed accounting period could be posted or edited without an explicit reopen operation. Previously, closed periods could not be reopened through the application.

**Root cause:**

The business had no close-through date or shared write guard for closed periods.

**Fix:**

Add a business-scoped close-through date, permit admins/accountants to advance it through the period-close page, and reject financial writes dated on or before it. Add a separate reopen action restricted to admins, require explicit confirmation, and retain audit logging of the business close-date change.

**Files changed:**

- `app/services/period_service.py`
- `app/services/audit_service.py`
- `app/models/accounting.py`
- `app/accounting/routes.py`
- `templates/period_close.html`
- `tests/test_accounting.py`
- `tests/test_routes.py`

**Updated behavior:** Only an administrator may reopen a closed period. The action clears the close-through date and creates an audit-log entry. Accountants may still close and advance the close date but cannot reopen it.

---

## Bug 24: Demo User Management Exposed Unneeded User Creation

**Date:** 2026-09-30
**Severity:** Low
**Environment:** Demo sessions

**Symptom:**

Demo administrators could open the manual **Create User** page, even though the demo is for exploring application roles rather than testing user provisioning.

**Root cause:**

The user creation route and link were available to any administrator, without checking whether the signed session was routed to the demo database.

**Fix:**

Hide manual user-creation links in demo user management and return 404 for direct GET and POST requests to `/users/create` during demo sessions. Role selection at demo entry still generates the internal user needed to explore each role. Production user management remains unchanged.

**Files changed:**

- `app/auth/register_routes.py`
- `templates/user_management.html`
- `tests/test_demo_accounts.py`
- `docs/MIGRATION_2026-09_demo_workspace_database.md`
- `docs/ENVIRONMENT.md`
- `docs/adr/ADR-0011-isolated-role-based-demo-access.md`
- `CHANGELOG.md`

---

## Bug 18: Tax Estimate Was Not Clearly Scoped or Qualified

**Date:** 2026-09-30 | **Severity:** High (financial reporting presentation) | **Environment:** All

**Symptom:**

The income statement tax display could use an unscoped configured rate and appear to be a statutory tax calculation.

**Root cause:**

The configured rate was not consistently read in the current business context, and the presentation did not sufficiently distinguish a simple estimate from a tax provision or filing calculation.

**Fix:**

Scope the rate to the current business and label the result as an informational estimate. The application does not calculate jurisdiction-specific tax, deductible adjustments, carryforwards, provisional tax, or deferred tax.

**Files changed:**

- `app/services/reports/income_statement.py`
- `services/fifo_service.py`
- `templates/reports.html`
- `templates/dashboard.html`
- `tests/test_reports.py`

---

## Bug 19: Journal Entry Templates Could Not Render

**Date:** 2026-09-30 | **Severity:** High (accounting workflow availability) | **Environment:** All

**Symptom:**

Opening the journal entry list, detail, or creation pages raised Jinja template syntax errors.

**Root cause:**

The detail template used a generator expression in a syntax form unsupported by the configured Jinja parser, and the list and creation templates had unmatched `endblock` tags.

**Fix:**

Use supported template logic and balanced block delimiters; expose reversal metadata and debit/credit totals.

**Files changed:**

- `templates/journal_entries.html`
- `templates/journal_entry_view.html`
- `templates/journal_entry_form.html`
- `app/accounting/routes.py`
- `tests/test_routes.py`

---

## Bug 20: Deferred Revenue Had No Supported Recognition Schedule

**Date:** 2026-09-30 | **Severity:** High (revenue cut-off and presentation) | **Environment:** All

**Symptom:**

Posted invoice revenue requiring time-based deferral had no application workflow to reclassify the unearned balance and recognize it over a service period.

**Root cause:**

No deferred-revenue schedule model or idempotent recognition service existed.

**Fix:**

Add a straight-line daily schedule for posted invoice revenue, with a liability reclassification and date-bounded recognition entries. This is an operational aid only: it does not evaluate IFRS 15/ASC 606 contract eligibility, identify performance obligations, or replace an accountant's assessment.

**Files changed:**

- `app/services/revenue_recognition_service.py`
- `app/models/accounting.py`
- `app/accounting/routes.py`
- `templates/revenue_recognition.html`
- `migrations/versions/20260930_financial_controls.py`
- `tests/test_accounting.py`

---

## Bug 21: Financial Reports Included Soft-Deleted Journal Entries

**Date:** 2026-09-30 | **Severity:** High (ledger/report accuracy) | **Environment:** All

**Symptom:**

Several financial reports and balance checks could include journal entries marked as deleted.

**Root cause:**

Report queries did not consistently filter the journal-entry soft-delete flag.

**Fix:**

Exclude soft-deleted entries from the financial report services and accounting integrity checks.

**Files changed:**

- `app/services/reports/balance_sheet.py`
- `app/services/reports/cash_flow.py`
- `app/services/reports/cashbook.py`
- `app/services/reports/general_ledger.py`
- `app/services/reports/income_statement.py`
- `app/services/reports/trial_balance.py`
- `tests/test_reports.py`
