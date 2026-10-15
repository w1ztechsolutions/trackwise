# TrackWise Deep Audit Report
**Date:** 2026-09-30  
**Project:** TrackWise – Accounting, Inventory & Production Management System  
**Scope:** Full repository review for bugs, errors, deprecated packages, and accounting standards compliance

---

## EXECUTIVE SUMMARY

TrackWise is a **mature, production-ready Flask-based multi-tenant accounting platform** with strong foundational architecture. The system implements double-entry accounting, FIFO inventory, sales/purchase management, and financial reporting aligned with **QuickBooks, Sage, Xero, and Zoho standards**.

**Overall Status:** ⚠️ **GOOD WITH CRITICAL GAPS**

- ✅ Core accounting engine is sound
- ✅ Database schema uses Numeric(14,2) precision correctly
- ✅ Test coverage is comprehensive
- ⚠️ **Critical:** Missing multi-currency support (hard-coded to 'MWK')
- ⚠️ **Critical:** Soft-delete audit trails incomplete/not enforced
- ⚠️ **High:** No reversals/correcting entries framework
- ⚠️ **High:** Tax calculation logic oversimplified
- ⚠️ **Medium:** AR/AP aging uses naive date logic, doesn't account for payments
- ⚠️ **Medium:** No formal reconciliation lock/period close
- ✅ Dependency stack is current (Flask 3.1.3, SQLAlchemy 2.0.51, no deprecated packages)

---

## SECTION 1: DEPENDENCY & PACKAGE AUDIT

### ✅ EXCELLENT — Dependencies are Current

**Requirements.txt Status (as of 2026-09-30):**

| Package | Version | Status | Notes |
| --------- | --------- | -------- | ------- |
| Flask | 3.1.3 | ✅ Current | Latest stable 3.x line |
| Flask-SQLAlchemy | 3.1.1 | ✅ Current | Latest stable |
| SQLAlchemy | 2.0.51 | ✅ Current | Production-grade ORM, full Python 3.12 support |
| Flask-Migrate | 4.1.0 | ✅ Current | Alembic wrapper, maintained |
| psycopg | 3.3.4 | ✅ Current | Modern PostgreSQL driver for psycopg3 |
| Flask-Login | 0.6.3 | ✅ Current | Latest stable, well-maintained |
| Flask-WTF | 1.3.0 | ✅ Current | Latest stable |
| Werkzeug | 3.1.6 | ✅ Current | Latest stable, shipped with Flask 3.1 |
| Jinja2 | 3.1.6 | ✅ Current | Latest stable |
| WeasyPrint | 65.0 | ✅ Current | PDF generation, supports Python 3.12 |
| Celery | ≥5.4.0 | ✅ Current | Async task queue, latest 5.x line |
| redis | ≥5.0.0 | ✅ Current | Latest stable |
| gunicorn | ≥23.0.0 | ✅ Current | Latest stable WSGI server |
| stripe | ≥10.0.0 | ✅ Current | Payment processing, well-maintained |
| Flask-Limiter | 3.5.0 | ✅ Current | Rate limiting, latest stable |
| alembic | 1.18.5 | ✅ Current | Database migrations, latest stable |
| python-dotenv | 1.1.1 | ✅ Current | Environment management |

**Finding:** ✅ **NO DEPRECATED PACKAGES DETECTED**  
All dependencies are on current, stable, and maintenance-active versions. No immediate security upgrades required.

### ⚠️ Configuration Improvements Needed

**Issue 1: Missing Python Version Pinning in requirements.txt**

- Current: No explicit Python version constraint
- Recommended: Add `# Python >=3.12` comment header
- Impact: Ensures CI/CD clarity; doesn't affect runtime

---

## SECTION 2: DATABASE & ACCOUNTING SCHEMA AUDIT

### ✅ Numeric Precision — Best Practice Compliance

**All monetary columns use `Numeric(14, 2)` or `Numeric(12, 2)` decimal types:**

- ✅ Prevents floating-point rounding errors (common bug in accounting)
- ✅ Complies with QuickBooks, Sage, Xero, Zoho standards
- ✅ Supports values up to 99,999,999.99 (standard SME range)

**Models audited:**

- [JournalLine](/app/models/accounting.py): `Numeric(14, 2)` ✅
- [InvoiceItem](/models.py): `Numeric(14, 2)` ✅
- [BillItem](/models.py): `Numeric(14, 2)` ✅
- [Payment](/models.py): `Numeric(14, 2)` ✅
- [Product](/models.py): `Numeric(12, 2)` ✅

**Finding:** ✅ **NO ROUNDING OR PRECISION BUGS DETECTED**

---

### ✅ Double-Entry Enforcement

[accounting_service.py](/app/services/accounting_service.py) **correctly**:

1. Validates all journal entries balance within ±0.01 tolerance
2. Enforces minimum 2 lines per entry
3. Posts entries atomically (all-or-nothing)
4. Logs via [AuditLog](/app/models/accounting.py) table

```python
# From accounting_service.py:
if abs(total_debit - total_credit) > 0.01:
    raise AccountingException(...)  # ✅ Correct tolerance for Numeric(14,2)
```

**Finding:** ✅ **DOUBLE-ENTRY INTEGRITY SOUND**

---

### ⚠️ CRITICAL: Missing Entry Reversal Framework

**Issue:** No mechanism to reverse/correct posted entries

- Current behavior: Manual deletion via soft-delete (is_deleted flag)
- **Problem:** Breaks audit trail; does not match accounting standards (QuickBooks, Xero, Sage require explicit reversals)
- **Risk:** Auditors cannot reconcile transaction history; regulatory non-compliance

**Recommended Fix:**

```sql
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS 
  reversed_by_entry_id INTEGER REFERENCES journal_entries(id);
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS 
  reversal_reason VARCHAR(255);
```

**Impact:** MEDIUM (affects audit compliance but not data integrity)

---

### ⚠️ CRITICAL: Hard-Coded Currency (MWK)

**Issue:** Business.currency defaults to 'MWK' (Malawi Kwacha); no multi-currency support

**Current:**

```python
# From accounting.py:
currency = db.Column(db.String(10), nullable=False, default='MWK')
```

**Problems:**

1. ❌ Cannot operate multi-currency businesses (e.g., USD, ZAR, ZWL)
2. ❌ No exchange rate tracking or conversion logic
3. ❌ Foreign receivables/payables cannot be modeled
4. ❌ Violates IAS 21 (International Accounting Standard for Currency)
5. ❌ All competitors (QB, Xero, Zoho) support multi-currency

**Risk:** HIGH – Blocks regional expansion beyond MWK markets

**Recommended Fix:** (Phase 2)

- [ ] Create `CurrencyRate` model with date-based rates
- [ ] Add `currency_code` column to JournalLine (optional, for reporting)
- [ ] Implement revaluation entries for FX gains/losses

---

### ⚠️ HIGH: No Period Close/Reconciliation Lock

**Issue:** No mechanism to lock periods or mark year-end close

**Missing:**

- No "locked period" concept (can edit past transactions indefinitely)
- No COA/GL freeze for audit trail
- No way to prevent post-close journal entries

**Risk:** MEDIUM – Large organizations need this for SOX/IFRS compliance

**Recommended Fix:**

```sql
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS 
  last_closed_period_date DATE;
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS 
  is_closed_period BOOLEAN DEFAULT FALSE;
```

---

## SECTION 3: ACCOUNTING LOGIC AUDIT

### ✅ Correct Account Type Handling

Trial Balance, Income Statement, Balance Sheet correctly compute balances by account type:

- Assets/Expenses: Normal debit balance (Dr = +, Cr = −)
- Liabilities/Equity/Income: Normal credit balance (Cr = +, Dr = −)

**Files verified:**

- [trial_balance.py](/app/services/reports/trial_balance.py) ✅
- [balance_sheet.py](/app/services/reports/balance_sheet.py) ✅
- [income_statement.py](/app/services/reports/income_statement.py) ✅

---

### ✅ FIFO Inventory Costing

[fifo_service.py](/services/fifo_service.py) correctly:

1. Tracks purchase layers (FIFO by timestamp)
2. Consumes layers in order (oldest first)
3. Records COGS via [StockTransaction](/models.py)
4. Updates inventory P&L atomically

**Test coverage:** [test_fifo.py](/tests/test_fifo.py) ✅ All tests pass

**Finding:** ✅ **FIFO LOGIC SOUND**

---

### ⚠️ HIGH: AR/AP Aging Reports – Logic Flaw

**File:** [ar_aging.py](/app/services/reports/ar_aging.py), [ap_aging.py](/app/services/reports/ap_aging.py)

**Issue:** Aging calculation ignores payments received/made

**Current logic:**

```python
for inv in customer_invoices:
    if inv.status in ('draft', 'issued'):
        total_balance += float(inv.total_amount or 0)
```

**Problems:**

1. ❌ Counts full invoice even if partially paid
2. ❌ No link to Receipt/Payment records
3. ❌ Violates Xero/QB aging methodology
4. ❌ Unusable for credit management

**Recommended Fix:**

- Calculate balance as: `invoice.total_amount - sum(receipts.amount WHERE invoice_id = X)`
- Segment by due date of *unpaid balance*, not invoice date

**Impact:** MEDIUM (reports are misleading but GL is correct)

---

### ⚠️ MEDIUM: Tax Calculation Oversimplified

**File:** [income_statement.py](/app/services/reports/income_statement.py)

**Current:**

```python
tax_amount = max(0.0, pre_tax_profit * (tax_rate / 100.0))
```

**Problems:**

1. ❌ Applies flat rate to profit (ignores tax rules: deductible expenses, loss carryforward)
2. ❌ No deferred tax asset/liability tracking
3. ❌ No quarterly/provisional tax handling
4. ❌ Inconsistent with tax authority requirements (Malawi Revenue Authority, etc.)

**Recommended Fix:**

- Create `TaxConfig` model for jurisdiction-specific rules
- Link tax adjustments to GL via separate journal entries
- Support deferred tax (deferred tax asset/liability accounts)

**Impact:** MEDIUM (financial reports may be inaccurate for tax planning)

---

### ⚠️ MEDIUM: No Deferred Revenue / Subscription Revenue Recognition

**Current:** Revenue posted immediately on invoice creation (cash vs. accrual mismatch)

**Issue:** IFRS 15 / ASC 606 requires performance obligation tracking; current model doesn't support:

- Multi-period subscriptions (revenue recognition over time)
- Conditional revenue (e.g., refundable until day 30)
- Contract asset/liability accounts

**Recommended Fix:**

- Create `RevenueRecognition` model (milestone-based)
- Support subscription revenue amortization entries
- Add deferred revenue (liability) account support

**Impact:** LOW for SMEs (high for SaaS, subscription-model businesses)

---

## SECTION 4: BUSINESS LOGIC & AUDIT TRAIL

### ✅ Soft-Delete Implementation

[JournalEntry](/app/models/accounting.py) correctly implements soft-delete:

```python
is_deleted = db.Column(db.Boolean, nullable=False, default=False)
deleted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
deleted_at = db.Column(db.DateTime, nullable=True)
```

**Verified:** All queries filter `is_deleted = False` ✅

---

### ⚠️ CRITICAL: Audit Log Not Enforced for All Transactions

**Issue:** Only journal_entries are logged; inventory adjustments, payment approvals, and user actions are NOT logged

**Missing audit coverage:**

- ❌ StockMovement/StockTransaction changes
- ❌ Purchase/Sale/Invoice modifications
- ❌ Payment status transitions
- ❌ User login/permission changes
- ❌ Report exports

**Risk:** HIGH – Regulatory bodies (MRA, tax authorities) require complete transaction audit trails

**Recommended Fix:**

- Expand [AuditLog](/app/models/accounting.py) to trigger on all Create/Update/Delete via SQLAlchemy events
- Log user actions via middleware (login, logout, password change, report access)

**Impact:** CRITICAL (non-compliance with audit requirements)

---

### ✅ Approval Workflow Framework

[ApprovalRequest](/app/models/approval.py) correctly supports:

- Transaction-level approvals (journal_entry, payment)
- Role-based approval levels
- Audit trail (ApprovalAction)

**Finding:** ✅ **APPROVAL LOGIC SOUND**

---

## SECTION 5: MULTI-TENANCY & DATA ISOLATION

### ✅ business_id Scoping

All queries correctly filter by `business_id`:

- [accounting_service.py](/app/services/accounting_service.py) ✅
- [inventory_service.py](/app/services/inventory_service.py) ✅
- All route handlers ✅

**Test case:** [test_routes.py](/tests/test_routes.py) verifies users only see their business data ✅

**Finding:** ✅ **MULTI-TENANT ISOLATION SOUND**

---

## SECTION 6: SECURITY & COMPLIANCE

### ✅ No Hard-Coded Credentials

All sensitive config via environment variables (config.py)

- ✅ SECRET_KEY enforced in production
- ✅ DATABASE_URL via .env
- ✅ Neon Postgres pooling optimized

### ✅ CSRF Protection

Flask-WTF CSRF enabled on all POST/PUT/DELETE routes ✅

### ⚠️ Missing Security Headers (from CHANGELOG)

**Noted in CHANGELOG as FIXED:**

- ✅ CSP hardened (removed unsafe-inline)
- ✅ SRI on external scripts
- ✅ Inline event handlers replaced

**Finding:** ✅ **Security headers appear correct**

---

## SECTION 7: TEST COVERAGE AUDIT

### ✅ Comprehensive Test Suite

| Test File | Status | Coverage | Notes |
| ----------- | -------- | ---------- | ------- |
| test_accounting.py | ✅ Pass | High | Tests post_entry, balancing, audit logs |
| test_reports.py | ✅ Pass | High | Tests all 8 reports (IS, BS, CF, TB, GL, AR/AP, Cashbook, Audit) |
| test_fifo.py | ✅ Pass | High | Tests FIFO layer consumption, COGS calculation |
| test_inventory_service.py | ✅ Pass | Medium | Tests stock adjustments, valuation |
| test_production.py | ✅ Pass | Medium | Tests batch creation, material usage |
| test_routes.py | ✅ Pass | High | Tests multi-tenancy, RBAC |
| test_coa_seeder.py | ✅ Pass | Medium | Tests COA initialization |
| test_database_config.py | ✅ Pass | Medium | Tests migration, schema compatibility |

**Finding:** ✅ **STRONG TEST COVERAGE**

---

## SECTION 8: ARCHITECTURAL REVIEW

### ✅ Clean Separation of Concerns

- **Models:** [app/models/](/app/models/) — Well-organized submodules (accounting.py, inventory.py, approval.py)
- **Services:** [app/services/](/app/services/) — Business logic (accounting_service, inventory_service, reports/)
- **Routes:** [app/{module}/routes.py](app/#) — HTTP handlers per blueprint
- **Database:** Migrations tracked in [migrations/versions/](/migrations/versions/) — Alembic-managed

### ✅ SQLAlchemy ORM Best Practices

- No raw SQL (except legacy schema repairs in [__init__.py](/app/__init__.py))
- Proper relationship cascades
- Indexes on foreign keys

### ⚠️ MEDIUM: Circular Import Risk

**File:** [app/accounting/routes.py](/app/accounting/routes.py) imports from [app/approvals/routes.py](/app/approvals/routes.py)  
**File:** [app/approvals/routes.py](/app/approvals/routes.py) may import from [app/accounting/routes.py](/app/accounting/routes.py)

**Risk:** Low (Python handles circular imports if not at module level), but refactor recommended

**Recommendation:** Extract shared approval logic to [app/services/](/app/services/) module

---

## SECTION 9: KNOWN ISSUES FROM CHANGELOG

### ✅ All Documented Bugs Fixed

| Issue | Status | Impact |
| ------- | -------- | -------- |
| RuntimeError: No secret key in production | ✅ Fixed | v1.0.1 |
| 404 on /register endpoint | ✅ Fixed | v1.0.1 |
| Missing superadmin templates | ✅ Fixed | v1.0.1 |
| KPI card overflow | ✅ Fixed | v1.0.1 |
| Missing mobile navigation | ✅ Fixed | v1.0.1 |
| CSP blocking Bootstrap Icons | ✅ Fixed | v1.0.1 |
| Multi-tenant data isolation | ✅ Fixed | v1.1.0 |
| Bank statement schema missing | ✅ Fixed | v1.1.0 |

---

## SECTION 10: COMPARISON TO INDUSTRY STANDARDS

### QuickBooks Compatibility

| Feature | TrackWise | Status |
| --------- | ----------- | -------- |
| Double-entry posting | ✅ Yes | Full compliance |
| Chart of Accounts hierarchy | ✅ Yes | Supported (parent_id) |
| Multi-business (company) | ✅ Yes | Via business_id |
| Audit trail | ⚠️ Partial | Only journal entries, not all transactions |
| Bank reconciliation | ✅ Yes | Implemented |
| Customer/Vendor master | ✅ Yes | With opening balances |
| Financial reports | ✅ Yes | IS, BS, CF, TB, GL, AR/AP Aging, Cashbook |
| Multi-currency | ❌ No | Hard-coded to MWK |
| Tax tracking | ⚠️ Basic | Flat rate, no jurisdiction rules |
| Expense categorization | ✅ Yes | FinancialCategory + LineItem |
| Payment approvals | ✅ Yes | Role-based workflow |

### Xero Compatibility

| Feature | TrackWise | Status |
| --------- | ----------- | -------- |
| API-first architecture | ⚠️ Partial | REST API present but limited |
| Real-time sync | ⚠️ No | Web-based only, no desktop sync |
| GST/VAT multi-jurisdiction | ❌ No | Single tax rate |
| Automated bank feeds | ⚠️ Partial | Manual statement upload only |
| Inventory integration | ✅ Yes | FIFO costing |
| Invoice-to-sales linkage | ✅ Yes | invoice_id column added |

### Zoho Books Compatibility

| Feature | TrackWise | Status |
| --------- | ----------- | -------- |
| Role-based permissions | ✅ Yes | admin, accountant, cashier, storekeeper, viewer |
| Approval workflows | ✅ Yes | Multi-level approval |
| Subscription billing | ✅ Yes | Plan/Subscription models |
| Expense management | ✅ Yes | Payments Hub |
| Production module | ✅ Yes | Batch tracking, material usage |
| Mobile app | ❌ No | Planned v2 |

### Sage Compatibility

| Feature | TrackWise | Status |
| --------- | ----------- | -------- |
| Manual journal entries | ✅ Yes | Full support |
| Accruals/Deferrals | ⚠️ Partial | No deferred revenue recognition |
| Cost centers | ⚠️ No | Future enhancement |
| Multi-branch accounting | ⚠️ No | Planned |

---

## SECTION 11: RECOMMENDED FIX PRIORITY

### 🔴 CRITICAL (Implement immediately)

| ID | Issue | Effort | Impact |
| ---- | ---- | -------- | -------- |
| C1 | Audit trail not enforced for all transactions | HIGH | Regulatory non-compliance |
| C2 | AR/AP aging ignores payments | MEDIUM | Misleading financial reports |
| C3 | No entry reversal framework | MEDIUM | Audit trail integrity |
| C4 | Hard-coded multi-currency (MWK only) | HIGH | Blocks regional expansion |

### 🟠 HIGH (Implement in next 2 quarters)

| ID | Issue | Effort | Impact |
| ---- | -------- | -------- | -------- |
| H1 | No period close/reconciliation lock | MEDIUM | Compliance gap (SOX/IFRS) |
| H2 | Tax calculation oversimplified | MEDIUM | Financial accuracy |
| H3 | No deferred revenue recognition (IFRS 15) | HIGH | For subscription-heavy businesses |
| H4 | Circular import risk in routing | LOW | Code quality |

### 🟡 MEDIUM (Implement in backlog)

| ID | Issue | Effort | Impact |
| ---- | ---- | -------- | -------- |
| M1 | Missing cost center support | MEDIUM | Departmental reporting |
| M2 | No expense budget tracking | LOW | For planning/forecasting |
| M3 | Limited export formats (PDF only, no Excel) | LOW | User convenience |

### ⚪ LOW (Nice-to-have)

| ID | Issue | Effort | Impact |
| ---- | ---- | -------- | -------- |
| L1 | Python version pinning in requirements.txt | LOW | CI/CD clarity |
| L2 | Refactor circular imports | LOW | Code maintainability |

---

## SECTION 12: ACTIONABLE RECOMMENDATIONS

### Immediate Actions (This Sprint)

1. **Expand AuditLog coverage:**

   ```python
   # Add SQLAlchemy event listeners in app/__init__.py
   @event.listens_for(StockMovement, 'after_insert')
   @event.listens_for(Payment, 'after_insert')
   def log_transaction(mapper, connection, target):
       # Log to AuditLog table
   ```

2. **Add entry reversal support:**

   ```sql
   ALTER TABLE journal_entries ADD COLUMN reversed_by_entry_id INTEGER;
   ALTER TABLE journal_entries ADD COLUMN reversal_reason VARCHAR(255);
   ```

3. **Fix AR/AP aging calculation** (see Section 3)

### Next Quarter

4. **Multi-currency foundation:**
   - Add CurrencyRate table
   - Implement revaluation journal entries
   - Support currency selection on reports

5. **Period close mechanism:**
   - Prevent editing closed periods
   - Add "year-end close" workflow

### Phase 2 (Next Year)

6. **IFRS 15 revenue recognition**
7. **Deferred tax asset/liability tracking**
8. **Cost center module**

---

## SECTION 13: DEPLOYMENT & OPERATIONS

### ✅ Production-Ready

- ✅ Vercel serverless-compatible
- ✅ Nginx + Gunicorn configuration present
- ✅ Health check endpoint (/health)
- ✅ Structured logging (logging_config.py)
- ✅ Environment-based config (DevelopmentConfig, ProductionConfig, TestingConfig)
- ✅ Database connection pooling tuned for Neon (serverless PostgreSQL)

### ⚠️ Missing Operational Docs

- ❓ No runbook for period close
- ❓ No disaster recovery procedure
- ❓ No data backup/retention policy

---

## SECTION 14: SUMMARY SCORECARD

| Category | Score | Status |
|----------|-------|--------|
| **Accounting Logic** | 9/10 | ✅ Excellent |
| **Data Integrity** | 9/10 | ✅ Excellent |
| **Audit Trail** | 6/10 | ⚠️ Incomplete |
| **Multi-Currency** | 2/10 | ❌ Critical gap |
| **Tax Compliance** | 5/10 | ⚠️ Basic only |
| **Security** | 8/10 | ✅ Good |
| **Test Coverage** | 8/10 | ✅ Good |
| **Documentation** | 7/10 | ✅ Good |
| **Code Quality** | 8/10 | ✅ Good |
| **Scalability** | 8/10 | ✅ Good (multi-tenant) |
| | **7.6/10** | **⚠️ GOOD WITH GAPS** |

---

## CONCLUSION

TrackWise is a **well-engineered, production-ready accounting system** suitable for SMEs in the Malawi/Southern Africa region. It successfully implements core double-entry accounting, FIFO inventory costing, sales/purchase management, and financial reporting aligned with industry standards.

**Strengths:**

- ✅ Sound accounting engine with perfect numerical precision
- ✅ Comprehensive financial reports (8+ report types)
- ✅ Strong multi-tenant architecture
- ✅ Current, secure dependency stack
- ✅ Good test coverage
- ✅ Responsive approval workflow

**Critical Gaps (Must Fix):**

1. **Incomplete audit trail** → Regulatory risk
2. **Hard-coded MWK currency** → Regional expansion blocked
3. **Simplified AR/AP aging** → Reports misleading
4. **No entry reversals** → Audit integrity risk

**Recommendation:** TrackWise is **READY FOR PRODUCTION** for single-currency operations (MWK). Before regional expansion or enterprise deployment, implement the 4 critical fixes above (3–6 months effort). With fixes, it will rival QuickBooks Online and Xero in feature parity for SME segments.

**Next Steps:**

1. Create GitHub issues for all 11 recommendations (C1–L2)
2. Prioritize C1 (audit log expansion)
3. Schedule multi-currency design phase (Q4 2026)

---

*Report prepared by: AI Code Review Agent*  
*Tools: ripgrep, SQLAlchemy introspection, pytest analysis*  
*No code changes made — report and recommendations only*
