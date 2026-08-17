# TrackWise — Budget & Expense Tracking Integration Review

**Project:** TrackWise (Flask-based SaaS ERP-lite)  
**Review Date:** 2026-08-17  
**Scope:** Budget/expense tracking, financial workflow integration, data sync, categorization, reporting, UX

---

## 1. Executive Summary

TrackWise implements a **Payments Hub** that replaces legacy expense tracking with a unified, double-entry-integrated payment recording system. While the core accounting engine is robust (balanced journal entries, immutable audit logs, approval workflows), the platform lacks **budget planning**, **external data synchronization**, and several **professional accounting workflows** expected in modern financial management software.

**Overall Assessment:**

- **Data Sync:** Manual-only (CSV paste for bank statements); no real-time API sync.  
- **Categorization:** Structurally sound (FinancialCategory → LineItem → Chart of Accounts), but limited flexibility and some hardcoded fallback mappings.  
- **Real-Time Reporting:** Server-rendered reports on demand; no live dashboards or push notifications.  
- **UX:** Functional but with significant friction points (no mobile optimization, missing breadcrumbs, limited inline validation, no print stylesheets).  

---

## 2. Data Synchronization Seamlessness

### 2.1. Current State

| Integration Point | Status | Details |
| --- | --- | --- |
| **Bank Statement Sync** | ❌ None | Only manual CSV paste via `/accounting/bank-reconciliation/import`. No OFX, QIF, or direct bank API (Plaid/Flutterwave). |
| **Receipt/Invoice Scanning** | ❌ None | No OCR or document ingestion. Users manually key all transaction data. |
| **External Payment Gateways** | ⚠️ Model-Only | Stripe subscription `stripe_subscription_id` exists, but no webhook handler or payment-intent flow is implemented. |
| **Mobile Money / Card Payments** | ❌ None | Payment modes are recorded as metadata strings (`cash`, `bank_transfer`, `mobile_money`, `cheque`, `card`) but no automated settlement sync. |
| **Inventory ↔ Accounting Sync** | ✅ Strong | FIFO service auto-posts COGS and inventory value changes to the Chart of Accounts on every sale/purchase. |
| **Sales/Purchase → Accounting** | ✅ Strong | Sales and purchases create balanced journal entries automatically. |

### 2.2. Friction Points

1. **No automated bank feeds** — Accountants must manually paste CSV data, increasing reconciliation time and error risk.
2. **No duplicate detection** — Imported bank statement lines are not matched against existing payments; duplicate CSV imports could create phantom unreconciled items.
3. **No real-time sync indicators** — Users receive no feedback on sync status, pending imports, or reconciliation progress beyond flash messages.

---

## 3. Transaction Categorization Accuracy

### 3.1. Current Architecture

TrackWise uses a **3-tier classification system**:

1. **FinancialCategory** (high-level: OPEX, COGS, ADMIN, SELL, FIN, TAX, OTH_INC)  
2. **LineItem** (granular sub-category linked to a FinancialCategory)  
3. **Chart of Accounts account_code** (maps LineItem to the double-entry account)

**Example mapping (seed data):**

- FinancialCategory: "Operating Expenses"
- LineItem: "Salaries" → `account_code: "5300"` (Salaries Expense)
- LineItem: "Rent" → `account_code: "5100"` (Rent Expense)

### 3.2. Strengths

- **Cascading dropdowns** in the Payments Hub UI ensure valid category → line-item pairing.
- **Double-entry enforcement** means categorization errors are caught at the accounting layer (unknown accounts raise `AccountingException`).
- **Default seeded categories** cover common SME expenses (Rent, Utilities, Salaries, Marketing, Logistics, etc.).

### 3.3. Weaknesses & Risks

1. **Hardcoded fallback mapping in legacy path** — `fifo_service.py` line 36–45 defines `_EXPENSE_ACCOUNT_MAP` as a Python dict. If a category string deviates from these keys (e.g., "Stationery" instead of "Supplies"), it silently falls back to `5900` (Other Expenses), masking misclassification.
2. **No categorization validation at entry time** — The Payments Hub accepts any `category_id`/`line_item_id` combination that exists in the database; there is no business-rule validation (e.g., preventing a COGS line item from being used for a staff salary payment).
3. **Legacy Expense model still active** — `Expense` table uses a plain string `category` field (not FK-joined), creating a parallel, uncontrolled taxonomy that undermines reporting consistency.
4. **No auto-categorization or rules engine** — Users must manually select categories for every payment. No merchant-based rules, amount thresholds, or keyword matching.

---

## 4. Real-Time Reporting Availability

### 4.1. Available Reports

| Report | Route | Data Freshness |
| --- | --- | --- |
| Income Statement | `/reports/income-statement` | On-demand (page reload) |
| Balance Sheet | `/reports/balance-sheet` | On-demand |
| Cash Flow | `/reports/cash-flow` | On-demand |
| Trial Balance | `/reports/trial-balance` | On-demand |
| General Ledger | `/reports/general-ledger` | On-demand, paginated |
| AR Aging | `/reports/ar-aging` | On-demand |
| AP Aging | `/reports/ap-aging` | On-demand |
| Audit Trail | `/reports/audit-log` | On-demand |

### 4.2. Strengths

- All reports are **derived from JournalEntry/JournalLine** — no manual report edits, ensuring data integrity.
- **Date-range and as-of filters** are available for most statements.
- **Chart.js visualizations** on the dashboard (6-month sales vs. expenses trend, balance sheet doughnut).

### 4.3. Limitations

1. **No real-time or near-real-time updates** — Reports are server-rendered. Users must manually refresh to see new transactions.
2. **No scheduled report delivery** — No email, PDF auto-generation, or subscription to report snapshots.
3. **Dashboard KPIs are all-time or monthly** — No custom period quick-selects, no drill-down from KPI to detail transactions.
4. **No budget-vs-actual reporting** — No budget tables exist, so variance analysis is impossible.
5. **General Ledger lacks advanced filters** — No filtering by user, reference type, or description keyword in the UI.

---

## 5. Overall User Experience for Financial Workflows

### 5.1. Payment Recording Flow

1. Navigate to `/payments`
2. Select payee type (supplier/staff) → conditional dropdown appears
3. Select FinancialCategory → LineItem dropdown filters dynamically via JS
4. Enter amount, payment mode, reference
5. If approval enabled → creates `ApprovalRequest`
6. If no approval → `_post_payment_accounting()` posts balanced journal entry instantly
7. Payment appears in history table with status badge

### 5.2. Strengths

- **Role-based access control** (admin, accountant, cashier, storekeeper, viewer) protects financial data.
- **Approval workflows** gate sensitive transactions (payments, supplier edits).
- **CSRF protection** on all forms.
- **Pagination** prevents large dataset overload.
- **Empty states** with SVG illustrations guide new users.

### 5.3. UX Friction Points

1. **No mobile bottom navigation** — The sidebar-only layout is impractical on phones.
2. **No print stylesheets** — Financial reports cannot be printed cleanly without sidebar/navigation clutter.
3. **No breadcrumb navigation** — Users lose context when drilling from Dashboard → Reports → General Ledger.
4. **Flash messages only for validation** — No inline field-level error messages; users must scroll to top to see form errors.
5. **No confirmation dialogs** — Destructive actions (voiding, deleting) lack confirmation modals.
6. **Dark-only theme** — No light/dark toggle; long bookkeeping sessions cause eye strain.
7. **Pagination is minimal** — No page-size selector on reports, limiting data-dense workflows.
8. **Keyboard accessibility gaps** — Sidebar toggle lacks keyboard handlers; no visible focus styles.

---

## 6. Friction Points & Missing Functionalities

### 6.1. Critical Gaps (Block Professional Use)

| # | Gap | Impact |
| --- | --- | --- |
| 1 | **No budget planning module** | Users cannot set budgets, track variances, or forecast cash flow. |
| 2 | **No external bank sync** | Manual CSV entry is error-prone and time-consuming for high-volume businesses. |
| 3 | **No AR payment application** | Receipts post to AR but there is no UI to apply partial payments, overpayments, or track unallocated cash. |
| 4 | **No manual journal entry UI** | Accountants cannot create adjusting entries, accruals, or corrections via the interface. |
| 5 | **No accrual accounting support** | All transactions are cash-basis; no accounts receivable/re payable aging based on invoices vs. payments. |
| 6 | **No tax-per-line-item logic** | `tax_amount` is hardcoded to `0.0` on invoices/bills; VAT/GST compliance is impossible. |

### 6.2. High-Value Missing Features

| # | Feature | Impact |
| --- | --- | --- |
| 7 | **Multi-currency support** | `Business.currency` exists but no exchange rates, FX gain/loss posting, or multi-currency reports. |
| 8 | **Fixed assets & depreciation** | No asset register, no depreciation schedules, no accumulated depreciation. |
| 9 | **Credit notes / refunds** | Returns do not reverse AR/AP or inventory; financial statements become overstated. |
| 10 | **Recurring transactions** | No templates for repeating expenses, invoices, or journal entries. |
| 11 | **Purchase order lifecycle** | No PO → Goods Receipt → Bill → Payment workflow. |
| 12 | **Document attachments** | No file uploads for invoices, receipts, or supporting docs. |
| 13 | **Public API exposure** | `GET /api/products` is unauthenticated, leaking inventory data. |

### 6.3. UX / Accessibility Gaps

| # | Gap | Impact |
| --- | --- | --- |
| 14 | **No mobile-optimized navigation** | Field staff and owners cannot efficiently record expenses on phones. |
| 15 | **No print-ready reports** | Accountants cannot produce clean financial statements for auditors or boards. |
| 16 | **No confirmation dialogs** | Risk of accidental data loss on destructive actions. |
| 17 | **No theme toggle** | Long sessions in dark-only UI cause fatigue. |
| 18 | **No skip link / ARIA improvements** | Fails WCAG 2.1 AA; excludes keyboard and screen-reader users. |

---

## 7. Action Plan

### 7.0. P0 — Immediate (Next Sprint)

| # | Action | Owner | Effort |
| --- | --- | --- | --- |
| 1 | **Add budget tables & variance engine** — Create `budgets` and `budget_line_items` models; add Budget vs. Actual report. | Backend | 3–5 days |
| 2 | **Fix public API exposure** — Add `@login_required` to `GET /api/products` and `GET /api/suppliers`. | Backend | 1 day |
| 3 | **Add manual journal entry UI** — Build `/accounting/journal-entries` route with multi-line balanced entry validation and approval. | Full-stack | 4–6 days |
| 4 | **Implement accrual-basis toggle** — Allow businesses to switch between cash and accrual reporting; add deferred revenue/expense logic. | Backend | 3–4 days |
| 5 | **Add AR payment application UI** — Support partial payments, overpayments, and unallocated cash against invoices. | Full-stack | 3–5 days |

### 7.1. P1 — High Priority (1–2 Sprints)

| # | Action | Owner | Effort |
| --- | --- | --- | --- |
| 6 | **Integrate bank feed API** — Add Plaid/Flutterwave or Open Banking connector for automated statement import and transaction matching. | Full-stack | 5–8 days |
| 7 | **Replace hardcoded tax logic** — Add per-line-item tax codes, tax-inclusive/exclusive pricing, and proper Tax Payable posting. | Backend | 3–4 days |
| 8 | **Add multi-currency support** — Exchange-rate table, auto-FX posting, multi-currency reports. | Backend | 4–6 days |
| 9 | **Build fixed assets module** — Asset register, depreciation methods (straight-line, reducing-balance), auto-journals. | Full-stack | 5–7 days |
| 10 | **Add credit notes / refunds flow** — Reverse sales/purchases, update AR/AP, adjust inventory if applicable. | Full-stack | 3–5 days |
| 11 | **Add recurring transaction templates** — Invoices, bills, expenses, and journal entries with auto-creation. | Full-stack | 3–4 days |

### 7.2. P2 — Medium Priority (Ongoing)

| # | Action | Owner | Effort |
| --- | --- | --- |
| 12 | **Implement purchase order lifecycle** — PO → Goods Receipt → Bill → Payment. | Full-stack | 5–7 days |
| 13 | **Add document attachments** — Upload invoices, receipts, bills to `Document` model with S3/local storage. | Full-stack | 3–4 days |
| 14 | **Add mobile bottom navigation & responsive breakpoints** — Improve usability on `< 768px`. | Frontend | 2–3 days |
| 15 | **Add print stylesheets** — Clean financial report printing without navigation. | Frontend | 1–2 days |
| 16 | **Add confirmation dialogs** — `data-confirm` attributes or Bootstrap modals for delete/void actions. | Frontend | 1 day |
| 17 | **Implement theme toggle (light/dark)** — Store in `localStorage` + per-business setting. | Frontend | 2 days |
| 18 | **WCAG 2.1 AA accessibility hardening** — Skip link, `aria-invalid`, table `scope`, focus-visible styles, chart fallbacks. | Frontend | 3–4 days |

---

## 8. Risk & Recommendation Summary

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **Manual data entry errors** due to lack of bank sync | High | Prioritize P0 #3 (manual journal UI) and P1 #6 (bank API) to reduce manual touchpoints. |
| **Misclassification of expenses** due to hardcoded fallback mappings | Medium | Refactor `_EXPENSE_ACCOUNT_MAP` to use `LineItem.account_code` exclusively; add validation rules. |
| **Overstated AR/AP** due to missing credit notes | High | Prioritize P1 #10 (credit notes/refunds) to maintain financial statement integrity. |
| **Tax compliance failure** due to hardcoded `tax_amount=0.0` | High | Prioritize P1 #7 (tax-per-line-item) before onboarding VAT/GST-registered clients. |
| **Data leakage** via public API endpoints | High | Immediate fix P0 #2. |

**Bottom Line:** TrackWise has a solid double-entry foundation, but to compete with Xero/QuickBooks for personal or business financial management, it must close the **budget planning gap**, **eliminate manual data synchronization**, and **harden the categorization and UX layers**. The action plan above prioritizes these in order of accounting correctness, user impact, and implementation feasibility.
