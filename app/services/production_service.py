from __future__ import annotations

from datetime import datetime, timezone

from models import db, Product, StockTransaction, ProductionBatch, MaterialUsage, FinishedGoodOutput, ChartOfAccounts
from app.services.accounting_service import get_account_by_code, post_entry


ACCOUNT_CODE_RAW_MATERIALS = '1410'
ACCOUNT_CODE_WIP = '1450'
ACCOUNT_CODE_FINISHED_GOODS = '1460'
ACCOUNT_CODE_INVENTORY = '1400'


def _ensure_account(business_id: int | None, code: str, name: str, account_type: str = 'asset'):
    if business_id is None:
        return None

    account = get_account_by_code(business_id, code)
    if account:
        return account

    account = ChartOfAccounts(
        business_id=business_id,
        code=code,
        name=name,
        type=account_type,
        is_active=True,
    )
    db.session.add(account)
    db.session.flush()
    return account


class ProductionServiceException(Exception):
    pass


def create_batch(*, business_id: int | None, product_id: int, quantity_produced: int, notes: str | None = None, created_by: int | None = None, production_date: datetime | None = None):
    product = db.session.get(Product, product_id)
    if not product:
        raise ProductionServiceException(f'Product {product_id} not found')

    if quantity_produced <= 0:
        raise ProductionServiceException('quantity_produced must be > 0')

    batch = ProductionBatch(
        business_id=business_id,
        batch_number=f"PB-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        production_date=production_date or datetime.now(timezone.utc),
        product_id=product.id,
        quantity_produced=quantity_produced,
        status='planned',
        notes=notes,
        created_by=created_by,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def consume_material(*, business_id: int | None, production_batch_id: int, product_id: int, quantity: int, unit_cost: float | int, created_by: int | None = None):
    batch = db.session.get(ProductionBatch, production_batch_id)
    if not batch:
        raise ProductionServiceException('Production batch not found')

    product = db.session.get(Product, product_id)
    if not product:
        raise ProductionServiceException(f'Product {product_id} not found')

    if quantity <= 0:
        raise ProductionServiceException('quantity must be > 0')
    if product.quantity_in_stock < quantity:
        raise ProductionServiceException(f'Insufficient stock for product {product.name}')

    usage = MaterialUsage(
        production_batch_id=batch.id,
        product_id=product.id,
        quantity_consumed=quantity,
        unit_cost_at_consumption=float(unit_cost),
    )
    db.session.add(usage)
    db.session.flush()

    product.quantity_in_stock -= quantity

    tx = StockTransaction(
        product_id=product.id,
        transaction_type='PRODUCTION_CONSUMPTION',
        quantity=-quantity,
        remaining_quantity=0,
        unit_cost=float(unit_cost),
        timestamp=batch.production_date,
        reference_type='ProductionBatch',
        reference_id=batch.id,
    )
    db.session.add(tx)
    db.session.commit()

    if business_id is not None:
        raw_material_acct = _ensure_account(business_id, ACCOUNT_CODE_RAW_MATERIALS, 'Raw Materials')
        wip_acct = _ensure_account(business_id, ACCOUNT_CODE_WIP, 'Work in Progress')
        if raw_material_acct and wip_acct:
            cost_value = float(quantity) * float(unit_cost)
            post_entry(
                business_id,
                batch.production_date,
                f"Raw materials usage for batch {batch.batch_number}",
                [
                    {'account_id': wip_acct.id, 'debit_amount': cost_value, 'credit_amount': 0},
                    {'account_id': raw_material_acct.id, 'debit_amount': 0, 'credit_amount': cost_value},
                ],
                reference_type='ProductionMaterialUsage',
                reference_id=usage.id,
                created_by=created_by,
            )

    return usage


def complete_batch(*, business_id: int | None, production_batch_id: int, unit_cost: float | int, created_by: int | None = None):
    batch = db.session.get(ProductionBatch, production_batch_id)
    if not batch:
        raise ProductionServiceException('Production batch not found')

    if batch.status == 'completed':
        return batch

    finished_product = db.session.get(Product, batch.product_id)
    if not finished_product:
        raise ProductionServiceException('Finished product not found')

    total_material_cost = sum(float(usage.quantity_consumed * usage.unit_cost_at_consumption) for usage in batch.material_usages)
    total_output = batch.quantity_produced
    if total_output <= 0:
        raise ProductionServiceException('quantity_produced must be > 0')

    unit_cost_value = float(unit_cost) if unit_cost is not None else (total_material_cost / total_output if total_output else 0.0)
    output = FinishedGoodOutput(
        production_batch_id=batch.id,
        product_id=finished_product.id,
        quantity=total_output,
        unit_cost=unit_cost_value,
    )
    db.session.add(output)
    db.session.flush()

    finished_product.quantity_in_stock += total_output

    tx = StockTransaction(
        product_id=finished_product.id,
        transaction_type='PRODUCTION_OUTPUT',
        quantity=total_output,
        remaining_quantity=total_output,
        unit_cost=unit_cost_value,
        timestamp=batch.production_date,
        reference_type='ProductionBatch',
        reference_id=batch.id,
    )
    db.session.add(tx)

    batch.status = 'completed'
    batch.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    if business_id is not None:
        finished_goods_acct = _ensure_account(business_id, ACCOUNT_CODE_FINISHED_GOODS, 'Finished Goods')
        wip_acct = _ensure_account(business_id, ACCOUNT_CODE_WIP, 'Work in Progress')
        if finished_goods_acct and wip_acct:
            amount = float(total_output) * unit_cost_value
            post_entry(
                business_id,
                batch.production_date,
                f"Production batch {batch.batch_number}",
                [
                    {'account_id': finished_goods_acct.id, 'debit_amount': amount, 'credit_amount': 0},
                    {'account_id': wip_acct.id, 'debit_amount': 0, 'credit_amount': amount},
                ],
                reference_type='ProductionBatch',
                reference_id=batch.id,
                created_by=created_by,
            )

    return batch
