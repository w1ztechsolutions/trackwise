from app.models.accounting import Business, ChartOfAccounts, JournalEntry
from app.services.production_service import create_batch, consume_material, complete_batch
from models import Product, ProductionBatch, MaterialUsage, FinishedGoodOutput, db, User


def test_production_batch_flow_updates_inventory_and_outputs(app):
    with app.app_context():
        business = Business(name='Production Test', currency='MWK')
        db.session.add(business)
        db.session.flush()

        for code, name in {
            '1000': 'Cash',
            '1400': 'Inventory',
            '5000': 'COGS',
        }.items():
            db.session.add(ChartOfAccounts(business_id=business.id, code=code, name=name, type='asset' if code == '1400' else 'expense'))

        user = User(business_id=business.id, email='prod-test@example.com', role='admin')
        user.set_password('testpass')
        db.session.add(user)
        db.session.flush()

        raw_material = Product(sku='RAW-001', name='Sand', quantity_in_stock=20, default_selling_price=0.0)
        finished_good = Product(sku='FG-001', name='Block', quantity_in_stock=0, default_selling_price=100.0)
        db.session.add_all([raw_material, finished_good])
        db.session.commit()

        batch = create_batch(
            business_id=business.id,
            product_id=finished_good.id,
            quantity_produced=10,
            notes='Initial run',
            created_by=user.id,
        )

        consume_material(
            business_id=business.id,
            production_batch_id=batch.id,
            product_id=raw_material.id,
            quantity=5,
            unit_cost=4.0,
            created_by=user.id,
        )

        complete_batch(
            business_id=business.id,
            production_batch_id=batch.id,
            unit_cost=10.0,
            created_by=user.id,
        )

        batch = db.session.get(ProductionBatch, batch.id)
        assert batch.status == 'completed'
        assert MaterialUsage.query.filter_by(production_batch_id=batch.id).count() == 1
        assert FinishedGoodOutput.query.filter_by(production_batch_id=batch.id).count() == 1
        assert finished_good.quantity_in_stock == 10
        assert raw_material.quantity_in_stock == 15
        entry = JournalEntry.query.filter_by(reference_type='ProductionBatch', reference_id=batch.id).first()
        assert entry is not None
        assert len(entry.lines) >= 2
