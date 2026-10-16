import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# REVIEW: Custom SQLAlchemy handle that automatically binds audit listeners to all sessions.
# REVIEW: Guarantees that model mutations across all HTTP requests and background tasks generate AuditLog entries.
class AuditedSQLAlchemy(SQLAlchemy):
    """SQLAlchemy handle whose sessions are always audited.

    The audit listeners are attached to the scoped session this handle owns rather
    than to ``sqlalchemy.orm.Session`` itself, so they no longer apply to every
    session in the process. Installing them here means every application that
    initializes the shared handle is audited, including the app factory.
    """

    def init_app(self, app):
        super().init_app(app)
        from app.services.audit_service import install_audit_listeners

        install_audit_listeners(self.session)


db = AuditedSQLAlchemy()

# REVIEW: Core inventory master record. Multi-tenant isolated via business_id FK.
# REVIEW: quantity_in_stock represents current available units, updated via FIFO purchase/sale operations.
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    quantity_in_stock = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    default_selling_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    unit_of_measure = db.Column(db.String(50), nullable=True)
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'name': self.name,
            'description': self.description or '',
            'quantity_in_stock': self.quantity_in_stock,
            'low_stock_threshold': self.low_stock_threshold,
            'default_selling_price': float(self.default_selling_price),
            'warehouse_id': self.warehouse_id,
            'category': self.category,
            'unit_of_measure': self.unit_of_measure,
            'barcode': self.barcode,
            'is_active': self.is_active,
        }


# REVIEW: Inventory purchase transaction header representing incoming inventory from suppliers.
# REVIEW: Associated items are automatically removed via cascade delete-orphan when the purchase is deleted.
class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    purchase_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    supplier = db.Column(db.String(200))
    notes = db.Column(db.Text)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    items = db.relationship('PurchaseItem', backref='purchase', cascade='all, delete-orphan')


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    product = db.relationship('Product', backref='purchase_items')


# REVIEW: Point-of-sale or invoice transaction header recording revenue and cost of goods sold (COGS).
# REVIEW: Tracks total_revenue and total_cogs simultaneously for instant gross profit margin analysis.
class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    sale_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    customer_name = db.Column(db.String(200))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    total_revenue = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    total_cogs = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')
    invoice = db.relationship('Invoice', backref='sales')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    cogs = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    product = db.relationship('Product', backref='sale_items')


# REVIEW: Direct operating expense voucher. Categorized by operational expense type
# REVIEW: and mapped to corresponding General Ledger expense accounts (5100-5900) during posting.
class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    expense_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(12, 2), nullable=False)


# REVIEW: Tenant configuration table. Unique constraint uq_business_setting_key enforces
# REVIEW: strict key uniqueness per business tenant, preventing setting collisions.
class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('business_id', 'key', name='uq_business_setting_key'),
    )


# REVIEW: FIFO inventory ledger record. Tracks cost layers and remaining_quantity for each batch.
# REVIEW: Depleted chronologically during sales to enforce First-In, First-Out costing rules.
class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    remaining_quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    transaction_type = db.Column(db.String(30), nullable=False, default='PURCHASE')
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    product = db.relationship('Product', backref='stock_transactions')


# REVIEW: Physical storage location master. Allows multi-warehouse inventory segregation and transfer tracking.
class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship('Product', backref='warehouse', lazy='select')


# REVIEW: Internal stock transfer or adjustment voucher moving inventory between warehouses
# REVIEW: or adjusting stock levels for shrinkage, damage, or audit reconciliation.
class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True)
    from_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True)
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True)
    type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    product = db.relationship('Product', backref='stock_movements')
    warehouse = db.relationship('Warehouse', backref='stock_movements_destination', foreign_keys=[warehouse_id])
    from_warehouse = db.relationship('Warehouse', backref='stock_movements_source', foreign_keys=[from_warehouse_id])
    to_warehouse = db.relationship('Warehouse', backref='stock_movements_target', foreign_keys=[to_warehouse_id])
    creator = db.relationship('User', backref='created_stock_movements')


# REVIEW: Accounts Receivable customer record. Maintains credit limits and opening balances
# REVIEW: for debt tracking and aging analysis.
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.String(20), unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    bank_name = db.Column(db.String(200), nullable=True)
    bank_branch = db.Column(db.String(200), nullable=True)
    bank_account_number = db.Column(db.String(50), nullable=True)
    credit_limit = db.Column(db.Numeric(14, 2), nullable=True)
    opening_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# REVIEW: Accounts Payable vendor/supplier record. Stores banking details and credit terms
# REVIEW: for payables reconciliation.
class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id = db.Column(db.String(20), unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    bank_name = db.Column(db.String(200), nullable=True)
    bank_branch = db.Column(db.String(200), nullable=True)
    bank_account_number = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    opening_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# REVIEW: Accounts Receivable invoice model tracking billing status (draft, sent, paid, void).
# REVIEW: Drives revenue recognition, customer statements, and AR aging reports.
class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    invoice_number = db.Column(db.String(60), nullable=True)
    invoice_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    due_date = db.Column(db.DateTime, nullable=True)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default='draft')
    notes = db.Column(db.Text, nullable=True)

    customer = db.relationship('Customer', backref='invoices')


# REVIEW: Invoice line item storing net amount, tax code reference, and unit pricing.
class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    line_total = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_code_id = db.Column(db.Integer, db.ForeignKey('tax_codes.id'), nullable=True)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0.0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_inclusive = db.Column(db.Boolean, nullable=False, default=False)

    invoice = db.relationship('Invoice', backref='items')
    tax_code = db.relationship('TaxCode', backref='invoice_items')
    product = db.relationship('Product', backref='invoice_items')


# REVIEW: Customer payment receipt voucher linked to invoices. Triggers AR control account credit.
class Receipt(db.Model):
    __tablename__ = 'receipts'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    receipt_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False, default='cash')
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    customer = db.relationship('Customer', backref='receipts')
    invoice = db.relationship('Invoice', backref='receipts')


# REVIEW: Accounts Payable vendor bill model tracking payables due dates and payment status.
class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    bill_number = db.Column(db.String(60), nullable=True)
    bill_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    due_date = db.Column(db.DateTime, nullable=True)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default='draft')
    notes = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier', backref='bills')


# REVIEW: Vendor bill line item detail recording cost expense/inventory allocations.
class BillItem(db.Model):
    __tablename__ = 'bill_items'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    line_total = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_code_id = db.Column(db.Integer, db.ForeignKey('tax_codes.id'), nullable=True)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0.0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    tax_inclusive = db.Column(db.Boolean, nullable=False, default=False)

    bill = db.relationship('Bill', backref='items')
    tax_code = db.relationship('TaxCode', backref='bill_items')
    product = db.relationship('Product', backref='bill_items')


# REVIEW: Supplier/vendor payment voucher linked to bills or direct expenses. Triggers AP control account debit.
class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('financial_categories.id'), nullable=True)
    line_item_id = db.Column(db.Integer, db.ForeignKey('line_items.id'), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    payee_type = db.Column(db.String(20), nullable=False, default='supplier')  # 'supplier' or 'staff'
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    payment_mode = db.Column(db.String(30), nullable=False, default='cash')
    reference = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | approved | rejected
    is_reversed = db.Column(db.Boolean, nullable=False, default=False)
    reversal_reason = db.Column(db.String(255), nullable=True)
    reversal_date = db.Column(db.DateTime, nullable=True)

    supplier = db.relationship('Supplier', backref='payments')
    bill = db.relationship('Bill', backref='payments')
    category = db.relationship('FinancialCategory', backref='payments', lazy='select')
    line_item = db.relationship('LineItem', backref='payments', lazy='select')


# REVIEW: User account model supporting Flask-Login session management and RBAC permissions.
# REVIEW: Scoped to business_id for tenant isolation.
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    custom_tasks = db.Column(db.Text, nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


# REVIEW: Manufacturing batch header tracking assembly of raw materials into finished goods.
class ProductionBatch(db.Model):
    __tablename__ = 'production_batches'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    batch_number = db.Column(db.String(60), nullable=False, unique=True)
    production_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_produced = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default='planned')
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    product = db.relationship('Product', backref='production_batches')
    material_usages = db.relationship('MaterialUsage', backref='production_batch', cascade='all, delete-orphan')
    outputs = db.relationship('FinishedGoodOutput', backref='production_batch', cascade='all, delete-orphan')


# REVIEW: Raw material inputs consumed during a production batch run.
class MaterialUsage(db.Model):
    __tablename__ = 'material_usages'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    production_batch_id = db.Column(db.Integer, db.ForeignKey('production_batches.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_consumed = db.Column(db.Integer, nullable=False, default=0)
    unit_cost_at_consumption = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)

    product = db.relationship('Product', backref='material_usages')


# REVIEW: Finished goods yielded from a production batch run, capitalized into inventory.
class FinishedGoodOutput(db.Model):
    __tablename__ = 'finished_good_outputs'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    production_batch_id = db.Column(db.Integer, db.ForeignKey('production_batches.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)

    product = db.relationship('Product', backref='finished_good_outputs')


# Plan model for subscription plans
# REVIEW: SaaS subscription plan definition specifying seat limits and feature capabilities.
class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    max_users = db.Column(db.Integer, nullable=False, default=1)
    features = db.Column(db.Text, nullable=True)  # JSON string
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# Subscription model for business subscriptions
# REVIEW: Tenant subscription status tracking recurring billing state and renewal terms.
class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='active')
    start_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    renewal_date = db.Column(db.DateTime, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)

    plan = db.relationship('Plan', backref='subscriptions')
    business = db.relationship('Business', backref='subscriptions', foreign_keys=[business_id])


# Malawi tax engine: effective-dated tax codes (VAT standard/zero-rated/exempt, WHT)
# REVIEW: tax engine models (Phase 1) — see docs/TAX_ENGINE.md and
# REVIEW: ADR-0015 for the design rationale. Key invariants:
# REVIEW: 1. codes are unique per business (tenant isolation, uq below);
# REVIEW: 2. rates are unique per (code, effective_from) so history is
# REVIEW:    append-only — edits add a new dated row, never mutate one.
class TaxCode(db.Model):
    __tablename__ = 'tax_codes'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    tax_type = db.Column(db.String(20), nullable=False, default='vat')  # vat | wht
    treatment = db.Column(db.String(20), nullable=False, default='standard')  # standard | zero_rated | exempt
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (db.UniqueConstraint('business_id', 'code', name='uq_tax_code_business_code'),)

    rates = db.relationship('TaxRate', backref='tax_code', order_by='TaxRate.effective_from')

    # REVIEW: rate_on() is the effective-dating core: it returns the rate of
    # REVIEW: the LATEST row whose effective_from is on/before the document
    # REVIEW: date. `rates` is relationship-ordered by effective_from, so
    # REVIEW: applicable[-1] is the newest applicable row. Returns None when
    # REVIEW: the code predates its earliest rate row.
    def rate_on(self, on_date):
        """Return the Decimal rate effective for the given date, or None."""
        if on_date is None:
            return None
        if hasattr(on_date, 'date'):
            on_date = on_date.date()
        applicable = [r for r in self.rates if r.effective_from <= on_date]
        return applicable[-1].rate if applicable else None


class TaxRate(db.Model):
    __tablename__ = 'tax_rates'
    id = db.Column(db.Integer, primary_key=True)
    tax_code_id = db.Column(db.Integer, db.ForeignKey('tax_codes.id', ondelete='CASCADE'), nullable=False, index=True)
    rate = db.Column(db.Numeric(6, 4), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    __table_args__ = (db.UniqueConstraint('tax_code_id', 'effective_from', name='uq_tax_rate_code_effective'),)


# Financial Statement Categories for accounting classification
# REVIEW: Budget and financial reporting expense classification master record.
class FinancialCategory(db.Model):
    __tablename__ = 'financial_categories'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), nullable=False)  # e.g., COS, OPEX, ADMIN, SELL, FIN, OTH, TAX
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    line_items = db.relationship('LineItem', backref='category', cascade='all, delete-orphan', lazy='select')


# REVIEW: Generic budget and expense line item mapping line descriptions to GL account codes.
class LineItem(db.Model):
    __tablename__ = 'line_items'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('financial_categories.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=True)  # e.g., RAW_MAT, RENT, SALARY
    account_code = db.Column(db.String(20), nullable=True)  # Maps to Chart of Accounts code
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# REVIEW: Staff payroll master record tracking employee profiles and compensation details.
class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    staff_id = db.Column(db.String(20), unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(100), nullable=True)  # e.g., Cashier, Driver, Manager, Laborer
    department = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    payments = db.relationship('Payment', backref='staff_member', lazy='select', foreign_keys='Payment.staff_id')

# REVIEW: re-export block — the canonical definitions live in app/models/accounting.py;
# REVIEW: root models.py re-exports them so legacy `from models import Business` callers
# REVIEW: (scripts/seed.py and friends) keep working. Explicit `as` aliases mark intent.
from app.models.accounting import (  # noqa: E402  # end-of-file by design: avoids circular import with app.models.accounting
    Business as Business,
    ChartOfAccounts as ChartOfAccounts,
    JournalEntry as JournalEntry,
    JournalLine as JournalLine,
    AuditLog as AuditLog,
    ExpenseBudget as ExpenseBudget,
)
