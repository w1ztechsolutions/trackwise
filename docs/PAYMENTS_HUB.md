# Payments Hub

> Comprehensive payment management system for TrackWise

The Payments Hub centralizes all outgoing payments — supplier payments, staff salaries, and operating expenses — with full double-entry accounting integration.

---

## 1. Overview

The Payments Hub replaces the legacy `/expenses` route with a unified payment system that:

- Supports **supplier payments** (Accounts Payable)
- Supports **staff/expense payments** (direct expense accounts)
- Maps payments to **financial statement categories** and **line items**
- Creates **journal entries** automatically for every payment
- Integrates with the **double-entry accounting engine**

---

## 2. Database Models

### 2.1 FinancialCategory

Represents high-level financial statement categories:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `name` | String | Category name (e.g., "Cost of Sales") |
| `statement_type` | String | `income_statement`, `balance_sheet`, etc. |
| `business_id` | Integer | Multi-tenant scoping |

### 2.2 LineItem

Sub-categories linked to a FinancialCategory:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `name` | String | Line item name (e.g., "Salaries") |
| `category_id` | Integer | FK to FinancialCategory |
| `business_id` | Integer | Multi-tenant scoping |

### 2.3 Staff

Staff/employee records for salary payments:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `name` | String | Staff full name |
| `position` | String | Job title/position |
| `business_id` | Integer | Multi-tenant scoping |

### 2.4 Payment (Updated)

The `Payment` model was extended with new fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `amount` | Numeric | Payment amount |
| `date` | DateTime | Payment date |
| `payment_mode` | String | `cash`, `bank_transfer`, `mobile_money`, `cheque`, `card` |
| `reference` | String | External reference (cheque no., transaction ID) |
| `category_id` | Integer | FK to FinancialCategory |
| `line_item_id` | Integer | FK to LineItem |
| `description` | Text | Payment description/notes |
| `staff_id` | Integer | FK to Staff (nullable) |
| `payee_type` | String | `supplier` or `staff` |
| `business_id` | Integer | Multi-tenant scoping |

---

## 3. Seed Data

Default financial categories and line items are seeded via `app/services/subscription_service.py` or `seed.py`.

### 3.1 Financial Categories

| Category | Statement Type |
|----------|---------------|
| Cost of Sales | income_statement |
| Operating Expenses | income_statement |
| Administrative Expenses | income_statement |
| Selling Expenses | income_statement |
| Finance Costs | income_statement |
| Other Income | income_statement |
| Tax | income_statement |

### 3.2 Line Items (Examples)

Each category has associated line items. For example:

**Operating Expenses:**
- Salaries
- Rent
- Utilities
- Marketing
- Maintenance

**Cost of Sales:**
- Raw Materials
- Production Labor
- Factory Overhead

---

## 4. Payment Flow

```
User fills form → POST /payments →
   1. Validate fields
   2. Create Payment record
   3. Call _post_payment_accounting()
   4. Create JournalEntry + JournalLine (double-entry)
   5. Commit transaction
```

### 4.1 Supplier Payments

When `payee_type = supplier`:

| Account | Debit | Credit |
|---------|-------|--------|
| Accounts Payable (AP) | ✓ | |
| Cash/Bank | | ✓ |

### 4.2 Staff/Expense Payments

When `payee_type = staff`:

| Account | Debit | Credit |
|---------|-------|--------|
| Expense Account (by line item) | ✓ | |
| Cash/Bank | | ✓ |

The expense account is determined by the selected `line_item_id` mapping.

---

## 5. API Endpoints

### POST /payments

Create a new payment.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount` | Numeric | Yes | Payment amount |
| `date` | String | Yes | Payment date (ISO format) |
| `payment_mode` | String | Yes | `cash`, `bank_transfer`, `mobile_money`, `cheque`, `card` |
| `reference` | String | No | External reference number |
| `category_id` | Integer | Yes | FK to FinancialCategory |
| `line_item_id` | Integer | Yes | FK to LineItem |
| `description` | String | No | Payment description |
| `payee_type` | String | Yes | `supplier` or `staff` |
| `staff_id` | Integer | Conditional | Required if `payee_type = staff` |
| `supplier_id` | Integer | Conditional | Required if `payee_type = supplier` |

**Response:**

```json
{
  "success": true,
  "payment_id": 42,
  "message": "Payment recorded successfully"
}
```

### GET /payments

List payments for the current business.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | String | Filter from date (ISO format) |
| `end_date` | String | Filter to date (ISO format) |
| `category_id` | Integer | Filter by category |
| `payee_type` | String | Filter by `supplier` or `staff` |

**Response:**

```json
{
  "payments": [
    {
      "id": 42,
      "amount": "1500.00",
      "date": "2026-08-15",
      "payment_mode": "bank_transfer",
      "reference": "TXN-001",
      "category": "Operating Expenses",
      "line_item": "Salaries",
      "description": "Monthly salary - John Doe",
      "payee_type": "staff",
      "payee_name": "John Doe"
    }
  ]
}
```

---

## 6. Frontend

The Payments Hub UI (`templates/payments.html`) includes:

### 6.1 Form Fields

1. **Financial Category** — Dropdown selector
2. **Line Item** — Dynamic dropdown filtered by selected category
3. **Payment Description** — Text input
4. **Payee Type** — Radio buttons (`supplier` / `staff`)
5. **Payee Selector** — Conditional dropdown:
   - Supplier Name (when `payee_type = supplier`)
   - Staff Name (when `payee_type = staff`)
6. **Amount** — Numeric input
7. **Payment Mode** — Dropdown: Cash, Bank Transfer, Mobile Money, Cheque, Card
8. **Reference** — Text input (optional)

### 6.2 Table Columns

| Column | Description |
|--------|-------------|
| Date | Payment date |
| Payee | Supplier or Staff name |
| Category | Financial category |
| Line Item | Specific line item |
| Description | Payment description |
| Amount | Payment amount |
| Mode | Payment method |
| Reference | External reference |

### 6.3 Dashboard Integration

The dashboard (`templates/dashboard.html`) includes a **Recent Payments** table showing the latest payments across all categories.

---

## 7. Accounting Integration

### 7.1 Service Method

The accounting logic is implemented in `app/services/fifo_service.py`:

```python
def _post_payment_accounting(self, payment, business_id):
    """Create journal entries for a payment."""
```

### 7.2 Journal Entry Creation

For every payment, the system:

1. Creates a `JournalEntry` with a unique reference
2. Creates `JournalLine` records for debit and credit
3. Validates that debits = credits
4. Commits the transaction atomically

### 7.3 Account Mapping

Line items are mapped to chart of accounts via a predefined mapping in the service layer. This ensures that each payment category posts to the correct expense or liability account.

---

## 8. Migration

Database changes were applied via `scripts/migrate.py`:

- Created tables: `financial_categories`, `line_items`, `staff`
- Altered `payments` table with new columns
- Verified against Neon PostgreSQL

---

## 9. Deprecation Notes

The legacy `/expenses` route (`app/expenses/routes.py`) now redirects to `/payments` with an informational deprecation message. All new payment functionality should use the Payments Hub.

---

## 10. Key Files

| File | Purpose |
|------|---------|
| `models.py` | FinancialCategory, LineItem, Staff, updated Payment |
| `app/models/__init__.py` | Updated model imports |
| `services/fifo_service.py` | `_post_payment_accounting()` method |
| `app/purchases/routes.py` | Payments route (GET/POST) |
| `app/dashboard/routes.py` | Recent payments data for dashboard |
| `templates/payments.html` | Payment form and table |
| `templates/dashboard.html` | Recent payments table |
| `app/expenses/routes.py` | Redirect to payments |
| `seed.py` | Financial categories and line items seed data |
| `scripts/migrate.py` | Database migration script |
