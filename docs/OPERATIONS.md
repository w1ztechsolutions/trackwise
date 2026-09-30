# Operations Guide — Utility Scripts & Runbooks

This document describes the operational utility scripts included in the TrackWise repository. These scripts are intended for **development, deployment, and troubleshooting** only. Do not run them in production without understanding their side effects.

---

## Table of Contents

1. [Database Migration](#database-migration)
2. [Database Schema Verification](#database-schema-verification)
3. [Invoice ID Column Verification](#invoice-id-column-verification)
4. [Seed Demo Data](#seed-demo-data)
5. [Quick Database Connectivity Check](#quick-database-connectivity-check)
6. [Common Operational Procedures](#common-operational-procedures)

---

## Database Migration

**File:** `scripts/run_migration.py`  
**Purpose:** Run Alembic migrations against the configured database with proper environment loading.

### Usage

```bash
# Make sure your .env or .env.local has DATABASE_URL configured
python scripts/run_migration.py
```

### What it does

1. Loads `.env` and `.env.local` in the correct precedence order.
2. Creates the Flask app using `ProductionConfig` so `DATABASE_URL` is honored exactly.
3. If the database has no application tables yet, it runs `db.create_all()` and stamps the Alembic version chain as `head`.
4. Otherwise, it runs `flask db upgrade` to apply pending migrations.

### Notes

- For a **fresh Neon/PostgreSQL database**, this is the recommended first-run command.
- For ongoing development, use `flask db upgrade` directly.
- Never edit an existing migration file that has been applied to production. Create a new migration instead.

---

## Database Schema Verification

**File:** `check_db_schema.py`  
**Purpose:** Verify that the Neon PostgreSQL database has the expected tables and migration status.

### Usage

```bash
python check_db_schema.py
```

### What it does

1. Prints the database engine name and a masked URI.
2. Lists all tables in the database.
3. Checks for Phase 7 SaaS tables (`plans`, `subscriptions`).
4. Reads the `alembic_version` table to show the current migration revision.
5. Counts records in key tables (`businesses`, `users`, `products`, `sales`, `purchases`, `journal_entries`, `chart_of_accounts`, `plans`, `subscriptions`).
6. Returns a status: `[OK] DATABASE STATUS: UPDATED` or `[X] DATABASE STATUS: PREVIOUS`.

### When to use

- After deploying to a new database.
- After running migrations to confirm schema is current.
- During debugging when tables seem missing.

---

## Invoice ID Column Verification

**File:** `verify_invoice_id.py`  
**Purpose:** Verify that the `invoice_id` column was successfully added to the `sales` table.

### Usage

```bash
python verify_invoice_id.py
```

### What it does

1. Connects to the database.
2. Introspects the `sales` table columns.
3. Prints whether `invoice_id` exists.

### When to use

- After running migration `20260816_add_invoice_id_to_sales.py`.
- When debugging sales-to-invoice linkage issues.

---

## Seed Demo Data

**File:** `seed.py`  
**Purpose:** Seed the database with sample data for development and testing.

### Usage

```bash
# Via Flask shell
flask shell
>>> from seed import seed_demo_data
>>> seed_demo_data()
>>> exit()

# Or run directly (also runs migrations first)
python seed.py
```

### What it does

- Creates a default `Business` if none exists.
- Seeds the `ChartOfAccounts` with a standard set of accounts.
- Seeds `FinancialCategory` and `LineItem` records for Payments Hub.
- Seeds sample `Staff` records.
- Clears existing transactional data (`products`, `purchases`, `sales`, `expenses`, `stock_transactions`) to prevent duplicates.
- Creates sample products, purchases, sales, and expenses with realistic data.

### Warning

`seed_demo_data()` **deletes existing transactional data** before reseeding. Do not run this against a production database.

---

## Quick Database Connectivity Check

**File:** `verify_db.py`  
**Purpose:** Quick sanity check that the app can connect to the database and the `users` table exists.

### Usage

```bash
python verify_db.py
```

### What it does

1. Prints the configured `SQLALCHEMY_DATABASE_URI`.
2. Executes a lightweight query (`SELECT 1` or table existence check).
3. Prints the user count.

### When to use

- Verifying `DATABASE_URL` is correctly loaded.
- Checking SQLite vs PostgreSQL dialect selection.

---

## Common Operational Procedures

### Configuring a Separate Neon Demo Database

1. Create a separate Neon project or branch exclusively for demo data. Set `DEMO_DATABASE_URL` to its connection string and retain `DATABASE_URL` for production; never paste either URL into logs or chat.
2. Set `DEMO_MODE_ENABLED=true` and restart/redeploy. Startup fails closed when the flag is on but the demo URL is missing or exactly matches the production URL.
3. Run `flask db upgrade` for production. For a new, empty demo database, use `flask --app 'app:create_demo_migration_app' demo-db-bootstrap`. The bootstrap verifies the target is separate, contains no application rows, and has no unexpected tables before creating the ORM schema and stamping Alembic head(s).
4. For subsequent demo schema changes, review the pending migrations and run `flask --app 'app:create_demo_migration_app' db upgrade`. Never point the normal app's `flask db upgrade` at the demo database.
5. Open `/demo`, enter a business name, and select a role. New names create a demo business; a matching normalized name prompts the visitor to proceed into the shared business or choose another name.
6. Proceeding creates a new random internal user for the selected role. Credentials are not displayed. All users of that business share its data, which may be changed or reset.
7. Regular `/login` credentials always use the production database. Each demo session has a signed database-context marker so application queries for that session remain on the demo database; logout clears the marker.
8. Disable demo mode to remove public access. Existing demo businesses remain only in the demo database.

### Closing an Accounting Period

1. Complete reconciliation and review the trial balance and supporting reports.
2. As an `admin` or `accountant`, open **Accounting → Journal Entries → Period Close**.
3. Close through the final date reviewed. The application only permits moving the close date forward.
4. If corrections in the closed period are required, only an `admin` can reopen it. Confirm the action on the Period Close page; the event is recorded in the audit log.
5. Complete and review corrections promptly, then close the period again. Alternatively, correct posted entries with a reasoned journal reversal and a new entry in an open period.
6. Take and verify a database backup before production close procedures.

The close-through date is business-scoped. New financial records and edits dated on or before it are rejected. It is a posting lock, not a substitute for an independent review, statutory close, tax filing, or jurisdiction-specific approval workflow.

### Running Migrations

```bash
# Development (SQLite)
flask db upgrade

# Production (PostgreSQL)
python scripts/run_migration.py
# Or
flask db upgrade
```

### Creating a New Migration

```bash
flask db migrate -m "description of change"
flask db upgrade
```

### Rolling Back a Migration

```bash
flask db downgrade -1
```

### Resetting the Database (Development Only)

```bash
# WARNING: Deletes all data
rm -rf migrations/versions/*
flask db migrate -m "initial"
flask db upgrade
python seed.py
```

### Checking Database Health

```bash
# Quick check
python verify_db.py

# Full schema audit
python check_db_schema.py
```

### Verifying Accounting Integrity

```bash
# Via API (authenticated)
curl http://localhost:5000/api/accounting/verify

# Or via Flask shell
flask shell
>>> from app.services.accounting_service import verify_balances
>>> verify_balances(business_id=1)
```

### Superadmin Bootstrap

```bash
flask create-superadmin admin@trackwise.app "Admin Name" "SecurePassword123!"
```

### Running Tests

```bash
pytest
pytest --cov=app --cov-report=html
```

---

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` is set correctly in `.env` or `.env.local`.
- For Neon, ensure you're using the pooled connection string and `sslmode=require` is set.
- Check that `psycopg` or `psycopg2` is installed for PostgreSQL.
- If `DATABASE_URL` is missing and `FLASK_ENV=production`, the app will raise `RuntimeError`.

### Migration Stuck at Old Revision

- Check `alembic_version` table: `SELECT * FROM alembic_version;`
- If a migration failed partially, repair the schema manually or roll back.
- Use `flask db stamp head` to mark all migrations as applied **only** if you're sure the schema is current.

### Alembic Detects Changes on Every Run

- Ensure `SQLALCHEMY_TRACK_MODIFICATIONS` is `False`.
- Check that model `__tablename__` values are consistent.
- Review `compare_type` and `compare_server_default` settings in `migrations/env.py`.
