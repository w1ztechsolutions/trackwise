# TrackWise — Comprehensive Review & Professionalization Plan

## Executive Summary

TrackWise is a **Flask-based SaaS ERP-lite** with a **strict double-entry accounting engine** at its core. It already outperforms basic inventory tools, but to reach **Xero / QuickBooks / Sage** parity, it needs structured accounting workflows, missing core modules, and systematic UI/UX hardening. This plan covers **accounting principles compliance**, **missing flows/routes**, **data model gaps**, and **responsive/accessible UI improvements**.

---

## 1. Accounting Principles Audit

### ✅ Compliant

- **Double-entry bookkeeping** — `AccountingService.post_entry()` enforces `debits == credits` (`abs(total_debit - total_credit) > 0.01` raises `AccountingException`).
- **Chart of Accounts** — Hierarchical `ChartOfAccounts` with codes, names, and types (asset/liability/equity/income/expense).
- **Immutable Audit Trail** — `AuditLog` records `old_values`/`new_values` JSON for every journal entry creation.
- **Approval-gated transactions** — Payments and master-data mutations require multi-level approval before accounting posts.
- **Report derivation** — All 8 reports (P&L, BS, CF, TB, GL, AR/AP Aging, Audit Trail) are **read-only views** of `JournalEntry`/`JournalLine` data. No manual report edits exist.

### ⚠️ Gaps vs. GAAP / Professional Practice

| Principle / Feature | Status | Gap |
| --- | --- | --- |
| **Accrual vs. Cash basis** | Cash-basis implied | No toggle; all revenue/expense recognized at transaction date. Need accrual support (e.g., invoiced but unpaid revenue). |
| **Tax per line item** | Flat corporate tax only | `invoice.tax_amount` and `bill.tax_amount` are hardcoded to `0.0`. No VAT/GST, no tax-inclusive pricing, no tax codes. |
| **Multi-currency** | Single currency (`MWK`) | No exchange-rate tables, no FX gain/loss posting, no multi-currency accounts. |
| **Opening balances / Period close** | None | No fiscal year setup, no opening balances for COA, no period-lock mechanism to prevent back-dated edits. |
| **Bank reconciliation** | None | No bank-account register, no statement import, no unreconciled-items report. |
| **Manual journal entries** | API verify only | Accountants cannot create adjusting/recurring entries via UI. |
| **Fixed assets / Depreciation** | None | No asset register, no depreciation schedules, no accumulated-depreciation accounts. |
| **Payroll** | None | `Staff` model exists but no payroll runs, payslips, statutory deductions, or payroll journal entries. |
| **Credit notes / Refunds** | None | No sales-credit or purchase-return flows; AR/AP remain overstated after returns. |
| **Recurring transactions** | None | No templates for repeating sales, purchases, expenses, or journal entries. |
| **Estimates / Quotes** | None | Only issued/draft invoices exist. |
| **Purchase Orders** | None | Bills are created directly from `record_purchase()`; no PO → Bill → Payment lifecycle. |
| **Inventory valuation beyond FIFO** | FIFO only | No weighted-average, LIFO, or standard-cost options. |
| **Cost centers / Departments** | None | `FinancialCategory` + `LineItem` provide basic OPEX classification but no departmental P&L. |
| **Budgeting / Forecasting** | None | No budget tables, no variance analysis. |
| **Document attachments** | None | No file uploads for invoices, receipts, bills, or supporting docs. |
| **Data retention / soft delete** | Hard delete | `JournalEntry` cascade-deletes with lines; no `deleted_at` or archive. |

---

## 2. Flow & Route Review

### Current Route Map (Main App)

| Blueprint | Prefix | Pages |
| --- | --- | --- |
| `auth_bp` | `/` | Login, logout, change-password, user CRUD, role/task assignment |
| `dashboard_bp` | `/dashboard` | Dashboard |
| `inventory_bp` | `/inventory` | Products, warehouses, stock count/transfer/adjustment |
| `purchases_bp` | `/purchases` | Purchases, suppliers, payments hub, payment status |
| `sales_bp` | `/sales` | Sales checkout, customers, invoices, receipts |
| `expenses_bp` | `/expenses` | **DEPRECATED** — redirects to `/purchases/payments` |
| `reports_bp` | `/reports` | 8 financial reports + audit trail |
| `settings_bp` | `/settings` | Tax rate, seed data |
| `production_bp` | `/production` | Production batches |
| `approvals_bp` | `/approvals` | Workflow config, pending approvals, history |
| `superadmin_bp` | `/superadmin` | SaaS platform management |
| `api_bp` | `/api` | Products, suppliers, accounting verify |

### Critical Route / Flow Issues

1. **`/api/products` is public** — `GET /api/products` returns JSON without `@login_required`. This leaks inventory data to unauthenticated users.
2. **No manual journal-entry UI** — Accountants cannot create adjusting entries, recurring entries, or bank-reconciliation entries.
3. **No AR payment recording** — A receipt posts `Dr Cash / Cr AR`, but there is no UI to apply partial payments or track overpayments/underpayments.
4. **No bill-approval → payment flow** — Bills are created but not listed; payments reference `supplier_id` directly, not `bill_id` (except `Payment.bill_id` exists but is unused in UI).
5. **No invoice lifecycle** — Invoices can be created (`issued`) but not marked paid, sent, or voided. No credit-note flow.
6. **No period / fiscal-year context** — All date filters are ad-hoc; no fiscal-year calendar, no closing entries.
7. **`expenses` blueprint deprecated but route remains** — `/expenses` still renders a template; should redirect permanently.
8. **No email / PDF delivery** — Invoices/receipts render HTML but are not emailed or attached to records.
9. **No search/filter on reports** — General Ledger, Audit Trail, and Aging reports lack server-side pagination and advanced filters (account, user, reference).
10. **Approval blind spots** — Journal entries, invoices, and bills are not approval-gated; only payments and master-data edits are.

---

## 3. Missing Core Accounting Modules (Prioritized)

### P0 — Blocker for Professional Use

| # | Module | Why Critical |
| --- | --- | --- |
| 1 | **Chart of Accounts Manager** | COA is currently seed-only. Accountants must be able to add/edit/archive accounts, set opening balances, and reorder codes. |
| 2 | **Manual Journal Entries** | Essential for adjustments, accruals, depreciation, opening balances, and corrections. Must support multi-line, balanced entry validation, and approval. |
| 3 | **Bank Reconciliation** | Every business must reconcile bank statements. Needs: bank-account register, statement import (CSV/OFX), match/unmatch, unreconciled report. |
| 4 | **Invoice & Bill Tax Logic** | Replace hardcoded `tax_amount=0.0` with per-line tax codes, tax-inclusive/exclusive pricing, and proper `Tax Payable` liability posting. |
| 5 | **AR Payment Application** | Support partial payments, overpayments, and unallocated cash. Update AR aging accordingly. |

### P1 — High Value

| # | Module | Why Important |
| --- | --- | --- |
| 6 | **Multi-Currency** | Each `Business` already has `currency`; add exchange-rate table, auto-FX posting, and multi-currency reports. |
| 7 | **Fixed Assets & Depreciation** | Asset register, depreciation methods (straight-line, reducing-balance), auto-journal entries, disposal. |
| 8 | **Credit Notes / Refunds** | Reverse sales/purchases, update AR/AP, and inventory if applicable. |
| 9 | **Recurring Transactions** | Templates for invoices, bills, expenses, and journal entries with auto-creation. |
| 10 | **Purchase Orders** | PO → Goods Receipt → Bill → Payment lifecycle. |

### P2 — Nice-to-Have

| # | Module | Why Nice-to-Have |
| --- | --- | --- |
| 11 | **Payroll** | Staff payments → payroll journal + statutory deductions. |
| 12 | **Budgeting & Forecasting** | Budget tables, actual-vs-budget variance. |
| 13 | **Estimates / Quotes** | Convert quote → invoice. |
| 14 | **Document Attachments** | Upload invoices, receipts, bills. |
| 15 | **Time Tracking / Projects** | Billable hours → invoices. |

---

## 4. UI / UX Improvements

### 4.1 Responsive Design (Tab / Mobile / Desktop)

| Issue | Fix |
| --- | --- |
| No max-width container for large screens | Wrap `.main-content` in a `.container-narrow` (max-width: 1400px, centered) to prevent ultra-wide line lengths on 4K monitors. |
| Breakpoints only at 768/900/1200 | Add `1024px` tablet breakpoint for sidebar + grid tweaks. Add `480px` for small phones. |
| No mobile bottom nav | Add a bottom tab bar on `< 768px` for 4–5 top actions (Dashboard, Sales, Purchases, Payments, More). |
| Sidebar toggle not keyboard-accessible | Ensure `#sidebarToggle` has `tabindex="0"` and Enter/Space handlers. |
| No print stylesheets | Add `@media print` rules to hide sidebar, use white background, and print financial reports cleanly. |
| Charts not touch-friendly | Increase Chart.js point radius and hit detection on touch devices (`options.plugins.tooltip` + `hover.mode`). |
| No responsive typography | Use `clamp()` for `h1`/`h2`/KPI values: `font-size: clamp(1.5rem, 2vw, 2rem)`. |

### 4.2 Accessibility (WCAG 2.1 AA)

| Issue | Fix |
| --- | --- |
| No skip link | Add `<a href="#main-content" class="skip-link">Skip to content</a>` at the top of `base.html`. |
| No focus trap / return focus in modals | Use Bootstrap's native `tabindex` handling, or add JS to trap focus and return to trigger on close. |
| Color contrast unverified | Run axe/contrast checker. Replace `rgba(248,250,252,0.55)` muted text with `#94a3b8` (slate-400) for body text; keep `#f8fafc` for headings. Ensure all text meets 4.5:1. |
| No `aria-describedby` on hints | Link `.field-hint` spans to inputs via `aria-describedby="id-hint"`. |
| No `aria-invalid` on errors | When rendering `input-error`, add `aria-invalid="true"` and `aria-describedby="id-error"`. |
| Table headers lack `scope` | Add `scope="col"` to all `<th>` in report and data tables. |
| Charts lack accessible fallback | Add `aria-label` and a hidden `<table>` summary for every `<canvas>` chart. |
| Loading spinner no ARIA | Add `role="status" aria-live="polite"` + `<span class="visually-hidden">Loading...</span>` to `.loading-overlay`. |
| No keyboard-visible focus | Define `:focus-visible` styles: `outline: 2px solid var(--primary); outline-offset: 2px;`. |
| Flash messages auto-dismiss | If auto-dismissing, add `role="alert"` instead of `role="status"`. |

### 4.3 Readability & Professional Polish

| Issue | Fix |
| --- | --- |
| Dark-only theme | Add a theme toggle (light/dark) stored in `localStorage` + per-business `setting`. Light theme: white cards, slate text, subtle borders. |
| All-caps table headers | Reduce to `text-transform: capitalize` or small-caps for readability. |
| KPI cards lack trend indicators | Add month-over-month % change with up/down arrows. |
| Empty states are basic | Replace inline SVG empty states with consistent `.empty-state` component: icon + heading + descriptive text + CTA button. |
| No breadcrumb navigation | Add breadcrumb trail on detail/report pages (e.g., Reports > General Ledger). |
| Pagination is minimal | Add page-size selector (10/25/50/100) and total-count display. |
| No confirmation dialogs | Add `data-confirm` attributes or Bootstrap modals for destructive actions (delete, void, reset). |
| Form validation feedback | Show inline error messages under each field, not just flash banners. |
| Receipt / invoice print view | Create dedicated print templates with proper page breaks, company header, and QR-code stub. |
| Superadmin theme divergence | Consolidate into the same design system with a CSS class modifier (`.theme-light`) instead of a separate `sa_base.html`. |

---

## 5. Data Model & Security Fixes

| Issue | Fix |
| --- | --- |
| `GET /api/products` is public | Move behind `@login_required` or add business-scoped API key auth. |
| `JournalEntry` hard-delete cascade | Add `is_deleted` soft-delete flag + `deleted_by` + `deleted_at`. Block delete if any downstream report is published. |
| `Invoice` / `Bill` status limited | Add `sent`, `paid`, `overdue`, `void` statuses. |
| `Customer` / `Supplier` `opening_balance` | Add `opening_balance_date` and post opening-balance journal entries on fiscal-year creation. |
| `Payment` `bill_id` unused | Wire bill selection into Payments Hub; allow applying payment to specific bills. |
| `FinancialCategory` / `LineItem` not enforced | Make `category_id` + `line_item_id` required on `Payment` and validate `line_item.account_code` maps to active COA. |
| `Setting` key/value as strings | Add typed setting metadata or use JSON column for structured config (tax, currency, fiscal year). |
| No CSRF on API JSON endpoints | Add CSRF protection or switch to token-based auth for JSON API. |
| `Business` lacks fiscal-year config | Add `fiscal_year_start` (month/day) and `current_fiscal_year_id`. |

---

## 6. Prioritized Implementation Plan

### Phase 1 — Foundation (Weeks 1–2)

1. **Security**: Lock `/api/products` and other JSON endpoints. Add API auth.
2. **COA Manager**: CRUD UI for Chart of Accounts with opening-balance support.
3. **Manual Journal Entries**: Multi-line form with auto-balance validation, approval workflow, and reference linking.
4. **Theme Toggle**: Light/dark mode with CSS variables + `localStorage`.
5. **Skip link + focus management**: Accessibility quick wins.

### Phase 2 — Accounting Hardening (Weeks 3–4)

6. **Tax per Line Item**: Update `Invoice`/`Bill`/`InvoiceItem`/`BillItem` to support tax codes, tax-inclusive pricing, and auto-post to `Tax Payable (2200)`.
7. **AR Payment Application**: Partial/overpayment handling, unallocated cash ledger, AR aging updates.
8. **Bank Reconciliation Module**: Bank-account register, CSV statement import, match/unmatch, reconciliation report.
9. **Invoice Lifecycle**: `draft → sent → paid → void` with credit-note support.
10. **Responsive Breakpoints**: Add 480px / 1024px breakpoints, bottom mobile nav, print styles.

### Phase 3 — Advanced Modules (Weeks 5–6)

11. **Multi-Currency**: Exchange-rate table, FX gain/loss, multi-currency COA accounts.
12. **Fixed Assets & Depreciation**: Asset CRUD, depreciation schedules, auto-journal entries.
13. **Recurring Transactions**: Templates + scheduler (Celery beat) for auto-creation.
14. **Purchase Orders**: PO → receipt → bill → payment flow.
15. **Accessibility Polish**: Contrast audit, `aria-describedby`, chart fallbacks, error-state ARIA.

### Phase 4 — Polish & Scale (Weeks 7–8)

16. **Budgeting & Forecasting**: Budget tables + variance reports.
17. **Document Attachments**: File upload for invoices, bills, receipts.
18. **Email & PDF Delivery**: WeasyPrint PDFs emailed via Celery.
19. **Superadmin Theme Unification**: Merge `sa_base.html` into main design system.
20. **Performance**: Server-side pagination for all report tables, query optimization, CDN for static assets.

---

## 7. Validation & Testing

- **Accounting**: Expand `tests/test_accounting.py` to cover:
  - Manual journal entry posting + approval
  - Tax per line item + tax-payable balancing
  - AR partial payment + aging update
  - Bank reconciliation matching
  - Multi-currency FX rounding
- **Routes**: Add route tests for new modules (COA, JE, bank recon).
- **UI/UX**: Add Playwright tests for:
  - Sidebar toggle on mobile (320px, 768px, 1024px, 1440px)
  - Theme toggle persistence
  - Skip link + keyboard tab order
  - Modal focus trap
- **Security**: Scan with `bandit` and `flask-talisman`; verify `/api/*` auth.

---

## 8. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Schema changes break existing data | Use Alembic migrations; backfill `is_deleted`, `status` columns with defaults. |
| Approval gating slows daily ops | Make approval optional per config; default to "no approval" for small transactions. |
| Tax logic complexity | Start with VAT-style per-line tax; avoid nested tax-inclusive math until core flow is stable. |
| Bank-recon CSV parsing fragility | Support OFX first (structured), then CSV with column-mapping UI. |
| Responsive refactor breaks existing layouts | Test on real devices + BrowserStack before merge; keep breakpoints additive. |

---

## 9. Open Questions

1. Should tax be **VAT-style** (output/input tax) or **sales-tax** (single-stage)? Recommended: VAT-style for international parity.
2. Should we support **cash-basis and accrual-basis** reports, or commit to one? Recommended: default accrual with cash-basis P&L as an option.
3. Do we need **depreciation** in Phase 1 or can it wait? Recommended: Phase 2, after bank recon.
4. Should `/api/*` remain public for integrations? Recommended: add token auth + rate limiting.
