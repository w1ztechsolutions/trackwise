"""Report routes for TrackWise."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import abort, render_template, request, redirect, url_for, flash, Response, send_file
from flask_login import current_user, login_required

from app.models import Product, Setting, db
from app.models.accounting import Branch, CostCenter
from services.fifo_service import get_inventory_valuation, get_profit_loss
from app.services.reports import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_trial_balance,
    get_general_ledger,
    get_audit_log,
    get_ar_aging,
    get_ap_aging,
    get_cashbook,
    get_expense_budget_variance,
    set_expense_budget,
)
from app.services.reports.xlsx_export import create_xlsx
from app.services.reports.xlsx_export import build_report_rows, create_xlsx

from . import reports_bp


def _report_dimensions(business_id):
    branches = []
    cost_centers = []
    if business_id:
        branches = Branch.query.filter_by(
            business_id=business_id,
        ).order_by(Branch.code).all()
        cost_centers = CostCenter.query.filter_by(
            business_id=business_id,
        ).order_by(CostCenter.code).all()
    branch_id = request.args.get('branch_id', type=int)
    cost_center_id = request.args.get('cost_center_id', type=int)
    if branch_id is not None and not any(branch.id == branch_id for branch in branches):
        abort(404)
    if cost_center_id is not None and not any(
        center.id == cost_center_id for center in cost_centers
    ):
        abort(404)
    return branches, cost_centers, branch_id, cost_center_id


def audit_report_access(report_type, action=None):
    """Record successful report views in the caller's transaction."""

    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            response = view(*args, **kwargs)
            from app.services.audit_service import record_user_action

            record_user_action(
                current_user.business_id,
                current_user.id,
                action or (
                    'REPORT_VIEW'
                    if request.method == 'GET'
                    else 'REPORT_ACTION'
                ),
                'reports',
                details={'report_type': report_type},
            )
            db.session.commit()
            return response

        return wrapped

    return decorate


@reports_bp.route('/reports')
@login_required
@audit_report_access('reports_home')
def reports():
    """Main reports page - shows income statement by default."""
    return redirect(url_for('reports.income_statement'))


@reports_bp.route('/reports/income-statement')
@login_required
@audit_report_access('income_statement')
def income_statement():
    """Income Statement report."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = None
    end_date = None
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        # Include the entire end day
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    
    # Get business_id from current user
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        pl_data = get_income_statement(business_id, start_date, end_date)
    else:
        pl_data = get_profit_loss(start_date, end_date)
    
    return render_template(
        'reports.html',
        report_type='income_statement',
        pl=pl_data,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@reports_bp.route('/reports/balance-sheet')
@login_required
@audit_report_access('balance_sheet')
def balance_sheet():
    """Balance Sheet report."""
    as_of_date_str = request.args.get('as_of_date')
    
    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        bs_data = get_balance_sheet(business_id, as_of_date)
    else:
        bs_data = {'total_assets': 0, 'assets': [], 'total_liabilities': 0, 'liabilities': [], 
                   'total_equity': 0, 'equity': [], 'is_balanced': True, 'difference': 0}
    
    return render_template(
        'reports.html',
        report_type='balance_sheet',
        bs=bs_data,
        as_of_date=as_of_date_str,
    )


@reports_bp.route('/reports/cash-flow')
@login_required
@audit_report_access('cash_flow')
def cash_flow():
    """Cash Flow Statement report."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = None
    end_date = None
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        cf_data = get_cash_flow(business_id, start_date, end_date)
    else:
        cf_data = {'operating': {'net_income': 0, 'adjustments': [], 'total': 0},
                   'investing': {'items': [], 'total': 0},
                   'financing': {'items': [], 'total': 0},
                   'net_cash': 0}
    
    return render_template(
        'reports.html',
        report_type='cash_flow',
        cf=cf_data,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@reports_bp.route('/reports/trial-balance')
@login_required
@audit_report_access('trial_balance')
def trial_balance():
    """Trial Balance report."""
    as_of_date_str = request.args.get('as_of_date')
    
    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    branches, cost_centers, branch_id, cost_center_id = _report_dimensions(business_id)
    
    if business_id:
        tb_data = get_trial_balance(
            business_id,
            as_of_date,
            branch_id=branch_id,
            cost_center_id=cost_center_id,
        )
    else:
        tb_data = {'entries': [], 'total_debits': 0, 'total_credits': 0, 'is_balanced': True, 'difference': 0}
    
    return render_template(
        'reports.html',
        report_type='trial_balance',
        tb=tb_data,
        as_of_date=as_of_date_str,
        branches=branches,
        cost_centers=cost_centers,
        branch_id=branch_id,
        cost_center_id=cost_center_id,
    )


@reports_bp.route('/reports/general-ledger')
@login_required
@audit_report_access('general_ledger')
def general_ledger():
    """General Ledger report."""
    account_id = request.args.get('account_id', type=int)
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
    branches, cost_centers, branch_id, cost_center_id = _report_dimensions(business_id)

    if business_id:
        gl_data = get_general_ledger(
            business_id,
            account_id,
            start_date,
            end_date,
            branch_id=branch_id,
            cost_center_id=cost_center_id,
        )
    else:
        gl_data = {'entries': [], 'accounts': [], 'selected_account': None}

    # Paginate entries
    from flask import request as flask_request
    per_page = min(max(per_page, 10), 100)
    total = len(gl_data.get('entries', []))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_entries = gl_data.get('entries', [])[start_idx:end_idx]
    gl_data['entries'] = paginated_entries
    gl_data['page'] = page
    gl_data['per_page'] = per_page
    gl_data['total'] = total
    gl_data['pages'] = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'reports.html',
        report_type='general_ledger',
        gl=gl_data,
        account_id=account_id,
        start_date=start_date_str,
        end_date=end_date_str,
        page=page,
        per_page=per_page,
        total=total,
        pages=gl_data['pages'],
        branches=branches,
        cost_centers=cost_centers,
        branch_id=branch_id,
        cost_center_id=cost_center_id,
    )


@reports_bp.route('/reports/cashbook')
@login_required
@audit_report_access('cashbook')
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
            'start_date': start_date, 'end_date': end_date,
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


@reports_bp.route('/reports/ar-aging')
@login_required
@audit_report_access('ar_aging')
def ar_aging():
    """AR Aging report."""
    as_of_date_str = request.args.get('as_of_date')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")

    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)

    if business_id:
        ar_data = get_ar_aging(business_id, as_of_date)
    else:
        ar_data = {'aging_data': [], 'totals': {'total_balance': 0, 'current': 0, 'days_30': 0, 'days_60': 0, 'days_90': 0}}

    per_page = min(max(per_page, 10), 100)
    total = len(ar_data.get('aging_data', []))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    ar_data['aging_data'] = ar_data.get('aging_data', [])[start_idx:end_idx]
    ar_data['page'] = page
    ar_data['per_page'] = per_page
    ar_data['total'] = total
    ar_data['pages'] = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'reports.html',
        report_type='ar_aging',
        ar=ar_data,
        as_of_date=as_of_date_str,
        page=page,
        per_page=per_page,
        total=total,
        pages=ar_data['pages'],
    )


@reports_bp.route('/reports/audit-log')
@login_required
@audit_report_access('audit_log')
def audit_log():
    """Audit Trail report."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    action = request.args.get('action')
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
        al_data = get_audit_log(business_id, start_date, end_date, action)
    else:
        al_data = {'entries': [], 'start_date': start_date, 'end_date': end_date, 'action': action}

    per_page = min(max(per_page, 10), 100)
    total = len(al_data.get('entries', []))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    al_data['entries'] = al_data.get('entries', [])[start_idx:end_idx]
    al_data['page'] = page
    al_data['per_page'] = per_page
    al_data['total'] = total
    al_data['pages'] = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'reports.html',
        report_type='audit_log',
        al=al_data,
        start_date=start_date_str,
        end_date=end_date_str,
        action=action,
        page=page,
        per_page=per_page,
        total=total,
        pages=al_data['pages'],
    )


@reports_bp.route('/reports/ap-aging')
@login_required
@audit_report_access('ap_aging')
def ap_aging():
    """AP Aging report."""
    as_of_date_str = request.args.get('as_of_date')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")

    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)

    if business_id:
        ap_data = get_ap_aging(business_id, as_of_date)
    else:
        ap_data = {'aging_data': [], 'totals': {'total_balance': 0, 'current': 0, 'days_30': 0, 'days_60': 0, 'days_90': 0}}

    per_page = min(max(per_page, 10), 100)
    total = len(ap_data.get('aging_data', []))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    ap_data['aging_data'] = ap_data.get('aging_data', [])[start_idx:end_idx]
    ap_data['page'] = page
    ap_data['per_page'] = per_page
    ap_data['total'] = total
    ap_data['pages'] = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'reports.html',
        report_type='ap_aging',
        ap=ap_data,
        as_of_date=as_of_date_str,
        page=page,
        per_page=per_page,
        total=total,
        pages=ap_data['pages'],
    )


def _budget_period(value):
    if not value:
        return date.today().replace(day=1)
    try:
        return datetime.strptime(value, '%Y-%m').date().replace(day=1)
    except ValueError as error:
        raise ValueError('Budget period must use YYYY-MM format.') from error

def _export_report_date(parameter, end_of_day=False):
    value = request.args.get(parameter)
    if not value:
        return None
    parsed = datetime.strptime(value, '%Y-%m-%d')
    if end_of_day:
        parsed += timedelta(days=1) - timedelta(seconds=1)
    return parsed


@reports_bp.route('/reports/<report_type>/export.xlsx')
@login_required
@audit_report_access('report_export', action='REPORT_EXPORT')
def export_report_xlsx(report_type):
    """Export an unpaginated, tenant-scoped financial report workbook."""
    business_id = current_user.business_id
    start_date = _export_report_date('start_date', end_of_day=False)
    end_date = _export_report_date('end_date', end_of_day=True)
    as_of_date = _export_report_date('as_of_date')

    if report_type == 'income-statement':
        report_key = 'income_statement'
        report = get_income_statement(business_id, start_date, end_date)
    elif report_type == 'balance-sheet':
        report_key = 'balance_sheet'
        report = get_balance_sheet(business_id, as_of_date)
    elif report_type == 'cash-flow':
        report_key = 'cash_flow'
        report = get_cash_flow(business_id, start_date, end_date)
    elif report_type == 'trial-balance':
        report_key = 'trial_balance'
        _, _, branch_id, cost_center_id = _report_dimensions(business_id)
        report = get_trial_balance(
            business_id,
            as_of_date,
            branch_id=branch_id,
            cost_center_id=cost_center_id,
        )
    elif report_type == 'general-ledger':
        report_key = 'general_ledger'
        _, _, branch_id, cost_center_id = _report_dimensions(business_id)
        report = get_general_ledger(
            business_id,
            request.args.get('account_id', type=int),
            start_date,
            end_date,
            branch_id=branch_id,
            cost_center_id=cost_center_id,
        )
    elif report_type == 'cashbook':
        report_key = 'cashbook'
        report = get_cashbook(business_id, start_date, end_date)
    elif report_type == 'ar-aging':
        report_key = 'ar_aging'
        report = get_ar_aging(business_id, as_of_date)
    elif report_type == 'ap-aging':
        report_key = 'ap_aging'
        report = get_ap_aging(business_id, as_of_date)
    elif report_type == 'audit-log':
        report_key = 'audit_log'
        report = get_audit_log(
            business_id,
            start_date,
            end_date,
            request.args.get('action'),
        )
    else:
        abort(404)

    rows = build_report_rows(report_key, report)
    filename = f'trackwise-{report_type}.xlsx'
    return send_file(
        create_xlsx(rows, sheet_name=report_type.replace('-', ' ').title()),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route('/reports/expense-budget-variance', methods=['GET', 'POST'])
@login_required
@audit_report_access('expense_budget_variance')
def expense_budget_variance():
    """Manage monthly expense budgets and compare them with posted actuals."""
    period_value = (
        request.form.get('period', '')
        if request.method == 'POST'
        else request.args.get('period', '')
    )
    try:
        period_start = _budget_period(period_value)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('reports.expense_budget_variance'))

    if request.method == 'POST':
        account_id = request.form.get('account_id', type=int)
        amount_value = request.form.get('amount', '').strip()
        if account_id is None:
            flash('Select an expense account.', 'danger')
        else:
            try:
                amount = Decimal(amount_value)
                set_expense_budget(
                    current_user.business_id,
                    account_id,
                    period_start,
                    amount,
                    created_by=current_user.id,
                )
            except (InvalidOperation, ValueError) as error:
                flash(str(error) or 'Enter a valid budget amount.', 'danger')
            else:
                flash('Expense budget saved.', 'success')
        return redirect(url_for(
            'reports.expense_budget_variance',
            period=period_start.strftime('%Y-%m'),
        ))

    variance = get_expense_budget_variance(current_user.business_id, period_start)
    return render_template(
        'reports.html',
        report_type='expense_budget_variance',
        budget_variance=variance,
        period=period_start.strftime('%Y-%m'),
    )


@reports_bp.route('/reports/expense-budget-variance/export.xlsx')
@login_required
@audit_report_access('expense_budget_variance_export', action='REPORT_EXPORT')
def export_expense_budget_variance():
    period_start = _budget_period(request.args.get('period', ''))
    variance = get_expense_budget_variance(current_user.business_id, period_start)
    rows = [[
        'Account Code',
        'Expense Account',
        'Budget',
        'Actual',
        'Variance (Budget - Actual)',
        'Budget Used (%)',
    ]]
    rows.extend(
        [
            row['account'].code,
            row['account'].name,
            row['budget'],
            row['actual'],
            row['variance'],
            row['percent_used'] if row['percent_used'] is not None else '',
        ]
        for row in variance['rows']
    )
    rows.append([
        '',
        'Total',
        variance['total_budget'],
        variance['total_actual'],
        variance['total_variance'],
        '',
    ])
    return send_file(
        create_xlsx(rows),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'expense-budget-variance-{period_start:%Y-%m}.xlsx',
    )