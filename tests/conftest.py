import pytest
from flask import Flask
from app import create_app
from config import TestingConfig
from models import db, User
from app.models.accounting import Business, ChartOfAccounts


def seed_test_business():
    """Seed a test business and default chart of accounts."""
    business = Business(name='Test Business', currency='MWK')
    db.session.add(business)
    db.session.flush()

    default_accounts = [
        ('1000', 'Cash', 'asset'),
        ('1100', 'Bank', 'asset'),
        ('1200', 'Accounts Receivable', 'asset'),
        ('1400', 'Inventory', 'asset'),
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
            business_id=business.id,
            code=code,
            name=name,
            type=type_,
            is_active=True,
        ))

    # Create a test user
    user = User(
        business_id=business.id,
        email='test@example.com',
        password_hash='pbkdf2:sha256:600000$dummy',
        role='admin',
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return business, user


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_test_business()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()