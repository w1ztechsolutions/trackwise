# Chart of Accounts Seeding Tool — Implementation Plan

## 1. Goal

Add a **"Need Headstart"** button to the Chart of Accounts page that opens a hierarchical selection interface, allowing the user to browse a professionally structured chart of accounts taxonomy, select specific accounts, and bulk-import them into their live COA with proper parent-child relationships, codes, and types.

---

## 2. Existing Context

| Component | Location / Status |
| ----------- | ------------------- |
| **COA Model** | `app/models/accounting.py` — `ChartOfAccounts` with `business_id`, `code`, `name`, `type`, `is_active`, `parent_id` |
| **COA Routes** | `app/accounting/routes.py` — CRUD via HTML forms only; no REST endpoints |
| **COA Template** | `templates/chart_of_accounts.html` — server-rendered Bootstrap 5 table with Add/Edit/Archive modals |
| **Seeder** | `seed.py` — static flat list of 17 accounts; no hierarchy, no subtotals |
| **Existing API** | `app/api/routes.py` — products/suppliers/verify only; no COA endpoints |
| **Testing** | `tests/test_accounting.py` — unittest style, Flask test client |

**Key gap**: No "Need Headstart" button exists. No hierarchical selection UI exists. No subtotaling logic exists. No REST endpoint for bulk COA creation exists.

---

## 3. Functional Workflow & User Journey

### Step 1 — Entry Point

- User navigates to **Chart of Accounts** (`/accounting/chart-of-accounts`).
- If the business has **zero accounts**, the empty-state message is replaced with a prominent **"Need Headstart"** button.
- If the business has accounts, a secondary **"Need Headstart"** button appears alongside **"Add Account"** in the header bar.

### Step 2 — Open Seeder Modal

- Clicking **"Need Headstart"** opens a full-screen or large modal overlay.
- The modal displays the **hierarchical taxonomy** in a collapsible tree:
  - Major Category (e.g., Revenue, Expenses, Assets, Liabilities, Equity)
  - Sub-category (e.g., Operating Revenue, Cost of Sales)
  - Account Type (e.g., Current Asset, Non-Current Asset)
  - Specific Account (e.g., Cash at Bank, Finished Goods Inventory)
- Each leaf node (Specific Account) has a **checkbox** for selection.
- Parent nodes are **expandable/collapsible** but not individually selectable (selection happens at the leaf level only).

### Step 3 — Selection & Preview

- User checks desired accounts. A **live counter** shows "X accounts selected".
- A **"Preview Selected"** panel lists selected accounts with their proposed code and name, grouped by Major Category.
- User can **deselect** any account from the preview panel.

### Step 4 — Import

- User clicks **"Import Selected Accounts"**.
- Frontend POSTs a JSON array of selected `{code, name, type, parent_code}` objects to a new backend endpoint.
- Backend validates, deduplicates, and bulk-inserts.
- Success feedback shows: **"Imported X accounts. Y skipped (already exist)."**
- The COA page refreshes to show the new accounts.

---

## 4. Hierarchical Data Taxonomy & Structure

### 4.1 Taxonomy Definition (Static JSON Seed)

Store the master taxonomy in a new file: **`app/accounting/coa_taxonomy.py`**.

```python
COA_TAXONOMY = [
    {
        "major_category": "Revenue",
        "subcategories": [
            {
                "name": "Operating Revenue",
                "account_types": [
                    {
                        "name": "Sales Revenue",
                        "accounts": [
                            {"code": "1100", "name": "Product Sales", "type": "income"},
                            {"code": "1110", "name": "Service Revenue", "type": "income"},
                            {"code": "1120", "name": "Subscription Revenue", "type": "income"},
                        ]
                    },
                    {
                        "name": "Other Revenue",
                        "accounts": [
                            {"code": "1190", "name": "Sales Returns & Allowances", "type": "income"},
                            {"code": "1195", "name": "Sales Discounts", "type": "income"},
                        ]
                    }
                ]
            },
            {
                "name": "Non-Operating Revenue",
                "account_types": [
                    {
                        "name": "Interest & Investment",
                        "accounts": [
                            {"code": "2100", "name": "Interest Income", "type": "income"},
                            {"code": "2110", "name": "Dividend Income", "type": "income"},
                            {"code": "2120", "name": "Gain on Sale of Assets", "type": "income"},
                            {"code": "2130", "name": "Donations Received", "type": "income"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Expenses",
        "subcategories": [
            {
                "name": "Cost of Sales",
                "account_types": [
                    {
                        "name": "Direct Costs",
                        "accounts": [
                            {"code": "3100", "name": "Cost of Goods Sold", "type": "expense"},
                            {"code": "3110", "name": "Cost of Services", "type": "expense"},
                            {"code": "3120", "name": "Freight & Shipping — COGS", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Operating Expenses",
                "account_types": [
                    {
                        "name": "Selling & Distribution",
                        "accounts": [
                            {"code": "4100", "name": "Salaries & Wages — Sales", "type": "expense"},
                            {"code": "4110", "name": "Sales Commissions", "type": "expense"},
                            {"code": "4120", "name": "Marketing & Advertising", "type": "expense"},
                            {"code": "4130", "name": "Delivery & Logistics", "type": "expense"},
                        ]
                    },
                    {
                        "name": "General & Administrative",
                        "accounts": [
                            {"code": "4200", "name": "Salaries & Wages — Admin", "type": "expense"},
                            {"code": "4210", "name": "Office Rent", "type": "expense"},
                            {"code": "4220", "name": "Utilities", "type": "expense"},
                            {"code": "4230", "name": "Professional Fees", "type": "expense"},
                            {"code": "4240", "name": "Insurance", "type": "expense"},
                            {"code": "4250", "name": "Office Supplies", "type": "expense"},
                            {"code": "4260", "name": "Depreciation Expense", "type": "expense"},
                            {"code": "4270", "name": "Amortization Expense", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Finance Costs",
                "account_types": [
                    {
                        "name": "Interest & Banking",
                        "accounts": [
                            {"code": "5100", "name": "Interest Expense", "type": "expense"},
                            {"code": "5110", "name": "Bank Charges & Fees", "type": "expense"},
                            {"code": "5120", "name": "Foreign Exchange Loss", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Taxes",
                "account_types": [
                    {
                        "name": "Income Taxes",
                        "accounts": [
                            {"code": "5200", "name": "Income Tax Expense", "type": "expense"},
                            {"code": "5210", "name": "Withholding Tax", "type": "expense"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Assets",
        "subcategories": [
            {
                "name": "Non-Current Assets",
                "account_types": [
                    {
                        "name": "Property, Plant & Equipment",
                        "accounts": [
                            {"code": "6100", "name": "Land & Land Improvements", "type": "asset"},
                            {"code": "6110", "name": "Buildings", "type": "asset"},
                            {"code": "6120", "name": "Machinery & Equipment", "type": "asset"},
                            {"code": "6130", "name": "Vehicles", "type": "asset"},
                            {"code": "6140", "name": "Furniture & Fixtures", "type": "asset"},
                            {"code": "6190", "name": "Accumulated Depreciation — PPE", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Intangible Assets",
                        "accounts": [
                            {"code": "6200", "name": "Patents & Licenses", "type": "asset"},
                            {"code": "6210", "name": "Goodwill", "type": "asset"},
                            {"code": "6290", "name": "Accumulated Amortization — Intangibles", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Long-Term Investments",
                        "accounts": [
                            {"code": "6300", "name": "Long-Term Investments", "type": "asset"},
                            {"code": "6310", "name": "Investments in Subsidiaries", "type": "asset"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Assets",
                "account_types": [
                    {
                        "name": "Cash & Bank",
                        "accounts": [
                            {"code": "7100", "name": "Cash on Hand", "type": "asset"},
                            {"code": "7110", "name": "Bank — Checking", "type": "asset"},
                            {"code": "7120", "name": "Bank — Savings", "type": "asset"},
                            {"code": "7130", "name": "Petty Cash", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Short-Term Investments",
                        "accounts": [
                            {"code": "7200", "name": "Short-Term Investments", "type": "asset"},
                            {"code": "7210", "name": "Marketable Securities", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Accounts Receivable",
                        "accounts": [
                            {"code": "7300", "name": "Accounts Receivable", "type": "asset"},
                            {"code": "7310", "name": "Allowance for Doubtful Debts", "type": "asset"},
                            {"code": "7320", "name": "Notes Receivable", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Inventory",
                        "accounts": [
                            {"code": "7400", "name": "Raw Materials Inventory", "type": "asset"},
                            {"code": "7410", "name": "Work-in-Progress Inventory", "type": "asset"},
                            {"code": "7420", "name": "Finished Goods Inventory", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Prepayments",
                        "accounts": [
                            {"code": "7500", "name": "Prepaid Expenses", "type": "asset"},
                            {"code": "7510", "name": "Prepaid Insurance", "type": "asset"},
                            {"code": "7520", "name": "Prepaid Rent", "type": "asset"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Liabilities",
        "subcategories": [
            {
                "name": "Non-Current Liabilities",
                "account_types": [
                    {
                        "name": "Long-Term Debt",
                        "accounts": [
                            {"code": "8000", "name": "Long-Term Bank Loans", "type": "liability"},
                            {"code": "8010", "name": "Mortgage Payable", "type": "liability"},
                            {"code": "8020", "name": "Less: Current Portion of Long-Term Debt", "type": "liability"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Liabilities",
                "account_types": [
                    {
                        "name": "Trade Payables",
                        "accounts": [
                            {"code": "8200", "name": "Accounts Payable", "type": "liability"},
                            {"code": "8210", "name": "Accrued Expenses", "type": "liability"},
                            {"code": "8220", "name": "Taxes Payable", "type": "liability"},
                            {"code": "8230", "name": "VAT Payable", "type": "liability"},
                        ]
                    },
                    {
                        "name": "Short-Term Debt",
                        "accounts": [
                            {"code": "8300", "name": "Short-Term Loans", "type": "liability"},
                            {"code": "8310", "name": "Current Portion of Long-Term Debt", "type": "liability"},
                        ]
                    },
                    {
                        "name": "Other Payables",
                        "accounts": [
                            {"code": "8400", "name": "Salaries & Wages Payable", "type": "liability"},
                            {"code": "8410", "name": "Dividends Payable", "type": "liability"},
                            {"code": "8420", "name": "Unearned Revenue", "type": "liability"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Equity",
        "subcategories": [
            {
                "name": "Owner's Equity",
                "account_types": [
                    {
                        "name": "Capital",
                        "accounts": [
                            {"code": "9100", "name": "Owner's Capital / Share Capital", "type": "equity"},
                            {"code": "9110", "name": "Additional Paid-In Capital", "type": "equity"},
                            {"code": "9120", "name": "Treasury Shares", "type": "equity"},
                        ]
                    },
                    {
                        "name": "Reserves & Retained Earnings",
                        "accounts": [
                            {"code": "9200", "name": "Retained Earnings", "type": "equity"},
                            {"code": "9210", "name": "Appropriated Reserves", "type": "equity"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Period Earnings",
                "account_types": [
                    {
                        "name": "P&L Summary",
                        "accounts": [
                            {"code": "9300", "name": "Current Year Earnings", "type": "equity"},
                            {"code": "9310", "name": "Dividends Declared", "type": "equity"},
                        ]
                    }
                ]
            }
        ]
    }
]
```

### 4.2 Subtotaling Logic — The "XX99" Rule

When the seeder inserts accounts, it must automatically generate **subtotal placeholder accounts** for every group of related line items.

**Rule**: If a range of accounts exists where the first two digits are identical and the last two digits range from `00` to `98` (or any non-`99` range), a subtotal account ending in `99` must be created as the **parent** of that range.

**Example — Current Assets (7100–7520)**:

- Line items: `7100`, `7110`, `7120`, `7130`, `7200`, `7210`, `7300`, `7310`, `7320`, `7400`, `7410`, `7420`, `7500`, `7510`, `7520`
- Subtotals generated:
  - `7199` — Total Cash & Bank (parent of 7100–7130)
  - `7299` — Total Short-Term Investments (parent of 7200–7210)
  - `7399` — Total Accounts Receivable (parent of 7300–7320)
  - `7499` — Total Inventory (parent of 7400–7420)
  - `7599` — Total Prepayments (parent of 7500–7520)
- `7999` — Total Assets (parent of 6999 + 7899) — grand total for Assets

**Revised ranges with corrected numbering**:

- Revenue: 1000–2999
- Expenses: 3000–5999
- Assets: 6000–7999
- Liabilities: 8000–8999
- Equity: 9000–9999

**Revised top-level subtotals** (always generated):

- `1199` — Total Sales Revenue (parent of all 1100–1120)
- `1299` — Total Other Revenue (parent of 1190–1195)
- `1999` — Total Operating Revenue (parent of 1100–1299) — derived as `2999 − 100`
- `2199` — Total Interest & Investment (parent of 2100–2130) — derived as `1999 − 100`
- `2999` — Total Revenue (parent of all 1000–2999) — grand total for Revenue
- `3099` — Total Direct Costs (parent of 3100–3120)
- `3999` — Total Cost of Sales (parent of 3099 + its children) — grand total for Cost of Sales
- `4099` — Total Selling & Distribution (parent of 4100–4130)
- `4199` — Total General & Administrative (parent of 4200–4270)
- `4999` — Total Operating Expenses (parent of 4099 + 4199)
- `5099` — Total Finance Costs (parent of 5100–5120)
- `5199` — Total Income Taxes (parent of 5200–5210)
- `5999` — Total Expenses (parent of all 3000–5999) — grand total for Expenses
- `5899` — Total Other Expenses (parent of 5099 + 5199) — derived as `5999 − 100`
- `6099` — Total PPE (parent of 6100–6190)
- `6199` — Total Intangible Assets (parent of 6200–6290)
- `6299` — Total Long-Term Investments (parent of 6300–6310)
- `6999` — Total Non-Current Assets (parent of 6099 + 6199 + 6299)
- `7899` — Total Current Assets (parent of 7199 + 7299 + 7399 + 7499 + 7599) — derived as `7999 − 100`
- `7999` — Total Assets (parent of 6999 + 7899) — grand total for Assets
- `8099` — Total Long-Term Debt (parent of 8000–8020)
- `8199` — Total Trade Payables (parent of 8200–8230)
- `8299` — Total Short-Term Debt (parent of 8300–8310)
- `8399` — Total Other Payables (parent of 8400–8420)
- `8799` — Total Current Liabilities (parent of 8199 + 8299 + 8399) — derived as `8999 − 100`
- `8999` — Total Liabilities (parent of 8099 + 8799) — grand total for Liabilities
- `9099` — Total Capital (parent of 9100–9120)
- `9199` — Total Reserves & Retained Earnings (parent of 9200–9210)
- `9299` — Total Current Period Earnings (parent of 9300–9310)
- `9999` — Total Equity (parent of 9099 + 9199 + 9299) — grand total for Equity

**Note on subtotal code uniqueness**: Every account code is unique. The grand total for each major category uses the category's upper-bound `XX99` code; direct subtotals under it use `XX99 − 100` (e.g., `7899` for Total Current Assets under grand total `7999`). This avoids code reuse and keeps the hierarchy unambiguous.

**Implementation**:

1. After parsing the taxonomy, group accounts by their first two digits (`xx00`) within each account type.
2. For each group where the last two digits do NOT include `99` and the group has ≥2 items, create a subtotal account with code `xx99`.
3. The subtotal account `name` = `"Total [Account Type Name]"` (e.g., "Total Cash & Bank").
4. The subtotal `type` = same as the group's account type.
5. The subtotal's `parent_id` points to the next higher-level subtotal or is `None` if it's the top-level summary.
6. Leaf accounts' `parent_id` point to their immediate subtotal.
7. **Do NOT** create subtotals for groups with 0 or 1 item (no need).
8. For subcategories with only one account type, skip the intermediate subtotal and attach leaf accounts directly to the category-level subtotal.
9. **Exception**: For the direct children of a major-category grand total (e.g., Total Non-Current Assets and Total Current Assets under Total Assets), the subtotal code is `XX99 − 100` instead of `XX99`, so it does not collide with the grand total.

---

## 5. Accounting Logic & Coding Schema

### 5.1 Code Ranges

| Major Category | Code Range | Type |
| ---------------- | ----------- | ------ |
| Revenue | 1000–2999 | `income` |
| Expenses | 3000–5999 | `expense` |
| Assets — Non-Current | 6000–6999 | `asset` |
| Assets — Current | 7000–7999 | `asset` |
| Liabilities — Non-Current | 8000–8099 | `liability` |
| Liabilities — Current | 8100–8999 | `liability` |
| Equity | 9000–9999 | `equity` |

### 5.2 Parent-Child Tree Assembly

After subtotals are generated, assemble the tree:

```format
2999 Total Revenue (income)
├── 1999 Total Operating Revenue (income)
│   ├── 1199 Total Sales Revenue (income)
│   │   ├── 1100 Product Sales
│   │   ├── 1110 Service Revenue
│   │   └── 1120 Subscription Revenue
│   └── 1299 Total Other Revenue (income)
│       ├── 1190 Sales Returns & Allowances
│       └── 1195 Sales Discounts
└── 2199 Total Interest & Investment (income)
    ├── 2100 Interest Income
    ├── 2110 Dividend Income
    ├── 2120 Gain on Sale of Assets
    └── 2130 Donations Received

5999 Total Expenses (expense)
├── 3999 Total Cost of Sales (expense)
│   └── 3099 Total Direct Costs (expense)
│       ├── 3100 Cost of Goods Sold
│       ├── 3110 Cost of Services
│       └── 3120 Freight & Shipping — COGS
├── 4999 Total Operating Expenses (expense)
│   ├── 4099 Total Selling & Distribution (expense)
│   │   ├── 4100 Salaries & Wages — Sales
│   │   ├── 4110 Sales Commissions
│   │   ├── 4120 Marketing & Advertising
│   │   └── 4130 Delivery & Logistics
│   └── 4199 Total General & Administrative (expense)
│       ├── 4200 Salaries & Wages — Admin
│       ├── 4210 Office Rent
│       ├── 4220 Utilities
│       ├── 4230 Professional Fees
│       ├── 4240 Insurance
│       ├── 4250 Office Supplies
│       ├── 4260 Depreciation Expense
│       └── 4270 Amortization Expense
└── 5899 Total Other Expenses (expense)
    ├── 5099 Total Finance Costs (expense)
    │   ├── 5100 Interest Expense
    │   ├── 5110 Bank Charges & Fees
    │   └── 5120 Foreign Exchange Loss
    └── 5199 Total Income Taxes (expense)
        ├── 5200 Income Tax Expense
        └── 5210 Withholding Tax

7999 Total Assets (asset)
├── 6999 Total Non-Current Assets (asset)
│   ├── 6099 Total PPE (asset)
│   │   ├── 6100 Land & Land Improvements
│   │   ├── 6110 Buildings
│   │   ├── 6120 Machinery & Equipment
│   │   ├── 6130 Vehicles
│   │   ├── 6140 Furniture & Fixtures
│   │   └── 6190 Accumulated Depreciation — PPE
│   ├── 6199 Total Intangible Assets (asset)
│   │   ├── 6200 Patents & Licenses
│   │   ├── 6210 Goodwill
│   │   └── 6290 Accumulated Amortization — Intangibles
│   └── 6299 Total Long-Term Investments (asset)
│       ├── 6300 Long-Term Investments
│       └── 6310 Investments in Subsidiaries
└── 7899 Total Current Assets (asset)
    ├── 7199 Total Cash & Bank (asset)
    │   ├── 7100 Cash on Hand
    │   ├── 7110 Bank — Checking
    │   ├── 7120 Bank — Savings
    │   └── 7130 Petty Cash
    ├── 7299 Total Short-Term Investments (asset)
    │   ├── 7200 Short-Term Investments
    │   └── 7210 Marketable Securities
    ├── 7399 Total Accounts Receivable (asset)
    │   ├── 7300 Accounts Receivable
    │   ├── 7310 Allowance for Doubtful Debts
    │   └── 7320 Notes Receivable
    ├── 7499 Total Inventory (asset)
    │   ├── 7400 Raw Materials Inventory
    │   ├── 7410 Work-in-Progress Inventory
    │   └── 7420 Finished Goods Inventory
    └── 7599 Total Prepayments (asset)
        ├── 7500 Prepaid Expenses
        ├── 7510 Prepaid Insurance
        └── 7520 Prepaid Rent

8999 Total Liabilities (liability)
├── 8099 Total Non-Current Liabilities (liability)
│   ├── 8000 Long-Term Bank Loans
│   ├── 8010 Mortgage Payable
│   └── 8020 Less: Current Portion of Long-Term Debt
└── 8799 Total Current Liabilities (liability)
    ├── 8199 Total Trade Payables (liability)
    │   ├── 8200 Accounts Payable
    │   ├── 8210 Accrued Expenses
    │   ├── 8220 Taxes Payable
    │   └── 8230 VAT Payable
    ├── 8299 Total Short-Term Debt (liability)
    │   ├── 8300 Short-Term Loans
    │   └── 8310 Current Portion of Long-Term Debt
    └── 8399 Total Other Payables (liability)
        ├── 8400 Salaries & Wages Payable
        ├── 8410 Dividends Payable
        └── 8420 Unearned Revenue

9999 Total Equity (equity)
├── 9099 Total Owner's Equity (equity)
│   ├── 9199 Total Capital (equity)
│   │   ├── 9100 Owner's Capital / Share Capital
│   │   ├── 9110 Additional Paid-In Capital
│   │   └── 9120 Treasury Shares
│   └── 9299 Total Reserves & Retained Earnings (equity)
│       ├── 9200 Retained Earnings
│       └── 9210 Appropriated Reserves
└── 9399 Total Current Period Earnings (equity)
    ├── 9300 Current Year Earnings
    └── 9310 Dividends Declared
```

**Implementation detail**:

- Subtotal accounts are inserted first (higher-level), then leaf accounts.
- Each leaf account's `parent_id` = the ID of its immediate subtotal.
- Each subtotal's `parent_id` = the ID of its parent subtotal (or `None` for top-level).
- The **order of insertion** matters for `parent_id` references. Use a two-pass approach:
  1. Pass 1: Insert all subtotal accounts, collect their `(code → id)` mappings.
  2. Pass 2: Insert all leaf accounts, using the mapping to set `parent_id`.
- Every account code is unique. The grand total for each major category uses the category's upper-bound `XX99` code; direct subtotals under it use `XX99 − 100`.

### 5.3 Type Field for Subtotals

The `type` field on subtotal accounts must match the underlying accounts' type so financial statements render correctly. The existing `ACCOUNT_TYPES` in `routes.py` uses `asset`, `liability`, `equity`, `income`, `expense`.

---

## 6. Content & Data Integrity Standards

### 6.1 Terminology

Use IFRS/GAAP universal nomenclature:

- "Accounts Receivable" not "Money owed by customers"
- "Cost of Goods Sold" not "Direct costs"
- "Accumulated Depreciation" not "Depreciation to date"
- "Unearned Revenue" not "Advance payments"

### 6.2 Data Fields (per leaf account)

| Field | Source | Notes |
| ------- | -------- | ------- |
| `code` | Hardcoded in taxonomy | 4-digit string, unique within taxonomy |
| `name` | Hardcoded in taxonomy | Descriptive, title case |
| `type` | Hardcoded in taxonomy | One of: `asset`, `liability`, `equity`, `income`, `expense` |
| `parent_id` | Computed via subtotaling logic | FK to another `chart_of_accounts.id` |

### 6.3 Deduplication Logic

When the user submits selected accounts:

1. **Query existing**: `SELECT code FROM chart_of_accounts WHERE business_id = :biz_id`
2. **Filter selected**: Remove any selected code that already exists in the business.
3. **Return summary**: `"Imported X accounts. Y skipped (already exist)."`
4. **No partial failures**: If a selected group has a subtotal that already exists but its children don't, the subtotal is skipped and children are still inserted with the subtotal as parent (re-query the subtotal's current ID).

---

## 7. Integration Requirements

### 7.1 New Files

| File | Purpose |
| ------ | --------- |
| `app/accounting/coa_taxonomy.py` | Master taxonomy JSON + `build_coa_tree(business_id)` function that returns structured tree with subtotals |
| `templates/coa_seeder_modal.html` | Jinja2 partial for the "Need Headstart" modal (rendered server-side or fetched via HTMX) |
| `static/js/coa-seeder.js` | Frontend logic for tree expansion, checkbox selection, preview, and POST submission |
| `tests/test_coa_seeder.py` | Unit tests for taxonomy generation, subtotaling, deduplication, and bulk insertion |

### 7.2 Modified Files

| File | Changes |
| ------ | --------- |
| `app/accounting/routes.py` | Add `coa_seeder()` GET (render modal) and `coa_seeder_import()` POST (bulk insert) |
| `templates/chart_of_accounts.html` | Add "Need Headstart" button + include modal partial |
| `app/accounting/__init__.py` | Ensure new routes are imported (already done via `from . import routes`) |

### 7.3 Backend Endpoint Design

**Route**: `POST /accounting/chart-of-accounts/seed`
**Auth**: `@login_required`, `@role_required('admin', 'accountant')`
**Request Body** (JSON):

```json
{
  "selected_codes": ["1100", "1110", "3100", "3110", "7100", "7110", "7300", "8200"]
}
```

**Response** (JSON):

```json
{
  "imported": 6,
  "skipped": 2,
  "skipped_codes": ["1100", "7100"],
  "message": "Imported 6 accounts. 2 skipped (already exist)."
}
```

**Backend Logic** (`coa_seeder_import()`):

1. Parse `selected_codes` from JSON body.
2. Load `COA_TAXONOMY` from `coa_taxonomy.py`.
3. Flatten taxonomy into a list of `{code, name, type}` for the requested codes.
4. For each selected code, determine if it's a leaf or a category/subcategory/type header.
   - **Only leaf accounts** (those with `code` and `name` directly) are importable.
   - Headers have no `code` field, so they are skipped automatically.
5. Build the subtotal tree for the selected leaf set using the same `XX99` logic.
6. Query existing codes for the business.
7. Insert subtotals first (pass 1), then leaves (pass 2), skipping any that already exist.
8. Commit and return summary.

### 7.4 Frontend Design

**UI Pattern**: Bootstrap 5 collapse/accordion for the tree.

**Tree rendering**:

```html
<div class="coa-tree">
  <div class="coa-major-category">
    <button class="btn btn-sm btn-outline-primary" data-bs-toggle="collapse" data-bs-target="#cat-revenue">
      ▼ Revenue
    </button>
    <div class="collapse show" id="cat-revenue">
      <div class="coa-subcategory">
        <span>Operating Revenue</span>
        <div class="coa-account-types">
          <div class="coa-type">
            <span>Sales Revenue</span>
            <label><input type="checkbox" value="1100"> Product Sales (1100)</label>
            <label><input type="checkbox" value="1110"> Service Revenue (1110)</label>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

**Selection preview panel** (sticky sidebar within modal):

- Shows selected accounts grouped by Major Category.
- Each item has a remove (×) button.
- Total count displayed in modal footer.

**AJAX submission**:

```javascript
async function importSelected() {
  const selected = [...document.querySelectorAll('.coa-tree input:checked')].map(cb => cb.value);
  const response = await fetch('/accounting/chart-of-accounts/seed', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ selected_codes: selected }),
  });
  const data = await response.json();
  showToast(data.message, data.imported > 0 ? 'success' : 'info');
  if (data.imported > 0) location.reload();
}
```

### 7.5 Database Considerations

- **No schema changes needed**: The existing `chart_of_accounts` table already supports `parent_id`, `code`, `name`, `type`, and the `business_id` multi-tenant constraint.
- **Unique constraint**: `uq_business_account_code` already prevents duplicate codes per business.
- **Subtotal accounts**: These are regular `ChartOfAccounts` rows. No special handling needed in the DB.

### 7.6 Testing Plan

**Unit tests** (`tests/test_coa_seeder.py`):

| Test | Description |
| ------ | ------------- |
| `test_taxonomy_has_all_leaf_accounts` | Verify every leaf in `COA_TAXONOMY` has `code`, `name`, `type` |
| `test_taxonomy_codes_in_range` | Verify all codes fall within their major category's range |
| `test_subtotals_generated` | Given a set of leaf codes, verify subtotal `XX99` accounts are created |
| `test_subtotal_no_single_item_groups` | Verify no subtotal is created for a group with only 1 leaf |
| `test_tree_assembly` | Verify `parent_id` relationships are correct after two-pass insertion |
| `test_deduplication` | Verify already-existing codes are skipped and counted |
| `test_import_endpoint` | POST to `/accounting/chart-of-accounts/seed` and verify response, DB rows |
| `test_unauthorized_access` | Verify non-admin/accountant gets 403 |
| `test_empty_selection` | Verify empty selection returns 0 imported, 0 skipped |

**Integration test**:

- Use Flask test client to POST a selection of 5–10 accounts.
- Query DB to verify:
  - Correct number of rows inserted.
  - `parent_id` relationships are set.
  - Codes are unique per business.
  - Types match expected values.

---

## 8. Rollout & Migration

### 8.1 No Data Migration Required

- The feature is additive. Existing businesses with existing COAs are unaffected.
- The taxonomy is hardcoded in Python, not a DB migration.

### 8.2 Feature Flag (Optional but Recommended)

Add a simple config flag in `config.py`:

```python
COA_SEEDER_ENABLED = os.environ.get("COA_SEEDER_ENABLED", "true").lower() == "true"
```

Hide the button when disabled. Allows disabling without deploy if issues arise.

### 8.3 Rollout Steps

1. **Deploy code** (new file + route + template changes).
2. **Verify** on staging: click "Need Headstart", select accounts, import, verify COA table.
3. **Monitor** for duplicate code errors (should be zero if deduplication works).
4. **Communicate** to users: "Use the Need Headstart button to quickly set up a standard chart of accounts."

---

## 9. Open Questions (Resolved)

| Question | Decision |
| ---------- | ---------- |
| Should subtotals be editable by users? | **No** — subtotals are system-generated. Users can edit names later if needed, same as any other account. |
| Should users be able to select entire categories at once? | **Yes** — but only for convenience. Selecting a major category selects all its leaf accounts and generates the full tree. |
| What if a user has partially seeded accounts and selects a category that includes existing accounts? | **Deduplication applies** — existing accounts are skipped; new ones are inserted with existing subtotals as parents where applicable. |
| Should the taxonomy be configurable per business? | **No** — keep it static and universal. Customization happens after import via the existing Edit functionality. |

---

## 10. Implementation Order

1. **Create `app/accounting/coa_taxonomy.py`** with `COA_TAXONOMY` and `build_coa_tree()`.
2. **Add routes** in `app/accounting/routes.py`: `coa_seeder()` (GET modal) and `coa_seeder_import()` (POST JSON).
3. **Create `templates/coa_seeder_modal.html`** partial.
4. **Update `templates/chart_of_accounts.html`**: Add "Need Headstart" button + modal trigger + include partial.
5. **Create `static/js/coa-seeder.js`**: Tree UI logic, preview, AJAX import.
6. **Create `tests/test_coa_seeder.py`**: Unit + integration tests.
7. **Run existing tests** to confirm no regressions.
8. **Manual QA** on dev environment.

---

## 11. Risk Assessment

| Risk | Mitigation |
| ------ | ----------- |
| Duplicate code insertion if two users click Import simultaneously | DB unique constraint (`uq_business_account_code`) + backend dedup check handles this. |
| Subtotal parent_id misalignment if insertion order is wrong | Two-pass insertion (subtotals first, leaves second) with `(code → id)` mapping. |
| Taxonomy too large/slow for JS rendering | Tree is ~100 accounts. Bootstrap collapse handles this. Lazy-render if needed, but unlikely to be an issue. |
| Users accidentally import accounts they didn't want | Preview panel + deselect before import. No auto-import. |
| CSRF token handling in JSON POST | Use existing `X-CSRFToken` header pattern already in `main.js`. |

---

## 12. Files Changed Summary

| Action | Path |
| -------- | ------ |
| **Create** | `app/accounting/coa_taxonomy.py` |
| **Modify** | `app/accounting/routes.py` |
| **Modify** | `templates/chart_of_accounts.html` |
| **Create** | `templates/coa_seeder_modal.html` |
| **Create** | `static/js/coa-seeder.js` |
| **Create** | `tests/test_coa_seeder.py` |
| **Modify (optional)** | `config.py` (feature flag) |
