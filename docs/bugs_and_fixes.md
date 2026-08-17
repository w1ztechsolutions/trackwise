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
