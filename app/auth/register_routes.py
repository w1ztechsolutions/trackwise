from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.models import db as _db

from . import auth_bp

db = _db


def _seed_accounting_data(business_id):
    """Seed default chart of accounts for a new business."""
    from app.models.accounting import ChartOfAccounts

    default_accounts = [
        ('1000', 'Cash', 'asset'),
        ('1100', 'Bank', 'asset'),
        ('1200', 'Accounts Receivable', 'asset'),
        ('1400', 'Inventory', 'asset'),
        ('1410', 'Raw Materials', 'asset'),
        ('1450', 'Work in Progress', 'asset'),
        ('1460', 'Finished Goods', 'asset'),
        ('1500', 'Fixed Assets', 'asset'),
        ('2100', 'Accounts Payable', 'liability'),
        ('2200', 'Tax Payable', 'liability'),
        ('3000', 'Capital', 'equity'),
        ('3100', 'Retained Earnings', 'equity'),
        ('4000', 'Sales Revenue', 'income'),
        ('4100', 'Other Income', 'income'),
        ('5000', 'Cost of Goods Sold', 'expense'),
        ('5100', 'Rent Expense', 'expense'),
        ('5200', 'Utilities Expense', 'expense'),
        ('5300', 'Salaries Expense', 'expense'),
        ('5400', 'Marketing Expense', 'expense'),
        ('5900', 'Other Expenses', 'expense'),
    ]

    for code, name, type_ in default_accounts:
        db.session.add(ChartOfAccounts(
            business_id=business_id,
            code=code,
            name=name,
            type=type_,
            is_active=True,
        ))

    # Seed default settings
    from models import Setting
    db.session.add(Setting(business_id=business_id, key='tax_rate', value='30.0'))
    db.session.commit()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Local import to avoid circular imports
    from app.models import User
    from app.models.accounting import Business

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        tax_id = request.form.get('tax_id', '').strip() or None
        currency = request.form.get('currency', 'MWK').strip().upper()

        if not business_name or not email or not password:
            flash('Business name, email and password are required.', 'danger')
            return render_template('register.html', show_nav=False)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', show_nav=False)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html', show_nav=False)

        # Create Business first
        business = Business(name=business_name, tax_id=tax_id, currency=currency)
        db.session.add(business)
        db.session.flush()

        # Seed chart of accounts for the new business
        _seed_accounting_data(business.id)

        # Create admin user with business_id
        user = User(
            business_id=business.id,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        # Subscribe to Free plan by default
        try:
            from app.services.subscription_service import seed_default_plans, subscribe
            seed_default_plans()
            free_plan = __import__('models', fromlist=['Plan']).Plan.query.filter_by(name='Free').first()
            if free_plan:
                subscribe(business.id, free_plan.id)
        except Exception:
            pass  # Non-critical - subscription can be set up later

        flash('Account created successfully. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', show_nav=False)