"""Report routes for TrackWise."""

from datetime import datetime, timedelta
from flask_login import login_required
from flask import render_template, request, redirect, url_for, flash, Response

from models import Product, Setting
from services.fifo_service import get_inventory_valuation, get_profit_loss
from app.services.reports import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_trial_balance,
    get_general_ledger,
    get_ar_aging,
    get_ap_aging,
)

from . import reports_bp


@reports_bp.route('/reports')
@login_required
def reports():
    """Main reports page - shows income statement by default."""
    return redirect(url_for('reports.income_statement'))


@reports_bp.route('/reports/income-statement')
@login_required
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
def trial_balance():
    """Trial Balance report."""
    as_of_date_str = request.args.get('as_of_date')
    
    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        tb_data = get_trial_balance(business_id, as_of_date)
    else:
        tb_data = {'entries': [], 'total_debits': 0, 'total_credits': 0, 'is_balanced': True, 'difference': 0}
    
    return render_template(
        'reports.html',
        report_type='trial_balance',
        tb=tb_data,
        as_of_date=as_of_date_str,
    )


@reports_bp.route('/reports/general-ledger')
@login_required
def general_ledger():
    """General Ledger report."""
    account_id = request.args.get('account_id', type=int)
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
        gl_data = get_general_ledger(business_id, account_id, start_date, end_date)
    else:
        gl_data = {'entries': [], 'accounts': [], 'selected_account': None}
    
    return render_template(
        'reports.html',
        report_type='general_ledger',
        gl=gl_data,
        account_id=account_id,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@reports_bp.route('/reports/ar-aging')
@login_required
def ar_aging():
    """AR Aging report."""
    as_of_date_str = request.args.get('as_of_date')
    
    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        ar_data = get_ar_aging(business_id, as_of_date)
    else:
        ar_data = {'aging_data': [], 'totals': {'total_balance': 0, 'current': 0, 'days_30': 0, 'days_60': 0, 'days_90': 0}}
    
    return render_template(
        'reports.html',
        report_type='ar_aging',
        ar=ar_data,
        as_of_date=as_of_date_str,
    )


@reports_bp.route('/reports/ap-aging')
@login_required
def ap_aging():
    """AP Aging report."""
    as_of_date_str = request.args.get('as_of_date')
    
    as_of_date = None
    if as_of_date_str:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    
    from flask_login import current_user
    business_id = getattr(current_user, 'business_id', None)
    
    if business_id:
        ap_data = get_ap_aging(business_id, as_of_date)
    else:
        ap_data = {'aging_data': [], 'totals': {'total_balance': 0, 'current': 0, 'days_30': 0, 'days_60': 0, 'days_90': 0}}
    
    return render_template(
        'reports.html',
        report_type='ap_aging',
        ap=ap_data,
        as_of_date=as_of_date_str,
    )