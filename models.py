import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
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
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    supplier = db.Column(db.String(200))
    notes = db.Column(db.Text)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    items = db.relationship('PurchaseItem', backref='purchase', cascade='all, delete-orphan')


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    product = db.relationship('Product', backref='purchase_items')


class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    customer_name = db.Column(db.String(200))
    total_revenue = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    total_cogs = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    cogs = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    product = db.relationship('Product', backref='sale_items')


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(12, 2), nullable=False)


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)


class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    remaining_quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    transaction_type = db.Column(db.String(20), nullable=False, default='PURCHASE')
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    product = db.relationship('Product', backref='stock_transactions')


class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship('Product', backref='warehouse', lazy='select')


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=True)
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
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    product = db.relationship('Product', backref='stock_movements')
    warehouse = db.relationship('Warehouse', backref='stock_movements_destination', foreign_keys=[warehouse_id])
    from_warehouse = db.relationship('Warehouse', backref='stock_movements_source', foreign_keys=[from_warehouse_id])
    to_warehouse = db.relationship('Warehouse', backref='stock_movements_target', foreign_keys=[to_warehouse_id])
    creator = db.relationship('User', backref='created_stock_movements')


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=True)
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
    business_id = db.Column(db.Integer, nullable=True)
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
    business_id = db.Column(db.Integer, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    invoice_number = db.Column(db.String(60), nullable=True)
    invoice_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
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
    business_id = db.Column(db.Integer, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    receipt_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False, default='cash')
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    customer = db.relationship('Customer', backref='receipts')
    invoice = db.relationship('Invoice', backref='receipts')


class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    bill_number = db.Column(db.String(60), nullable=True)
    bill_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
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
    business_id = db.Column(db.Integer, nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False, default='cash')
    reference = db.Column(db.String(100), nullable=True)

    supplier = db.relationship('Supplier', backref='payments')
    bill = db.relationship('Bill', backref='payments')


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, nullable=True)
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


from app.models.accounting import Business, ChartOfAccounts, JournalEntry, JournalLine, AuditLog

