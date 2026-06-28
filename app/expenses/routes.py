from datetime import datetime
from flask_login import login_required, current_user
from flask import flash, redirect, render_template, request, url_for

from models import Expense
from services.fifo_service import record_expense

from . import expenses_bp


@expenses_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        category = request.form.get('category').strip()
        description = request.form.get('description', '').strip()
        amount = float(request.form.get('amount', 0.0))
        expense_date_str = request.form.get('expense_date')

        expense_date = None
        if expense_date_str:
            expense_date = datetime.fromisoformat(expense_date_str)

        if not category or amount <= 0:
            flash('Category and positive Amount are required!', 'danger')
            return redirect(url_for('expenses.expenses'))

        try:
            record_expense(expense_date, category, description, amount, current_user.business_id, current_user.id)
            flash('Operating expense recorded successfully!', 'success')
        except Exception as e:
            flash(f'Error recording expense: {str(e)}', 'danger')

        return redirect(url_for('expenses.expenses'))

    page = request.args.get('page', 1, type=int)
    expense_records = Expense.query.order_by(Expense.expense_date.desc()).paginate(page=page, per_page=10)
    categories = ['Rent', 'Utilities', 'Salaries', 'Marketing', 'Logistics', 'Tax', 'Supplies', 'Other']
    return render_template('expenses.html', expenses=expense_records, categories=categories)

