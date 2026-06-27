from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    quantity_in_stock = db.Column(db.Integer, default=0, nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=5, nullable=False)
    default_selling_price = db.Column(db.Float, default=0.0, nullable=False)
    
    # Relationships
    stock_transactions = db.relationship('StockTransaction', backref='product', cascade='all, delete-orphan', lazy=True)
    purchase_items = db.relationship('PurchaseItem', backref='product', cascade='all, delete-orphan', lazy=True)
    sale_items = db.relationship('SaleItem', backref='product', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'quantity_in_stock': self.quantity_in_stock,
            'low_stock_threshold': self.low_stock_threshold,
            'default_selling_price': self.default_selling_price
        }


class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'PURCHASE', 'SALE', 'ADJUSTMENT'
    quantity = db.Column(db.Integer, nullable=False)  # positive for restock, negative for sale/reduction
    remaining_quantity = db.Column(db.Integer, default=0, nullable=False) # For FIFO layer tracking (only positive stock changes)
    unit_cost = db.Column(db.Float, nullable=False)  # The unit cost for this batch/layer
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reference_type = db.Column(db.String(50), nullable=True)  # 'PurchaseItem', 'SaleItem', 'Manual'
    reference_id = db.Column(db.Integer, nullable=True)


class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    supplier = db.Column(db.String(100), nullable=True)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    items = db.relationship('PurchaseItem', backref='purchase', cascade='all, delete-orphan', lazy=True)


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)


class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    customer_name = db.Column(db.String(100), nullable=True)
    total_revenue = db.Column(db.Float, default=0.0, nullable=False)
    total_cogs = db.Column(db.Float, default=0.0, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    net_profit = db.Column(db.Float, default=0.0, nullable=False)
    
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan', lazy=True)


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    cogs = db.Column(db.Float, default=0.0, nullable=False)  # COGS allocated to this item via FIFO


class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # e.g., 'Rent', 'Utilities', 'Salaries', etc.
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=False)


class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
