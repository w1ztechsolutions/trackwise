from datetime import date, datetime
from flask_login import login_required
from flask import redirect, render_template, url_for

from app.models import Product, Purchase, Sale, Expense, Payment
from app.services.budget_service import get_dashboard_budget_summary
from app.services.reports import get_expense_budget_variance
from services.fifo_service import get_profit_loss, get_inventory_valuation

from . import dashboard_bp


def month_bounds(base_dt, offset_months):
    year = base_dt.year + (base_dt.month - 1 + offset_months) // 12
    month = (base_dt.month - 1 + offset_months) % 12 + 1
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


@dashboard_bp.route('/')
def index():
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    from flask_login import current_user
    biz_id = getattr(current_user, 'business_id', None)
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1)

    # Compute end of current month
    if today.month == 12:
        end_of_month = datetime(today.year + 1, 1, 1)
    else:
        end_of_month = datetime(today.year, today.month + 1, 1)

    pl_stats = get_profit_loss(business_id=biz_id)  # All-time stats for the dashboard overview
    month_stats = get_profit_loss(start_date=start_of_month, end_date=end_of_month, business_id=biz_id)
    prev_start, prev_end = month_bounds(today, -1)
    prev_month_pl = get_profit_loss(start_date=prev_start, end_date=prev_end, business_id=biz_id)
    val_stats = get_inventory_valuation(business_id=biz_id)

    low_stock_products = Product.query.filter(
        Product.business_id == biz_id,
        Product.quantity_in_stock <= Product.low_stock_threshold,
    ).all()

    recent_sales = Sale.query.filter_by(business_id=biz_id).order_by(Sale.sale_date.desc()).limit(5).all()
    recent_purchases = Purchase.query.filter_by(business_id=biz_id).order_by(Purchase.purchase_date.desc()).limit(5).all()
    recent_expenses = Expense.query.filter_by(business_id=biz_id).order_by(Expense.expense_date.desc()).limit(5).all()
    recent_payments = Payment.query.filter_by(business_id=biz_id).order_by(Payment.payment_date.desc()).limit(5).all()

    chart_labels = []
    chart_sales = []
    chart_expenses = []

    for offset in range(-5, 1):
        m_start, m_end = month_bounds(today, offset)
        m_pl = get_profit_loss(start_date=m_start, end_date=m_end, business_id=biz_id)
        chart_labels.append(m_start.strftime("%b %Y"))
        chart_sales.append(m_pl['total_sales'])
        chart_expenses.append(m_pl['total_expenses'])

    budget_summary = get_dashboard_budget_summary(biz_id, start_of_month.date())
    budget_labels = []
    budget_values = []
    budget_actual_values = []
    for row in budget_summary['rows']:
        if row['budget'] <= 0:
            continue
        budget_labels.append(row['period_start'].strftime('%b %Y'))
        budget_values.append(float(row['budget']))
        budget_actual_values.append(float(row['actual']))

    current_variance = get_expense_budget_variance(biz_id, start_of_month.date())
    account_labels = []
    account_budget = []
    account_actual = []
    for row in current_variance['rows']:
        if row['budget'] <= 0:
            continue
        account_labels.append(f"{row['account'].code} {row['account'].name}")
        account_budget.append(float(row['budget']))
        account_actual.append(float(row['actual']))

    return render_template(
        'dashboard.html',
        pl=pl_stats,
        month_pl=month_stats,
        prev_month_pl=prev_month_pl,
        valuation=val_stats['total_valuation'],
        low_stock=low_stock_products,
        recent_sales=recent_sales,
        recent_purchases=recent_purchases,
        recent_expenses=recent_expenses,
        recent_payments=recent_payments,
        chart_labels=chart_labels,
        chart_sales=chart_sales,
        chart_expenses=chart_expenses,
        chart_budget_labels=budget_labels,
        chart_budget=budget_values,
        chart_budget_actual=budget_actual_values,
        chart_budget_utilization=budget_summary['utilization'],
        chart_account_labels=account_labels,
        chart_account_budget=account_budget,
        chart_account_actual=account_actual,
    )

