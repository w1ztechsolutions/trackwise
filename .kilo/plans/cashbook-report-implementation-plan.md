# Cashbook Report — Implementation Action Plan

## Executive Summary

The **Cashbook Report** is completely missing from the TrackWise codebase. There is no model, service, route, template, test, or documentation for it. This plan defines the work needed to implement it following the existing 3-layer report architecture (Service → Route → Template).

A cashbook report shows all cash (account 1000) and bank (1100) transactions chronologically, with running balances — essentially a General Ledger filtered to liquid accounts.

---

## Current State

| Layer | Existing Files | Cashbook Status |
|-------|---------------|-----------------|
| **Service** | pp/services/reports/{8 services} | ❌ Missing cashbook.py |
| **Route** | pp/reports/routes.py (8 endpoints) | ❌ Missing /reports/cashbook |
| **Template** | 	emplates/reports.html (8 blocks) | ❌ Missing cashbook block |
| **Export** | pp/services/reports/__init__.py | ❌ Missing get_cashbook |
| **PDF Task** | pp/tasks/report_tasks.py | ❌ Missing cashbook case |
| **Test** | 	ests/test_reports.py (8 tests) | ❌ Missing 	est_cashbook |
| **Docs** | README.md, API.md | ❌ Missing references |

**Data model support:** ✅ Complete. Cash (code 1000) and Bank (1100) accounts exist in ChartOfAccounts. All transactions flow through JournalEntry/JournalLine. No new DB table is needed.

---

## Action Items

### 1. Create Service: pp/services/reports/cashbook.py *(HIGH PRIORITY)*

**Pattern to follow:** general_ledger.py (chronological entries with running balance).

**Responsibilities:**
- Query JournalLine joined with JournalEntry and ChartOfAccounts
- Filter by usiness_id and account codes 1000 (Cash) and 1100 (Bank)
- Apply optional start_date / nd_date filters
- Order by ntry_date ASC, ntry_id ASC, line_id ASC
- Compute running balance per entry (assets = debit balance: unning += debit - credit)
- Resolve created_by user IDs to display names (avoid N+1)
- Return structured dict with entries, accounts, totals, date filters

**Proposed return shape:**
`python
{
    'entries': [
        {
            'date': datetime,
            'entry_id': int,
            'description': str,
            'reference_type': str,
            'reference_id': int,
            'account_code': str,       # '1000' or '1100'
            'account_name': str,       # 'Cash' or 'Bank'
            'debit': float,            # Money in
            'credit': float,           # Money out
            'balance': float,          # Running balance
            'created_by_name': str,
            'created_at': datetime,
        },
        ...
    ],
    'accounts': [...],               # Cash + Bank accounts
    'total_debits': float,
    'total_credits': float,
    'net_cash_flow': float,
    'opening_balance': float,
    'closing_balance': float,
    'start_date': datetime | None,
    'end_date': datetime | None,
}
`

**Key decisions:**
- Combine Cash + Bank into a single chronological list (most useful for SMEs)
- Show running balance as a separate column
- Include opening/closing balance summaries
- Follow existing loat(line.debit_amount or 0) casting pattern

---

### 2. Add Route: pp/reports/routes.py *(HIGH PRIORITY)*

**Add after the general_ledger route (around line 203):**

`python
@reports_bp.route('/reports/cashbook')
@login_required
def cashbook():
    """Cashbook report showing all cash and bank transactions."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    start_date = None
    end_date = None

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)

    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)

    if business_id:
        cb_data = get_cashbook(business_id, start_date, end_date)
    else:
        cb_data = {
            'entries': [], 'accounts': [], 'total_debits': 0,
            'total_credits': 0, 'net_cash_flow': 0,
            'opening_balance': 0, 'closing_balance': 0,
        }

    # Paginate entries
    per_page = min(max(per_page, 10), 100)
    total = len(cb_data.get('entries', []))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    cb_data['entries'] = cb_data.get('entries', [])[start_idx:end_idx]
    cb_data['page'] = page
    cb_data['per_page'] = per_page
    cb_data['total'] = total
    cb_data['pages'] = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'reports.html',
        report_type='cashbook',
        cb=cb_data,
        start_date=start_date_str,
        end_date=end_date_str,
        page=page,
        per_page=per_page,
        total=total,
        pages=cb_data['pages'],
    )
`

**Also update the import block at top:**
`python
from app.services.reports import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_trial_balance,
    get_general_ledger,
    get_audit_log,
    get_ar_aging,
    get_ap_aging,
    get_cashbook,          # ← ADD
)
`

---

### 3. Update Template: 	emplates/reports.html *(HIGH PRIORITY)*

#### 3a. Add dropdown option (line 18-25 area):
`html
<option value="{{ url_for('reports.cashbook') }}" {% if report_type == 'cashbook' %}selected{% endif %}>Cashbook</option>
`

#### 3b. Add date filter condition (line 31):
`html
{% if report_type in ['income_statement', 'cash_flow', 'general_ledger', 'audit_log', 'cashbook'] %}
`

#### 3c. Add cashbook template block (after General Ledger block, before AR Aging):
`html
<!-- Cashbook -->
{% if report_type == 'cashbook' %}
<div class="glass-card">
    <h3 class="section-title">Cashbook</h3>

    <!-- Summary Cards -->
    <div class="dashboard-grid mb-4">
        <div class="glass-card">
            <h4 class="section-title text-sm">Opening Balance</h4>
            <span class="value text-primary">{{ cb.opening_balance | currency }}</span>
        </div>
        <div class="glass-card">
            <h4 class="section-title text-sm">Total Receipts</h4>
            <span class="value text-success">{{ cb.total_debits | currency }}</span>
        </div>
        <div class="glass-card">
            <h4 class="section-title text-sm">Total Payments</h4>
            <span class="value text-danger">{{ cb.total_credits | currency }}</span>
        </div>
        <div class="glass-card">
            <h4 class="section-title text-sm">Closing Balance</h4>
            <span class="value text-info">{{ cb.closing_balance | currency }}</span>
        </div>
    </div>

    <div class="table-container">
        <table class="custom-table">
            <thead>
                <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Account</th>
                    <th scope="col">Description</th>
                    <th scope="col">Reference</th>
                    <th scope="col" class="text-end">Receipt (Dr)</th>
                    <th scope="col" class="text-end">Payment (Cr)</th>
                    <th scope="col" class="text-end">Balance</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in cb.entries %}
                    <tr>
                        <td>{{ entry.date.strftime('%Y-%m-%d') }}</td>
                        <td>{{ entry.account_code }} - {{ entry.account_name }}</td>
                        <td>{{ entry.description }}</td>
                        <td>
                            {% if entry.reference_type and entry.reference_id %}
                                {{ entry.reference_type }} #{{ entry.reference_id }}
                            {% else %}
                                -
                            {% endif %}
                        </td>
                        <td class="text-end">{{ entry.debit | currency }}</td>
                        <td class="text-end">{{ entry.credit | currency }}</td>
                        <td class="text-end fw-bold">{{ entry.balance | currency }}</td>
                    </tr>
                {% else %}
                    <tr>
                        <td colspan="7" class="text-center text-muted">No cash/bank transactions found</td>
                    </tr>
                {% endfor %}
            </tbody>
            <tfoot>
                <tr class="fw-bold">
                    <td colspan="4">Totals</td>
                    <td class="text-end">{{ cb.total_debits | currency }}</td>
                    <td class="text-end">{{ cb.total_credits | currency }}</td>
                    <td class="text-end">{{ cb.net_cash_flow | currency }}</td>
                </tr>
            </tfoot>
        </table>
    </div>

    {% if cb.pages and cb.pages > 1 %}
    <div class="d-flex justify-content-between align-items-center mt-3">
        <form method="GET" action="{{ url_for('reports.cashbook') }}" class="d-flex align-items-center gap-2">
            <input type="hidden" name="start_date" value="{{ start_date or '' }}">
            <input type="hidden" name="end_date" value="{{ end_date or '' }}">
            <label class="form-label mb-0" for="per_page">Rows per page:</label>
            <select id="per_page" name="per_page" class="form-control form-control-sm w-auto" onchange="this.form.submit()">
                <option value="10" {% if cb.per_page == 10 %}selected{% endif %}>10</option>
                <option value="25" {% if cb.per_page == 25 %}selected{% endif %}>25</option>
                <option value="50" {% if cb.per_page == 50 %}selected{% endif %}>50</option>
                <option value="100" {% if cb.per_page == 100 %}selected{% endif %}>100</option>
            </select>
        </form>
        <nav aria-label="Cashbook pagination">
            <ul class="pagination mb-0">
                {% if cb.page > 1 %}
                <li class="page-item"><a class="page-link" href="{{ url_for('reports.cashbook', start_date=start_date, end_date=end_date, page=cb.page-1, per_page=cb.per_page) }}">Previous</a></li>
                {% endif %}
                <li class="page-item active"><span class="page-link">{{ cb.page }} of {{ cb.pages }}</span></li>
                {% if cb.page < cb.pages %}
                <li class="page-item"><a class="page-link" href="{{ url_for('reports.cashbook', start_date=start_date, end_date=end_date, page=cb.page+1, per_page=cb.per_page) }}">Next</a></li>
                {% endif %}
            </ul>
        </nav>
    </div>
    {% endif %}
</div>
{% endif %}
`

---

### 4. Export Service: pp/services/reports/__init__.py *(MEDIUM PRIORITY)*

Add the import and export:
`python
from .cashbook import get_cashbook

__all__ = [
    'get_income_statement',
    'get_balance_sheet',
    'get_cash_flow',
    'get_trial_balance',
    'get_general_ledger',
    'get_audit_log',
    'get_ar_aging',
    'get_ap_aging',
    'get_cashbook',
]
`

---

### 5. Add PDF Handling: pp/tasks/report_tasks.py *(MEDIUM PRIORITY)*

Add get_cashbook to imports and add the lif report_type == 'cashbook' branch.

**Note:** PDF templates (	emplates/reports/{type}_pdf.html) are missing for ALL reports — this is a pre-existing bug. Fixing it is out of scope for the cashbook report but should be tracked separately.

---

### 6. Add Test: 	ests/test_reports.py *(HIGH PRIORITY)*

Add 	est_cashbook method following the existing pattern:

`python
def test_cashbook(self):
    """Test cashbook report generation."""
    from app.services.reports import get_cashbook

    # Record a purchase (cash outflow)
    record_purchase(
        purchase_date=datetime(2026, 6, 1),
        supplier='Supplier X',
        notes='Test purchase',
        items_data=[{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 100.0}],
        business_id=self.business.id,
        created_by=self.user.id,
    )

    # Record a sale (cash inflow)
    record_sale(
        sale_date=datetime(2026, 6, 2),
        customer_name='Customer Y',
        items_data=[{'product_id': self.product.id, 'quantity': 5, 'unit_price': 200.0}],
        business_id=self.business.id,
        created_by=self.user.id,
    )

    # Get cashbook
    cb = get_cashbook(self.business.id)

    self.assertIn('entries', cb)
    self.assertIn('total_debits', cb)
    self.assertIn('total_credits', cb)
    self.assertIn('opening_balance', cb)
    self.assertIn('closing_balance', cb)
    self.assertIn('net_cash_flow', cb)
    self.assertGreater(len(cb['entries']), 0)

    # Verify entries have required fields
    for entry in cb['entries']:
        self.assertIn('date', entry)
        self.assertIn('account_code', entry)
        self.assertIn('account_name', entry)
        self.assertIn('debit', entry)
        self.assertIn('credit', entry)
        self.assertIn('balance', entry)
`

---

### 7. Update Documentation *(LOW PRIORITY)*

| File | Action |
|------|--------|
| README.md | Add /reports/cashbook to report endpoints list |
| docs/API.md | Add cashbook to planned /api/reports/ endpoints |
| docs/professionalization-plan.md | Mark cashbook as completed if listed |

---

## Pre-existing Issues (Out of Scope but Should Be Tracked)

These issues affect all reports including the new cashbook report:

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| Missing PDF templates | Medium | 	emplates/reports/ | eport_tasks.py references eports/{type}_pdf.html but the 	emplates/reports/ directory does not exist |
| Missing JSON API | Low | pp/api/routes.py | No /api/reports/* endpoints exist; docs list them as planned |
| Hardcoded account codes | Low | All services | Account codes like 1000, 5000 are hardcoded instead of looked up dynamically |
| Missing breadcrumb nav | Low | 	emplates/reports.html | No breadcrumb navigation; noted in professionalization-plan.md |

---

## Implementation Sequence

`
1. cashbook.py (service)          ← Foundation, no dependencies on other new files
2. __init__.py (export)           ← Depends on #1
3. routes.py (route)              ← Depends on #1, #2
4. tests/test_reports.py (test)   ← Depends on #1, #2
5. templates/reports.html         ← Depends on #3
6. report_tasks.py (PDF)          ← Depends on #1
7. Documentation                  ← Depends on #3
`

---

## Files to Modify/Create

| File | Action | Lines Changed |
|------|--------|---------------|
| pp/services/reports/cashbook.py | CREATE | ~120 |
| pp/services/reports/__init__.py | MODIFY | +2 import, +1 export |
| pp/reports/routes.py | MODIFY | +1 import, +1 route (~50 lines) |
| 	emplates/reports.html | MODIFY | +1 dropdown, +1 filter condition, +1 block (~100 lines) |
| pp/tasks/report_tasks.py | MODIFY | +1 import, +1 branch (~8 lines) |
| 	ests/test_reports.py | MODIFY | +1 test method (~50 lines) |
| README.md | MODIFY | +1 endpoint line |
| docs/API.md | MODIFY | +1 endpoint line |

**Total new code:** ~330 lines  
**Total modified files:** 7

---

## Verification Checklist

- [ ] pytest tests/test_reports.py::TestReportServices::test_cashbook passes
- [ ] Full test suite pytest passes (no regressions)
- [ ] /reports/cashbook loads without error with no date filters
- [ ] /reports/cashbook?start_date=2026-01-01&end_date=2026-12-31 filters correctly
- [ ] Pagination works (next/prev buttons)
- [ ] Running balance is correct (debits increase, credits decrease for asset accounts)
- [ ] Opening balance = sum of all cash/bank debits - credits before start_date
- [ ] Closing balance = opening + net_cash_flow
- [ ] Report dropdown navigates correctly to cashbook
- [ ] No N+1 queries on created_by user resolution
