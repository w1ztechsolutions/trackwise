from datetime import datetime, timedelta

from flask import render_template, request

from models import Product
from services.fifo_service import get_inventory_valuation, get_profit_loss

from . import reports_bp


@reports_bp.route('/reports')
def reports():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = None
    end_date = None

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        # Include the entire end day
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)

    pl_data = get_profit_loss(start_date, end_date)
    valuation_data = get_inventory_valuation()

    expense_cats = list(pl_data['expense_by_category'].keys())
    expense_vals = list(pl_data['expense_by_category'].values())

    return render_template(
        'reports.html',
        pl=pl_data,
        total_valuation=valuation_data['total_valuation'],
        start_date=start_date_str,
        end_date=end_date_str,
        expense_cats=expense_cats,
        expense_vals=expense_vals
    )

