# Database Schema Reference

This document provides a reference for the TrackWise PostgreSQL database schema. It describes each table, its columns, relationships, and business purpose.

> **Note:** All tables include `business_id` for multi-tenant data isolation unless noted otherwise.

---

## Core Tables

### `businesses`

The tenant root. Every record belongs to a single business.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `name` | VARCHAR(200) | No | — | Business name |
| `tax_id` | VARCHAR(100) | Yes | — | Tax identification number |
| `currency` | VARCHAR(10) | No | `MWK` | Default currency code |
| `fiscal_year_start` | VARCHAR(5) | Yes | `01-01` | Fiscal year start month-day |
| `created_at` | TIMESTAMP | No | UTC now | Record creation timestamp |
| `created_by_superadmin_id` | INTEGER | Yes | — | FK to `super_admins.id` |

**Relationships:** One-to-many with `users`, `chart_of_accounts`, `journal_entries`, `products`, `sales`, `purchases`, `invoices`, `bills`, `payments`, `production_batches`, `subscriptions`, `financial_categories`, `line_items`, `staff`, `warehouses`, `stock_movements`, `bank_statements`.

---

### `users`

Application users within a business.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `email` | VARCHAR(120) | No | — | Unique email address |
| `name` | VARCHAR(120) | Yes | — | Display name |
| `password_hash` | VARCHAR(255) | No | — | Bcrypt hashed password |
| `role` | VARCHAR(20) | No | `viewer` | RBAC role: `admin`, `accountant`, `cashier`, `storekeeper`, `viewer` |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |
| `must_change_password` | BOOLEAN | No | `FALSE` | Force password reset on next login |
| `custom_tasks` | TEXT | Yes | — | JSON or text for custom role tasks |

**Relationships:** Belongs to `businesses`. Creates `journal_entries`, `stock_movements`.

---

### `super_admins`

Platform-level administrators.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `email` | VARCHAR(120) | No | — | Unique email |
| `name` | VARCHAR(120) | No | — | Display name |
| `password_hash` | VARCHAR(255) | No | — | Bcrypt hashed password |

---

## Accounting Tables

### `chart_of_accounts`

Chart of Accounts entries.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `code` | VARCHAR(20) | No | — | Account code (e.g., `1000`, `5000`) |
| `name` | VARCHAR(200) | No | — | Account name |
| `type` | VARCHAR(20) | No | — | `asset`, `liability`, `equity`, `income`, `expense` |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-archive flag |
| `parent_id` | INTEGER | Yes | — | Self-referencing FK for hierarchical accounts |

**Constraints:** `UNIQUE(business_id, code)`

**Relationships:** Parent/child self-referencing. Referenced by `journal_lines`, `bank_statements`.

---

### `journal_entries`

Double-entry journal entry headers.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `entry_date` | TIMESTAMP | No | UTC now | Transaction date |
| `reference_type` | VARCHAR(50) | Yes | — | Source module (e.g., `Invoice`, `Payment`, `JournalEntry`) |
| `reference_id` | INTEGER | Yes | — | ID of the source record |
| `description` | TEXT | No | — | Entry description |
| `created_by` | INTEGER | Yes | — | FK to `users.id` |
| `created_at` | TIMESTAMP | No | UTC now | Record creation timestamp |
| `is_deleted` | BOOLEAN | No | `FALSE` | Soft-delete flag |
| `deleted_by` | INTEGER | Yes | — | FK to `users.id` |
| `deleted_at` | TIMESTAMP | Yes | — | Soft-delete timestamp |

**Relationships:** One-to-many with `journal_lines`.

---

### `journal_lines`

Individual debit/credit lines within a journal entry.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `journal_entry_id` | INTEGER | No | — | FK to `journal_entries.id` |
| `account_id` | INTEGER | No | — | FK to `chart_of_accounts.id` |
| `debit_amount` | NUMERIC(14,2) | No | `0.00` | Debit amount |
| `credit_amount` | NUMERIC(14,2) | No | `0.00` | Credit amount |

**Rules:** Every `journal_entry` must have at least two lines and total debits must equal total credits (within 0.01 tolerance).

**Relationships:** Belongs to `journal_entries`, `chart_of_accounts`.

---

### `audit_logs`

Immutable audit trail for accounting events.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | Yes | — | FK to `businesses.id` |
| `user_id` | INTEGER | Yes | — | FK to `users.id` |
| `action` | VARCHAR(50) | No | — | Action type (e.g., `CREATE`, `UPDATE`, `DELETE`) |
| `table_name` | VARCHAR(100) | No | — | Affected table |
| `record_id` | INTEGER | Yes | — | Affected record ID |
| `old_values` | TEXT | Yes | — | JSON snapshot of old values |
| `new_values` | TEXT | Yes | — | JSON snapshot of new values |
| `timestamp` | TIMESTAMP | No | UTC now | Event timestamp |

---

### `bank_statements`

Bank statement lines for reconciliation.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `account_id` | INTEGER | No | — | FK to `chart_of_accounts.id` (bank account) |
| `statement_date` | TIMESTAMP | No | — | Date of the statement line |
| `description` | VARCHAR(255) | No | — | Transaction description |
| `amount` | NUMERIC(14,2) | No | — | Transaction amount |
| `reference` | VARCHAR(100) | Yes | — | Optional reference |
| `is_reconciled` | BOOLEAN | No | `FALSE` | Reconciliation status |
| `journal_entry_id` | INTEGER | Yes | — | FK to `journal_entries.id` when matched |
| `created_at` | TIMESTAMP | No | UTC now | Record creation timestamp |

**Relationships:** Belongs to `chart_of_accounts`, optionally linked to `journal_entries`.

---

## Inventory Tables

### `products`

Product / item master data.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `sku` | VARCHAR(50) | No | — | Unique stock keeping unit |
| `name` | VARCHAR(200) | No | — | Product name |
| `description` | TEXT | Yes | — | Product description |
| `quantity_in_stock` | INTEGER | No | `0` | Current stock level |
| `low_stock_threshold` | INTEGER | No | `5` | Alert threshold |
| `default_selling_price` | NUMERIC(12,2) | No | `0.00` | Default selling price |
| `warehouse_id` | INTEGER | Yes | — | FK to `warehouses.id` |
| `category` | VARCHAR(100) | Yes | — | Product category |
| `unit_of_measure` | VARCHAR(50) | Yes | — | UOM (e.g., `kg`, `pcs`) |
| `barcode` | VARCHAR(100) | Yes | — | Unique barcode |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Constraints:** `UNIQUE(sku)`, `UNIQUE(barcode)`

---

### `warehouses`

Storage locations.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `name` | VARCHAR(200) | No | — | Warehouse name |
| `location` | VARCHAR(200) | Yes | — | Physical location |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Relationships:** One-to-many with `products`, `stock_movements`.

---

### `stock_movements`

Inventory movement records.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `product_id` | INTEGER | No | — | FK to `products.id` |
| `warehouse_id` | INTEGER | Yes | — | FK to `warehouses.id` |
| `from_warehouse_id` | INTEGER | Yes | — | Source warehouse for transfers |
| `to_warehouse_id` | INTEGER | Yes | — | Destination warehouse for transfers |
| `type` | VARCHAR(20) | No | — | Movement type: `PURCHASE`, `SALE`, `PRODUCTION_INPUT`, `PRODUCTION_OUTPUT`, `TRANSFER`, `ADJUSTMENT` |
| `quantity` | INTEGER | No | `0` | Movement quantity |
| `unit_cost` | NUMERIC(12,2) | Yes | — | Unit cost at time of movement |
| `reference_type` | VARCHAR(50) | Yes | — | Source module |
| `reference_id` | INTEGER | Yes | — | Source record ID |
| `created_by` | INTEGER | Yes | — | FK to `users.id` |
| `notes` | TEXT | Yes | — | Optional notes |
| `timestamp` | TIMESTAMP | No | UTC now | Movement timestamp |

---

### `stock_transactions`

Legacy FIFO cost layers. Used by the FIFO costing engine.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `product_id` | INTEGER | No | — | FK to `products.id` |
| `quantity` | INTEGER | No | `0` | Original quantity |
| `remaining_quantity` | INTEGER | No | `0` | Quantity not yet consumed |
| `unit_cost` | NUMERIC(12,2) | No | `0.00` | Cost per unit |
| `transaction_type` | VARCHAR(30) | No | `PURCHASE` | Type of transaction |
| `reference_type` | VARCHAR(50) | Yes | — | Source module |
| `reference_id` | INTEGER | Yes | — | Source record ID |
| `timestamp` | TIMESTAMP | No | UTC now | Transaction timestamp |

---

## Sales & Purchase Tables

### `customers`

Customer master data.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `customer_id` | VARCHAR(20) | Yes | — | Unique customer code |
| `name` | VARCHAR(200) | No | — | Customer name |
| `phone` | VARCHAR(50) | Yes | — | Contact phone |
| `email` | VARCHAR(120) | Yes | — | Contact email |
| `address` | TEXT | Yes | — | Physical address |
| `bank_name` | VARCHAR(200) | Yes | — | Bank name |
| `bank_branch` | VARCHAR(200) | Yes | — | Bank branch |
| `bank_account_number` | VARCHAR(50) | Yes | — | Bank account number |
| `credit_limit` | NUMERIC(14,2) | Yes | — | Credit limit |
| `opening_balance` | NUMERIC(14,2) | No | `0.00` | Opening AR balance |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Constraints:** `UNIQUE(customer_id)`

---

### `suppliers`

Supplier master data.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `supplier_id` | VARCHAR(20) | Yes | — | Unique supplier code |
| `name` | VARCHAR(200) | No | — | Supplier name |
| `phone` | VARCHAR(50) | Yes | — | Contact phone |
| `email` | VARCHAR(120) | Yes | — | Contact email |
| `address` | TEXT | Yes | — | Physical address |
| `bank_name` | VARCHAR(200) | Yes | — | Bank name |
| `bank_branch` | VARCHAR(200) | Yes | — | Bank branch |
| `bank_account_number` | VARCHAR(50) | Yes | — | Bank account number |
| `payment_terms` | VARCHAR(100) | Yes | — | Payment terms |
| `opening_balance` | NUMERIC(14,2) | No | `0.00` | Opening AP balance |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Constraints:** `UNIQUE(supplier_id)`

---

### `invoices`

Sales invoice headers.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `customer_id` | INTEGER | Yes | — | FK to `customers.id` |
| `invoice_number` | VARCHAR(60) | Yes | — | Human-readable invoice number |
| `invoice_date` | TIMESTAMP | No | UTC now | Invoice date |
| `due_date` | TIMESTAMP | Yes | — | Payment due date |
| `subtotal` | NUMERIC(14,2) | No | `0.00` | Sum of line totals before tax |
| `tax_amount` | NUMERIC(14,2) | No | `0.00` | Total tax |
| `total_amount` | NUMERIC(14,2) | No | `0.00` | Grand total |
| `status` | VARCHAR(30) | No | `draft` | `draft`, `issued`, `paid`, `overdue`, `void` |
| `notes` | TEXT | Yes | — | Optional notes |

**Relationships:** Belongs to `customers`. One-to-many with `invoice_items`, `receipts`, `sales`.

---

### `invoice_items`

Sales invoice line items.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `invoice_id` | INTEGER | No | — | FK to `invoices.id` |
| `product_id` | INTEGER | Yes | — | FK to `products.id` |
| `description` | TEXT | Yes | — | Line description |
| `quantity` | INTEGER | No | `1` | Quantity |
| `unit_price` | NUMERIC(12,2) | No | `0.00` | Unit price |
| `line_total` | NUMERIC(14,2) | No | `0.00` | `quantity * unit_price` |
| `tax_rate` | NUMERIC(5,2) | No | `0.00` | Tax rate percentage |
| `tax_amount` | NUMERIC(14,2) | No | `0.00` | Tax amount for this line |
| `tax_inclusive` | BOOLEAN | No | `FALSE` | Whether unit_price includes tax |

**Relationships:** Belongs to `invoices`, optionally `products`.

---

### `receipts`

Payment receipts against invoices.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `customer_id` | INTEGER | Yes | — | FK to `customers.id` |
| `invoice_id` | INTEGER | Yes | — | FK to `invoices.id` |
| `receipt_date` | TIMESTAMP | No | UTC now | Receipt date |
| `amount` | NUMERIC(14,2) | No | `0.00` | Payment amount |
| `payment_method` | VARCHAR(30) | No | `cash` | Payment method |
| `reference` | VARCHAR(100) | Yes | — | Optional reference |
| `notes` | TEXT | Yes | — | Optional notes |

---

### `bills`

Purchase bill headers.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `supplier_id` | INTEGER | Yes | — | FK to `suppliers.id` |
| `bill_number` | VARCHAR(60) | Yes | — | Human-readable bill number |
| `bill_date` | TIMESTAMP | No | UTC now | Bill date |
| `due_date` | TIMESTAMP | Yes | — | Payment due date |
| `subtotal` | NUMERIC(14,2) | No | `0.00` | Sum of line totals before tax |
| `tax_amount` | NUMERIC(14,2) | No | `0.00` | Total tax |
| `total_amount` | NUMERIC(14,2) | No | `0.00` | Grand total |
| `status` | VARCHAR(30) | No | `draft` | `draft`, `issued`, `paid`, `overdue`, `void` |
| `notes` | TEXT | Yes | — | Optional notes |

**Relationships:** Belongs to `suppliers`. One-to-many with `bill_items`, `payments`.

---

### `bill_items`

Purchase bill line items.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `bill_id` | INTEGER | No | — | FK to `bills.id` |
| `product_id` | INTEGER | Yes | — | FK to `products.id` |
| `description` | TEXT | Yes | — | Line description |
| `quantity` | INTEGER | No | `1` | Quantity |
| `unit_cost` | NUMERIC(12,2) | No | `0.00` | Unit cost |
| `line_total` | NUMERIC(14,2) | No | `0.00` | `quantity * unit_cost` |
| `tax_rate` | NUMERIC(5,2) | No | `0.00` | Tax rate percentage |
| `tax_amount` | NUMERIC(14,2) | No | `0.00` | Tax amount for this line |
| `tax_inclusive` | BOOLEAN | No | `FALSE` | Whether unit_cost includes tax |

**Relationships:** Belongs to `bills`, optionally `products`.

---

### `payments`

Unified payment records (supplier and staff payments).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `supplier_id` | INTEGER | Yes | — | FK to `suppliers.id` |
| `bill_id` | INTEGER | Yes | — | FK to `bills.id` |
| `category_id` | INTEGER | Yes | — | FK to `financial_categories.id` |
| `line_item_id` | INTEGER | Yes | — | FK to `line_items.id` |
| `staff_id` | INTEGER | Yes | — | FK to `staff.id` |
| `payment_date` | TIMESTAMP | No | UTC now | Payment date |
| `payee_type` | VARCHAR(20) | No | `supplier` | `supplier` or `staff` |
| `description` | TEXT | Yes | — | Payment description |
| `amount` | NUMERIC(14,2) | No | `0.00` | Payment amount |
| `payment_mode` | VARCHAR(30) | No | `cash` | `cash`, `bank_transfer`, `mobile_money`, `cheque`, `card` |
| `reference` | VARCHAR(100) | Yes | — | Optional reference |
| `status` | VARCHAR(20) | No | `pending` | `pending`, `approved`, `rejected` |

**Relationships:** Belongs to `suppliers`, optionally `bills`, `financial_categories`, `line_items`, `staff`.

---

## Production Tables

### `production_batches`

Production batch headers.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `batch_number` | VARCHAR(60) | No | — | Unique batch number |
| `production_date` | TIMESTAMP | No | UTC now | Production date |
| `product_id` | INTEGER | No | — | FK to `products.id` (finished good) |
| `quantity_produced` | INTEGER | No | `0` | Quantity produced |
| `status` | VARCHAR(30) | No | `planned` | `planned`, `in_progress`, `completed`, `cancelled` |
| `notes` | TEXT | Yes | — | Optional notes |
| `created_by` | INTEGER | Yes | — | FK to `users.id` |
| `completed_at` | TIMESTAMP | Yes | — | Completion timestamp |

**Constraints:** `UNIQUE(batch_number)`

**Relationships:** One-to-many with `material_usages`, `finished_good_outputs`.

---

### `material_usages`

Raw material consumption records.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `production_batch_id` | INTEGER | No | — | FK to `production_batches.id` |
| `product_id` | INTEGER | No | — | FK to `products.id` (raw material) |
| `quantity_consumed` | INTEGER | No | `0` | Quantity consumed |
| `unit_cost_at_consumption` | NUMERIC(12,2) | No | `0.00` | Cost per unit at time of consumption |

---

### `finished_good_outputs`

Finished goods produced.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `production_batch_id` | INTEGER | No | — | FK to `production_batches.id` |
| `product_id` | INTEGER | No | — | FK to `products.id` (finished good) |
| `quantity` | INTEGER | No | `0` | Quantity produced |
| `unit_cost` | NUMERIC(12,2) | No | `0.00` | Calculated unit cost |

---

## Subscription Tables

### `plans`

Subscription plan definitions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `name` | VARCHAR(100) | No | — | Plan name (e.g., `Free`, `Starter`) |
| `price` | NUMERIC(10,2) | No | `0.00` | Monthly price |
| `max_users` | INTEGER | No | `1` | Maximum users allowed |
| `features` | TEXT | Yes | — | JSON string of enabled features |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Relationships:** One-to-many with `subscriptions`.

---

### `subscriptions`

Business subscription records.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `plan_id` | INTEGER | No | — | FK to `plans.id` |
| `status` | VARCHAR(30) | No | `active` | `active`, `cancelled`, `past_due` |
| `start_date` | TIMESTAMP | No | UTC now | Subscription start |
| `renewal_date` | TIMESTAMP | Yes | — | Next renewal date |
| `stripe_subscription_id` | VARCHAR(255) | Yes | — | Stripe subscription ID |
| `payment_method` | VARCHAR(50) | Yes | — | Last 4 digits or type |

**Relationships:** Belongs to `businesses`, `plans`.

---

## Payments Hub Tables

### `financial_categories`

OPEX/COGS classification categories.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `name` | VARCHAR(100) | No | — | Category name |
| `code` | VARCHAR(10) | No | — | Short code (e.g., `COS`, `OPEX`) |
| `description` | TEXT | Yes | — | Category description |
| `sort_order` | INTEGER | No | `0` | Display order |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Constraints:** `UNIQUE(business_id, code)`

**Relationships:** One-to-many with `line_items`, `payments`.

---

### `line_items`

Granular expense/payment line items.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `category_id` | INTEGER | No | — | FK to `financial_categories.id` |
| `name` | VARCHAR(200) | No | — | Line item name |
| `code` | VARCHAR(20) | Yes | — | Short code |
| `account_code` | VARCHAR(20) | Yes | — | Maps to Chart of Accounts code |
| `description` | TEXT | Yes | — | Description |
| `sort_order` | INTEGER | No | `0` | Display order |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

---

### `staff`

Employee / staff records.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `staff_id` | VARCHAR(20) | Yes | — | Unique staff code |
| `name` | VARCHAR(200) | No | — | Full name |
| `phone` | VARCHAR(50) | Yes | — | Contact phone |
| `email` | VARCHAR(120) | Yes | — | Contact email |
| `role` | VARCHAR(100) | Yes | — | Job role |
| `department` | VARCHAR(100) | Yes | — | Department |
| `is_active` | BOOLEAN | No | `TRUE` | Soft-active flag |

**Constraints:** `UNIQUE(staff_id)`

**Relationships:** One-to-many with `payments`.

---

## Approval Tables

### `approval_configs`

Workflow configuration for approval-gated transactions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `transaction_type` | VARCHAR(50) | No | — | e.g., `payment`, `journal_entry` |
| `is_active` | BOOLEAN | No | `TRUE` | Whether this workflow is active |

---

### `approval_requests`

Pending approval requests.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `business_id` | INTEGER | No | — | FK to `businesses.id` |
| `transaction_type` | VARCHAR(50) | No | — | Type of transaction |
| `transaction_id` | INTEGER | No | — | ID of the pending transaction |
| `created_by` | INTEGER | No | — | FK to `users.id` |
| `status` | VARCHAR(20) | No | `pending` | `pending`, `approved`, `rejected` |
| `data` | TEXT | Yes | — | JSON payload of the proposed change |

---

### `approval_actions`

Individual approval/rejection actions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | Auto | Primary key |
| `approval_request_id` | INTEGER | No | — | FK to `approval_requests.id` |
| `user_id` | INTEGER | No | — | FK to `users.id` (actor) |
| `action` | VARCHAR(20) | No | — | `approve` or `reject` |
| `comments` | TEXT | Yes | — | Optional comments |
| `timestamp` | TIMESTAMP | No | UTC now | Action timestamp |

---

## Legacy Tables

### `purchases`, `purchase_items`, `sales`, `sale_items`, `expenses`, `settings`

These tables exist for backward compatibility with the legacy FIFO service. New features should use the accounting-native tables (`invoices`, `bills`, `journal_entries`, etc.) instead.

---

## Indexes

Key indexes are defined via SQLAlchemy model definitions:

- All foreign key columns are indexed (`business_id`, `user_id`, `product_id`, etc.).
- `chart_of_accounts` has a unique constraint on `(business_id, code)`.
- `products` has unique constraints on `sku` and `barcode`.
- `customers` and `suppliers` have unique constraints on their ID fields.

---

## Migrations

Database schema changes are managed via Alembic migrations in `migrations/versions/`. Migration filenames follow the pattern:

```
{timestamp}_{description}.py
```

Example: `20260817_add_bank_statements.py`

To create a new migration:

```bash
flask db migrate -m "description of change"
flask db upgrade
```
