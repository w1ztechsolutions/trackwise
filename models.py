import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


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


class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    sale_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    customer_name = db.Column(db.String(200))
    total_revenue = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    total_cogs = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')


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


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    expense_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(12, 2), nullable=False)


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('business_id', 'key', name='uq_business_setting_key'),
    )


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


class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship('Product', backref='warehouse', lazy='select')


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
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    product = db.relationship('Product', backref='stock_movements')
    warehouse = db.relationship('Warehouse', backref='stock_movements_destination', foreign_keys=[warehouse_id])
    from_warehouse = db.relationship('Warehouse', backref='stock_movements_source', foreign_keys=[from_warehouse_id])
    to_warehouse = db.relationship('Warehouse', backref='stock_movements_target', foreign_keys=[to_warehouse_id])
    creator = db.relationship('User', backref='created_stock_movements')


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    credit_limit = db.Column(db.Numeric(14, 2), nullable=True)
    opening_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    opening_balance = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


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

    invoice = db.relationship('Invoice', backref='items')
    product = db.relationship('Product', backref='invoice_items')


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

    bill = db.relationship('Bill', backref='items')
    product = db.relationship('Product', backref='bill_items')


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False, default='cash')
    reference = db.Column(db.String(100), nullable=True)

    supplier = db.relationship('Supplier', backref='payments')
    bill = db.relationship('Bill', backref='payments')


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


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


class MaterialUsage(db.Model):
    __tablename__ = 'material_usages'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    production_batch_id = db.Column(db.Integer, db.ForeignKey('production_batches.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_consumed = db.Column(db.Integer, nullable=False, default=0)
    unit_cost_at_consumption = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)

    product = db.relationship('Product', backref='material_usages')


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
class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    max_users = db.Column(db.Integer, nullable=False, default=1)
    features = db.Column(db.Text, nullable=True)  # JSON string
    is_active = db.Column(db.Boolean, nullable=False, default=True)


# Subscription model for business subscriptions
class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='active')
    start_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    renewal_date = db.Column(db.DateTime, nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)

    plan = db.relationship('Plan', backref='subscriptions')
    business = db.relationship('Business', backref='subscriptions', foreign_keys=[business_id])


from app.models.accounting import Business, ChartOfAccounts, JournalEntry, JournalLine, AuditLog