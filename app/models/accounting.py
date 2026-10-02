from datetime import datetime, timezone

from models import db


class Business(db.Model):
    __tablename__ = 'businesses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    tax_id = db.Column(db.String(100), nullable=True)
    currency = db.Column(db.String(10), nullable=False, default='MWK')
    fiscal_year_start = db.Column(db.String(5), nullable=True, default='01-01')
    last_closed_period_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_superadmin_id = db.Column(db.Integer, db.ForeignKey('super_admins.id'), nullable=True)


class DemoWorkspace(db.Model):
    __tablename__ = 'demo_workspaces'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    normalized_name = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ChartOfAccounts(db.Model):
    __tablename__ = 'chart_of_accounts'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('business_id', 'code', name='uq_business_account_code'),
    )


class Branch(db.Model):
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint('business_id', 'code', name='uq_business_branch_code'),
    )


class CostCenter(db.Model):
    __tablename__ = 'cost_centers'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint('business_id', 'code', name='uq_business_cost_center_code'),
    )


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True, index=True)
    entry_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    reversed_by_entry_id = db.Column(
        db.Integer,
        db.ForeignKey('journal_entries.id', ondelete='SET NULL'),
        nullable=True,
        unique=True,
    )
    reversal_reason = db.Column(db.String(255), nullable=True)

    lines = db.relationship('JournalLine', backref='journal_entry', cascade='all, delete-orphan')
    branch = db.relationship('Branch', backref='journal_entries')
    reversal_entry = db.relationship(
        'JournalEntry',
        remote_side=[id],
        foreign_keys=[reversed_by_entry_id],
        uselist=False,
    )


class JournalLine(db.Model):
    __tablename__ = 'journal_lines'

    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=False)
    cost_center_id = db.Column(
        db.Integer,
        db.ForeignKey('cost_centers.id'),
        nullable=True,
        index=True,
    )
    debit_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    credit_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)

    account = db.relationship('ChartOfAccounts', backref='journal_lines')
    cost_center = db.relationship('CostCenter', backref='journal_lines')


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_name = db.Column(db.String(120), nullable=True)
    actor_email = db.Column(db.String(120), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.Integer, nullable=True)
    old_values = db.Column(db.Text, nullable=True)
    new_values = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class ImportRun(db.Model):
    """Lifecycle record for one spreadsheet import (ADR-0013)."""

    __tablename__ = 'import_runs'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_name = db.Column(db.String(120), nullable=True)
    actor_email = db.Column(db.String(120), nullable=True)
    entity = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='staged')
    column_map = db.Column(db.Text, nullable=True)
    date_order = db.Column(db.String(3), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=True)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    imported_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.Text, nullable=True)
    staged_rows = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index('ix_import_runs_business_status', 'business_id', 'status'),
    )


class BankStatement(db.Model):
    __tablename__ = 'bank_statements'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=False)
    statement_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reference = db.Column(db.String(100), nullable=True)
    is_reconciled = db.Column(db.Boolean, nullable=False, default=False)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    account = db.relationship('ChartOfAccounts', backref='bank_statements')
    journal_entry = db.relationship('JournalEntry', backref='bank_statement_matches')


class BankReconciliationPeriod(db.Model):
    """Lock records for bank reconciliation periods (per account, per period).

    Once a reconciliation period is locked for a bank account, no further
    matching or unmatching of statements in that period is allowed.
    """
    __tablename__ = 'bank_reconciliation_periods'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    account_id = db.Column(
        db.Integer,
        db.ForeignKey('chart_of_accounts.id'),
        nullable=False,
    )
    period_end = db.Column(db.Date, nullable=False)
    closed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    closed_at = db.Column(db.DateTime, nullable=True)
    reopened_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    reopened_at = db.Column(db.DateTime, nullable=True)
    is_locked = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint(
            'business_id', 'account_id', 'period_end',
            name='uq_bank_recon_periods_business_account_period'
        ),
        db.Index('ix_bank_recon_periods_business_id', 'business_id'),
        db.Index('ix_bank_recon_periods_account_id', 'account_id'),
        db.Index('ix_bank_recon_periods_is_locked', 'is_locked'),
    )

    account = db.relationship('ChartOfAccounts', backref='reconciliation_periods')
    closed_by_user = db.relationship('User', foreign_keys=[closed_by])
    reopened_by_user = db.relationship('User', foreign_keys=[reopened_by])


class RevenueRecognitionSchedule(db.Model):
    __tablename__ = 'revenue_recognition_schedules'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, unique=True)
    revenue_account_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=False)
    deferred_revenue_account_id = db.Column(db.Integer, db.ForeignKey('chart_of_accounts.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)
    recognized_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    last_recognized_through = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    invoice = db.relationship('Invoice')
    revenue_account = db.relationship('ChartOfAccounts', foreign_keys=[revenue_account_id])
    deferred_revenue_account = db.relationship(
        'ChartOfAccounts',
        foreign_keys=[deferred_revenue_account_id],
    )


class ExpenseBudget(db.Model):
    __tablename__ = 'expense_budgets'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    account_id = db.Column(
        db.Integer,
        db.ForeignKey('chart_of_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    period_start = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint(
            'business_id',
            'account_id',
            'period_start',
            name='uq_expense_budget_business_account_period',
        ),
    )

    account = db.relationship('ChartOfAccounts')


BUDGET_TYPES = ('revenue', 'expense')
BUDGET_STATUSES = ('draft', 'approved', 'archived')


class Budget(db.Model):
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(200), nullable=False)
    budget_type = db.Column(db.String(20), nullable=False, default='expense')
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft')
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    lines = db.relationship(
        'BudgetLineItem',
        backref='budget',
        cascade='all, delete-orphan',
        order_by='BudgetLineItem.id',
    )

    __table_args__ = (
        db.CheckConstraint(
            "budget_type IN ('revenue', 'expense')",
            name='ck_budget_type',
        ),
        db.CheckConstraint(
            "status IN ('draft', 'approved', 'archived')",
            name='ck_budget_status',
        ),
        db.CheckConstraint('period_end >= period_start', name='ck_budget_period'),
    )


class BudgetLineItem(db.Model):
    __tablename__ = 'budget_line_items'

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(
        db.Integer,
        db.ForeignKey('budgets.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    account_id = db.Column(
        db.Integer,
        db.ForeignKey('chart_of_accounts.id', ondelete='CASCADE'),
        nullable=False,
    )
    cost_center_id = db.Column(
        db.Integer,
        db.ForeignKey('cost_centers.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    account = db.relationship('ChartOfAccounts')
    cost_center = db.relationship('CostCenter')

    __table_args__ = (
        db.UniqueConstraint(
            'budget_id',
            'account_id',
            'cost_center_id',
            name='uq_budget_line_account_cost_center',
        ),
        db.CheckConstraint('amount >= 0', name='ck_budget_line_amount'),
    )


class PurchaseReturn(db.Model):
    __tablename__ = 'purchase_returns'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey('businesses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id', ondelete='SET NULL'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    return_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    return_type = db.Column(db.String(20), nullable=False, default='credit_note')
    is_applied_to_ap = db.Column(db.Boolean, nullable=False, default=True)
    journal_entry_id = db.Column(
        db.Integer,
        db.ForeignKey('journal_entries.id', ondelete='SET NULL'),
        nullable=True,
    )
    is_reversed = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    bill = db.relationship('Bill', backref='purchase_returns')
    supplier = db.relationship('Supplier', backref='purchase_returns')
    journal_entry = db.relationship('JournalEntry', backref='purchase_return_entries')

    __table_args__ = (
        db.CheckConstraint(
            "return_type IN ('credit_note', 'refund')",
            name='ck_purchase_return_type',
        ),
        db.CheckConstraint('amount > 0', name='ck_purchase_return_amount'),
    )
