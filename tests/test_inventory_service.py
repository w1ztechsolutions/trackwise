from datetime import datetime, timezone

from flask import Flask

from models import db, Product, StockMovement, StockTransaction, Warehouse
from app.services.inventory_service import record_stock_count, transfer_stock
from app.models.accounting import Business, ChartOfAccounts


def _seed_business():
    business = Business(name='Inventory Test Biz', currency='MWK')
    db.session.add(business)
    db.session.flush()
    # Seed cash account for accounting
    db.session.add(ChartOfAccounts(business_id=business.id, code='1000', name='Cash', type='asset'))
    db.session.add(ChartOfAccounts(business_id=business.id, code='1400', name='Inventory', type='asset'))
    db.session.commit()
    return business


def test_record_stock_count_creates_adjustment_for_variance():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config['SECRET_KEY'] = 'test'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        business = _seed_business()

        product = Product(sku="INV-001", name="Inventory Test", default_selling_price=10.0, business_id=business.id)
        product.quantity_in_stock = 10
        db.session.add(product)
        db.session.flush()

        db.session.add(
            StockTransaction(
                business_id=business.id,
                product_id=product.id,
                transaction_type="PURCHASE",
                quantity=10,
                remaining_quantity=10,
                unit_cost=5.0,
                timestamp=datetime.now(timezone.utc),
            )
        )

        warehouse = Warehouse(name="Main Warehouse", is_active=True, business_id=business.id)
        db.session.add(warehouse)
        db.session.commit()

        movement = record_stock_count(
            business_id=business.id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            counted_quantity=8,
            created_by=None,
            notes="Physical count",
        )

        db.session.refresh(product)

        assert movement is not None
        assert product.quantity_in_stock == 8
        assert StockMovement.query.filter_by(product_id=product.id).count() == 1
        assert StockMovement.query.filter_by(product_id=product.id).first().type == "ADJUSTMENT_OUT"


def test_transfer_stock_creates_movement_between_warehouses():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config['SECRET_KEY'] = 'test'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        business = _seed_business()

        product = Product(sku="INV-002", name="Transfer Test", default_selling_price=10.0, business_id=business.id)
        product.quantity_in_stock = 10
        db.session.add(product)
        db.session.flush()

        db.session.add(
            StockTransaction(
                business_id=business.id,
                product_id=product.id,
                transaction_type="PURCHASE",
                quantity=10,
                remaining_quantity=10,
                unit_cost=5.0,
                timestamp=datetime.now(timezone.utc),
            )
        )

        source_wh = Warehouse(name="Source Warehouse", is_active=True, business_id=business.id)
        target_wh = Warehouse(name="Target Warehouse", is_active=True, business_id=business.id)
        db.session.add_all([source_wh, target_wh])
        db.session.commit()

        movement = transfer_stock(
            business_id=business.id,
            product_id=product.id,
            from_warehouse_id=source_wh.id,
            to_warehouse_id=target_wh.id,
            quantity=3,
            created_by=None,
            notes="Warehouse transfer",
        )

        db.session.refresh(product)

        assert movement is not None
        assert product.quantity_in_stock == 10
        assert StockMovement.query.filter_by(product_id=product.id).count() == 1
        assert StockMovement.query.filter_by(product_id=product.id).first().type == "TRANSFER"