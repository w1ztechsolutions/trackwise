from datetime import datetime

from flask import flash, redirect, render_template, request, url_for

from models import Expense
from services.fifo_service import record_expense

from . import expenses_bp


@expenses_bp.route('/expenses', methods=['GET', 'POST'])
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
            record_expense(expense_date, category, description, amount)
            flash('Operating expense recorded successfully!', 'success')
        except Exception as e:
            flash(f'Error recording expense: {str(e)}', 'danger')

        return redirect(url_for('expenses.expenses'))

    expense_records = Expense.query.order_by(Expense.expense_date.desc()).all()
    categories = ['Rent', 'Utilities', 'Salaries', 'Marketing', 'Logistics', 'Tax', 'Supplies', 'Other']
    return render_template('expenses.html', expenses=expense_records, categories=categories)

