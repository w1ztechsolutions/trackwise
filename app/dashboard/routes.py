from datetime import datetime

from flask import redirect, render_template, url_for

from models import Product, Purchase, Sale, Expense
from services.fifo_service import get_profit_loss, get_inventory_valuation

from . import dashboard_bp


@dashboard_bp.route('/')
def index():
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/dashboard')
def dashboard():
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1)

    # Compute end of current month
    if today.month == 12:
        end_of_month = datetime(today.year + 1, 1, 1)
    else:
        end_of_month = datetime(today.year, today.month + 1, 1)

    pl_stats = get_profit_loss()  # All-time stats for the dashboard overview
    month_stats = get_profit_loss(start_date=start_of_month, end_date=end_of_month)
    val_stats = get_inventory_valuation()

    low_stock_products = Product.query.filter(
        Product.quantity_in_stock <= Product.low_stock_threshold
    ).all()

    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    recent_purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.expense_date.desc()).limit(5).all()

    chart_labels = []
    chart_sales = []
    chart_expenses = []

    def month_bounds(base_dt, offset_months):
        year = base_dt.year + (base_dt.month - 1 + offset_months) // 12
        month = (base_dt.month - 1 + offset_months) % 12 + 1
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        return start, end

    for offset in range(-5, 1):
        m_start, m_end = month_bounds(today, offset)
        m_pl = get_profit_loss(start_date=m_start, end_date=m_end)
        chart_labels.append(m_start.strftime("%b %Y"))
        chart_sales.append(m_pl['total_sales'])
        chart_expenses.append(m_pl['total_expenses'])

    return render_template(
        'dashboard.html',
        pl=pl_stats,
        month_pl=month_stats,
        valuation=val_stats['total_valuation'],
        low_stock=low_stock_products,
        recent_sales=recent_sales,
        recent_purchases=recent_purchases,
        recent_expenses=recent_expenses,
        chart_labels=chart_labels,
        chart_sales=chart_sales,
        chart_expenses=chart_expenses
    )

