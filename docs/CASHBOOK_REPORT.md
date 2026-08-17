# Cashbook Report

**Project:** TrackWise (Flask-based SaaS ERP-lite)  
**Document Date:** 2026-08-17  
**Scope:** Cashbook report feature — purpose, data flow, usage, fields, and implementation details

---

## 1. Executive Summary

The **Cashbook Report** provides a chronological view of all cash and bank transactions for a business. It combines the Cash (account `1000`) and Bank (account `1100`) accounts into a single, time-ordered register with running balances, summary totals, and date-range filtering.

The cashbook is derived entirely from `JournalEntry` and `JournalLine` records — no manual edits or separate data store is required. It follows the same read-only, double-entry-derived pattern used by all TrackWise reports.

---

## 2. What Is a Cashbook Report

A cashbook (also called a cash register or cash book) is a fundamental accounting record that tracks all cash inflows and outflows. In TrackWise, it covers both:

| Account | Code | Type | Description |
| --------- | ------ | ------ | ------------- |
| Cash | `1000` | Asset | Physical cash on hand |
| Bank | `1100` | Asset | Bank account balances |

Every receipt, payment, sale, purchase, and expense that touches cash or a bank account appears in the cashbook. This makes it the primary tool for:

- Reconciling physical cash at period end
- Verifying bank deposits and withdrawals
- Detecting missing or duplicate transactions
- Auditing payment and receipt patterns
- Preparing bank-reconciliation schedules

---

## 3. Data Flow

```flow
Sale / Purchase / Expense / Payment / Receipt
          │
          ▼
    JournalEntry (balanced)
          │
          ▼
    JournalLine (Dr Cash 1000 / Cr Cash 1000
                  Dr Bank 1100 / Cr Bank 1100)
          │
          ▼
    Cashbook Report (read-only aggregation)
```

**Key points:**

- Every financial transaction in TrackWise posts a balanced `JournalEntry` with two or more `JournalLine` records.
- When cash or bank is involved, at least one line targets account `1000` or `1100`.
- The cashbook report queries only those lines, ordered chronologically.
- No report data is stored or cached — it is computed fresh from journal data on every request.

---

## 4. How to Use

### 4.1 Navigation

1. Log in to TrackWise.
2. Go to **Reports** → **Cashbook** (or navigate directly to `/reports/cashbook`).
3. The report loads with the current business's cash and bank transactions.

### 4.2 Date Filtering

The cashbook supports **date-range filtering**:

| Filter | Behavior |
| -------- | ---------- |
| No dates | Shows all cash/bank transactions for the business |
| Start date only | Shows transactions from that date onward |
| End date only | Shows transactions up to and including that date |
| Both dates | Shows transactions within the range |

**Usage:**

- Select a start date and/or end date in the filter form.
- Click **Apply Filter** to refresh the report.
- Click **Reset** to clear filters and show all transactions.

### 4.3 Reading the Report

#### Summary Cards

Four cards at the top of the report provide at-a-glance totals:

| Card | Field | Meaning |
| ------ | ------- | --------- |
| Opening Balance | `opening_balance` | Cash + Bank balance before the start date |
| Total Receipts | `total_debits` | Sum of all money received (Dr entries on 1000/1100) in the period |
| Total Payments | `total_credits` | Sum of all money paid out (Cr entries on 1000/1100) in the period |
| Closing Balance | `closing_balance` | `opening_balance + total_debits - total_credits` |

#### Transaction Table

Each row represents one journal line on a cash or bank account:

| Column | Source | Description |
| -------- | -------- | ------------- |
| Date | `JournalEntry.entry_date` | Transaction date |
| Account | `ChartOfAccounts.code` + `name` | Cash (`1000`) or Bank (`1100`) |
| Description | `JournalEntry.description` | Transaction description |
| Reference | `JournalEntry.reference_type` + `reference_id` | Source document (e.g., `Sale #5`, `Purchase #3`) |
| Receipt (Dr) | `JournalLine.debit_amount` | Money coming into cash/bank |
| Payment (Cr) | `JournalLine.credit_amount` | Money going out of cash/bank |
| Balance | Computed | Running balance after this transaction |

#### Running Balance Logic

For asset accounts (Cash, Bank), the running balance follows double-entry conventions:

```formula
balance = previous_balance + debit_amount - credit_amount
```

- **Receipts (Dr)** increase the balance.
- **Payments (Cr)** decrease the balance.

#### Pagination

Large cashbooks are paginated for performance:

- **Default:** 25 rows per page
- **Options:** 10, 25, 50, 100
- Use the **Previous / Next** links to navigate pages.

---

## 5. Report Fields Reference

### Service Return Shape

The `get_cashbook()` function in `app/services/reports/cashbook.py` returns:

```python
{
    'entries': [
        {
            'date': datetime,           # Journal entry date
            'entry_id': int,            # Journal entry ID
            'description': str,         # Entry description
            'reference_type': str,      # Source model (Sale, Purchase, Payment, etc.)
            'reference_id': int,        # Source record ID
            'account_code': str,        # '1000' or '1100'
            'account_name': str,        # 'Cash' or 'Bank'
            'debit': float,             # Money received (Dr)
            'credit': float,            # Money paid (Cr)
            'balance': float,           # Running balance after this line
            'created_by_name': str,     # User who created the entry
            'created_at': datetime,     # Entry creation timestamp
        },
        ...
    ],
    'accounts': [                      # Cash + Bank ChartOfAccounts records
        ChartOfAccounts(id=..., code='1000', name='Cash', ...),
        ChartOfAccounts(id=..., code='1100', name='Bank', ...),
    ],
    'total_debits': float,             # Sum of all debits in the period
    'total_credits': float,            # Sum of all credits in the period
    'net_cash_flow': float,            # total_debits - total_redits
    'opening_balance': float,          # Balance before start_date
    'closing_balance': float,          # Balance after end_date
    'start_date': datetime | None,     # Applied filter start
    'end_date': datetime | None,       # Applied filter end
    # Pagination fields (applied by route after service call):
    'page': int,
    'per_page': int,
    'total': int,
    'pages': int,
}
```

### Query Parameters

| Parameter | Type | Required | Description |
| ----------- | ------ | ---------- | ------------- |
| `start_date` | `YYYY-MM-DD` | No | Filter transactions from this date |
| `end_date` | `YYYY-MM-DD` | No | Filter transactions up to this date |
| `page` | Integer | No | Page number (default: 1) |
| `per_page` | Integer (10-100) | No | Rows per page (default: 25) |

### URL

```bash
/reports/cashbook
/reports/cashbook?start_date=2026-01-01&end_date=2026-06-30
/reports/cashbook?start_date=2026-01-01&end_date=2026-06-30&page=2&per_page=50
```

---

## 6. Technical Implementation

### 6.1 Architecture Layer

The cashbook follows the standard TrackWise report 3-layer pattern:

| Layer | File | Responsibility |
| ------- | ------ | ---------------- |
| **Service** | `app/services/reports/cashbook.py` | Query `JournalLine`/`JournalEntry`, filter to 1000/1100, compute running balance |
| **Route** | `app/reports/routes.py` → `cashbook()` | Parse filters, call service, paginate, render template |
| **Template** | `templates/reports.html` → `{% if report_type == 'cashbook' %}` | Render dropdown, filters, summary cards, transaction table, pagination |

### 6.2 Service Logic

The `get_cashbook(business_id, start_date, end_date)` function:

1. **Resolves accounts** — Finds the business's Cash (`1000`) and Bank (`1100`) `ChartOfAccounts` records.
2. **Queries journal lines** — Joins `JournalLine` → `JournalEntry` → `ChartOfAccounts`, filtering by `business_id` and the two account IDs.
3. **Applies date filters** — `JournalEntry.entry_date >= start_date` and/or `<= end_date` when provided.
4. **Orders chronologically** — `entry_date ASC`, `entry_id ASC`, `line_id ASC`.
5. **Computes running balance** — Iterates lines in order, accumulating `debit - credit` (asset convention).
6. **Computes summary totals** — `total_debits`, `total_credits`, `net_cash_flow`.
7. **Computes opening balance** — Queries all cash/bank lines before `start_date` and sums their net.
8. **Computes closing balance** — `opening_balance + net_cash_flow`.
9. **Resolves user names** — Batch-loads `User` records for `created_by` IDs to avoid N+1 queries.
10. **Returns dict** — Structured data consumed by the route and template.

### 6.3 Data Model Relationships

```model
Business (business_id)
  └── ChartOfAccounts (code 1000, 1100)
  └── JournalEntry (business_id)
        └── JournalLine (account_id → ChartOfAccounts.id)
              ├── debit_amount  (for Cash/Bank: money in)
              └── credit_amount (for Cash/Bank: money out)
```

### 6.4 Multi-Tenancy

All queries are scoped to the authenticated user's `business_id` via `g.business_id` (set in `before_request`). Users from one business cannot see another business's cashbook entries.

---

## 7. Usage Examples

### Example 1: View All Transactions

Navigate to `/reports/cashbook` with no filters to see all cash and bank transactions for the business.

### Example 2: Monthly Cashbook

Filter to a specific month:

```bash
/reports/cashbook?start_date=2026-07-01&end_date=2026-07-31
```

Use the summary cards to verify:

- Opening balance on July 1
- Total receipts (sales, customer payments) in July
- Total payments (purchases, expenses) in July
- Closing balance on July 31

### Example 3: Paginated Review

For businesses with hundreds of transactions:

```bash
/reports/cashbook?start_date=2026-01-01&end_date=2026-06-30&per_page=50
```

---

## 8. Known Limitations

| Limitation | Severity | Details |
| ------------ | ---------- | --------- |
| No CSV/Excel export | Medium | Report is view-only; no download option yet. |
| No print stylesheet | Medium | Printing the page includes sidebar/navigation. |
| No PDF generation | Medium | Background PDF task references missing templates; affects all reports. |
| No JSON API | Low | No `/api/reports/cashbook` endpoint; data is only available via HTML. |
| No account filter | Low | Cash and Bank are combined; no dropdown to view one account at a time. |
| Hardcoded account codes | Low | Service uses literal strings `'1000'` and `'1100'` instead of dynamic lookup. |

---

## 9. Future Enhancements

| Enhancement | Priority | Description |
| ------------- | ---------- | ------------- |
| CSV/Excel export | P1 | Allow downloading the cashbook as a spreadsheet. |
| Account filter dropdown | P2 | Let users view Cash only, Bank only, or both combined. |
| Print stylesheet | P1 | Add `@media print` rules for clean financial statement printing. |
| PDF generation | P1 | Create `templates/reports/cashbook_pdf.html` and wire into `report_tasks.py`. |
| Bank reconciliation integration | P0 | Link cashbook entries to `BankStatement` reconciliation status. |
| Drill-down to source | P2 | Make reference types/IDs clickable links to the source transaction. |
| Search/filter by reference | P2 | Filter cashbook by reference type (Sale, Purchase, Payment, etc.). |
| Opening balance edit | P2 | Allow accountants to set/adjust opening balances for new fiscal periods. |

---

## 10. Testing

The cashbook report includes a unit test in `tests/test_reports.py`:

```python
def test_cashbook(self):
    from app.services.reports import get_cashbook

    # Record a purchase (cash/bank outflow)
    record_purchase(...)
    
    # Record a sale (cash/bank inflow)
    record_sale(...)
    
    cb = get_cashbook(self.business.id)
    
    self.assertIn('entries', cb)
    self.assertIn('total_debits', cb)
    self.assertIn('total_credits', cb)
    self.assertIn('opening_balance', cb)
    self.assertIn('closing_balance', cb)
    self.assertIn('net_cash_flow', cb)
```

Run the test:

```bash
pytest tests/test_reports.py::TestReportServices::test_cashbook -v
```

---

## 11. Related Documentation

- **[Reports Suite](../README.md#reports)** — Overview of all financial reports
- **[General Ledger](general_ledger.md)** — All account transactions (cashbook is a filtered subset)
- **[Double-Entry Accounting](ARCHITECTURE.md)** — How journal entries enforce balanced books
- **[Chart of Accounts](DATABASE.md)** — Account codes and types
- **[Bank Reconciliation](accounting/)** — Matching bank statements to cashbook entries
- **[Reports Action Plan](../.kilo/plans/cashbook-report-implementation-plan.md)** — Implementation plan for this report

---

## 12. Support

For issues or questions about the cashbook report:

1. Verify that transactions are posting correctly to Cash (`1000`) or Bank (`1100`) in the General Ledger.
2. Check that `ChartOfAccounts` records for codes `1000` and `1100` exist and are active.
3. Confirm the user has `accountant`, `admin`, or `viewer` role (reports require login).
