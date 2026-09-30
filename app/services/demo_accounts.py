"""Create isolated workspaces and randomly credentialed demo users."""

import secrets
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app.models import Business, ChartOfAccounts, DemoWorkspace, User, db


DEMO_ROLES = (
    ("admin", "Administrator"),
    ("manager", "Manager"),
    ("accountant", "Accountant"),
    ("cashier", "Cashier"),
    ("storekeeper", "Storekeeper"),
    ("viewer", "Viewer"),
)

DEMO_ACCOUNTS = (
    ("1000", "Cash", "asset"),
    ("1100", "Bank", "asset"),
    ("1200", "Accounts Receivable", "asset"),
    ("1400", "Inventory", "asset"),
    ("1500", "Fixed Assets", "asset"),
    ("2100", "Accounts Payable", "liability"),
    ("2200", "Tax Payable", "liability"),
    ("2300", "Deferred Revenue", "liability"),
    ("3000", "Capital", "equity"),
    ("3100", "Retained Earnings", "equity"),
    ("4000", "Sales Revenue", "income"),
    ("4100", "Other Income", "income"),
    ("5000", "Cost of Goods Sold", "expense"),
    ("5100", "Rent Expense", "expense"),
    ("5200", "Utilities Expense", "expense"),
    ("5300", "Salaries Expense", "expense"),
    ("5400", "Marketing Expense", "expense"),
    ("5900", "Other Expenses", "expense"),
)


def normalize_business_name(name):
    """Trim and collapse whitespace, then case-fold for duplicate detection."""
    display_name = " ".join(name.split())
    return display_name, display_name.casefold()


def find_demo_workspace(normalized_name):
    return DemoWorkspace.query.filter_by(normalized_name=normalized_name).one_or_none()


def create_demo_user(business_id, role):
    title = dict(DEMO_ROLES)[role]
    user = User(
        business_id=business_id,
        email=f"demo-{uuid4().hex}@trackwise.invalid",
        name=f"Demo {title}",
        password_hash=generate_password_hash(secrets.token_urlsafe(48)),
        role=role,
        is_active=True,
        must_change_password=False,
    )
    db.session.add(user)
    db.session.flush()
    return user


def create_demo_workspace(display_name, normalized_name, role):
    """Create the business, starter ledger accounts, and first selected-role user."""
    business = Business(name=display_name, currency="MWK")
    db.session.add(business)
    db.session.flush()
    workspace = DemoWorkspace(
        business_id=business.id,
        normalized_name=normalized_name,
    )
    db.session.add(workspace)

    for code, name, account_type in DEMO_ACCOUNTS:
        db.session.add(ChartOfAccounts(
            business_id=business.id,
            code=code,
            name=name,
            type=account_type,
            is_active=True,
        ))

    user = create_demo_user(business.id, role)
    db.session.commit()
    return business, user
