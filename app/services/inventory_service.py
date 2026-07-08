from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from models import db, Product, StockTransaction, StockMovement, Warehouse
from app.services.accounting_service import post_entry, get_account_by_code


class InventoryServiceException(Exception):
    pass


# Accounting account codes (must exist in Chart of Accounts)
ACCOUNT_CODE_CASH = '1000'
ACCOUNT_CODE_INVENTORY = '1400'
ACCOUNT_CODE_COGS = '5000'

# For adjustments/transfers, we keep it conservative:
# - transfers are internal (no accounting)
# - stock adjustments are treated as:
#   * increase => Dr Inventory, Cr COGS/Adjustment contra
#   * decrease => Dr COGS/Adjustment, Cr Inventory
# If you have a dedicated "Inventory Adjustment" account, wire it here.
ACCOUNT_CODE_INVENTORY_ADJUSTMENT = '5900'


def _ensure_positive_int(value, name: str) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        raise InventoryServiceException(f"{name} must be an integer")
    if ivalue <= 0:
        raise InventoryServiceException(f"{name} must be > 0")
    return ivalue


def _ensure_non_negative_decimal(value, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except Exception:
        raise InventoryServiceException(f"{name} must be numeric")
    if d < 0:
        raise InventoryServiceException(f"{name} must be >= 0")
    return d


def _get_default_unit_cost(product: Product) -> Decimal:
    # Fallback: use current FIFO layer unit_cost for valuation.
    layer = (
        StockTransaction.query.filter(
            StockTransaction.product_id == product.id,
            StockTransaction.remaining_quantity > 0,
            StockTransaction.quantity > 0,
        )
        .order_by(StockTransaction.timestamp.asc(), StockTransaction.id.asc())
        .first()
    )
    if not layer:
        return Decimal('0.00')
    return Decimal(str(layer.unit_cost))


def adjust_stock(
    *,
    business_id: int | None,
    product_id: int,
    warehouse_id: int | None,
    adjustment_type: str,
    quantity: int,
    unit_cost: Optional[Decimal] = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
    timestamp: datetime | None = None,
):
    """Manual inventory adjustment.

    adjustment_type: 'IN' or 'OUT' or 'ADJUSTMENT_IN'/'ADJUSTMENT_OUT'
    quantity must be positive.

    Posts accounting as inventory <-> adjustment/COGS (placeholder mapping).
    """
    if adjustment_type is None:
        raise InventoryServiceException("adjustment_type is required")

    t = adjustment_type.upper().strip()
    if t in {'IN', 'ADJUSTMENT_IN'}:
        movement_type = 'ADJUSTMENT_IN'
        sign = 1
    elif t in {'OUT', 'ADJUSTMENT_OUT'}:
        movement_type = 'ADJUSTMENT_OUT'
        sign = -1
    else:
        raise InventoryServiceException("adjustment_type must be IN or OUT")

    qty = _ensure_positive_int(quantity, 'quantity')
    ts = timestamp or datetime.now(timezone.utc)

    product = db.session.get(Product, product_id)
    if not product:
        raise InventoryServiceException(f"Product {product_id} not found")

    wh = None
    if warehouse_id is not None:
        wh = db.session.get(Warehouse, warehouse_id)
        if not wh or (wh.is_active is False):
            raise InventoryServiceException("Invalid or inactive warehouse")

    cost = _ensure_non_negative_decimal(unit_cost if unit_cost is not None else _get_default_unit_cost(product), 'unit_cost')
    movement_value = cost * Decimal(str(qty))

    # Update legacy FIFO tracking (keeps system consistent)
    # - increase: add a purchase-like layer
    # - decrease: create an outgoing layer at provided cost (simplified)
    if sign == 1:
        tx = StockTransaction(
            business_id=business_id,
            product_id=product.id,
            transaction_type='ADJUSTMENT_IN',
            quantity=qty,
            remaining_quantity=qty,
            unit_cost=cost,
            timestamp=ts,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        product.quantity_in_stock += qty
    else:
        # consume from FIFO layers first
        if product.quantity_in_stock < qty:
            raise InventoryServiceException("Insufficient stock for OUT adjustment")

        remaining_to_fulfill = qty
        layers = (
            StockTransaction.query.filter(
                StockTransaction.product_id == product.id,
                StockTransaction.remaining_quantity > 0,
                StockTransaction.quantity > 0,
            )
            .order_by(StockTransaction.timestamp.asc(), StockTransaction.id.asc())
            .all()
        )
        for layer in layers:
            if remaining_to_fulfill <= 0:
                break
            taken = min(int(layer.remaining_quantity), remaining_to_fulfill)
            portion_cogs_cost = Decimal(str(layer.unit_cost)) * Decimal(str(taken))
            layer.remaining_quantity -= taken

            consume_tx = StockTransaction(
                business_id=business_id,
                product_id=product.id,
                transaction_type='ADJUSTMENT_OUT',
                quantity=-taken,
                remaining_quantity=0,
                unit_cost=layer.unit_cost,
                timestamp=ts,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            db.session.add(consume_tx)
            remaining_to_fulfill -= taken

        if remaining_to_fulfill > 0:
            raise InventoryServiceException("FIFO consumption failed for OUT adjustment")

        product.quantity_in_stock -= qty

    # Create stock movement (warehouse-aware)
    sm = StockMovement(
        business_id=business_id,
        product_id=product.id,
        warehouse_id=warehouse_id,
        type=movement_type,
        quantity=qty * sign,
        unit_cost=cost,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=created_by,
        notes=notes,
        timestamp=ts,
    )
    db.session.add(sm)
    db.session.commit()

    # Accounting postings (best-effort)
    # Inventory account: debit/in credit depending on adjustment
    if business_id is not None:
        inventory_acct = get_account_by_code(business_id, ACCOUNT_CODE_INVENTORY)
        adj_acct = get_account_by_code(business_id, ACCOUNT_CODE_INVENTORY_ADJUSTMENT)

        lines = []
        if sign == 1:
            # Increase: Dr Inventory, Cr Adjustment
            if inventory_acct:
                lines.append({'account_id': inventory_acct.id, 'debit_amount': float(movement_value), 'credit_amount': 0})
            if adj_acct:
                lines.append({'account_id': adj_acct.id, 'debit_amount': 0, 'credit_amount': float(movement_value)})
        else:
            # Decrease: Dr Adjustment, Cr Inventory
            if adj_acct:
                lines.append({'account_id': adj_acct.id, 'debit_amount': float(movement_value), 'credit_amount': 0})
            if inventory_acct:
                lines.append({'account_id': inventory_acct.id, 'debit_amount': 0, 'credit_amount': float(movement_value)})

        if len(lines) >= 2:
            post_entry(
                business_id,
                ts,
                f"Inventory adjustment for product {product_id}",
                lines,
                reference_type='InventoryAdjustment',
                reference_id=sm.id,
                created_by=created_by,
            )

    return sm


def record_stock_count(
    *,
    business_id: int | None,
    product_id: int,
    warehouse_id: int | None,
    counted_quantity: int,
    created_by: int | None = None,
    notes: str | None = None,
    timestamp: datetime | None = None,
):
    """Record a physical inventory count and post the variance as an adjustment."""
    product = db.session.get(Product, product_id)
    if not product:
        raise InventoryServiceException(f"Product {product_id} not found")

    current_quantity = int(product.quantity_in_stock or 0)
    counted_quantity = int(counted_quantity)

    if counted_quantity < 0:
        raise InventoryServiceException("counted_quantity must be >= 0")

    variance = counted_quantity - current_quantity
    if variance == 0:
        return None

    adjustment_type = "ADJUSTMENT_IN" if variance > 0 else "ADJUSTMENT_OUT"
    adjustment_quantity = abs(variance)

    return adjust_stock(
        business_id=business_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        adjustment_type=adjustment_type,
        quantity=adjustment_quantity,
        unit_cost=None,
        reference_type="StockCount",
        reference_id=None,
        created_by=created_by,
        notes=notes or "Physical inventory count",
        timestamp=timestamp,
    )


def transfer_stock(
    *,
    business_id: int | None,
    product_id: int,
    from_warehouse_id: int,
    to_warehouse_id: int,
    quantity: int,
    reference_type: str | None = None,
    reference_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
    timestamp: datetime | None = None,
):
    """Transfer stock between warehouses.

    Implementation detail (compatibility):
    - Keeps legacy FIFO cost consumption/inventory update globally.
    - Records warehouse movement rows.
    - Does not post accounting because transfer is internal.
    """
    qty = _ensure_positive_int(quantity, 'quantity')
    if from_warehouse_id == to_warehouse_id:
        raise InventoryServiceException("from_warehouse_id and to_warehouse_id must be different")

    ts = timestamp or datetime.now(timezone.utc)

    product = db.session.get(Product, product_id)
    if not product:
        raise InventoryServiceException(f"Product {product_id} not found")

    from_wh = db.session.get(Warehouse, from_warehouse_id)
    to_wh = db.session.get(Warehouse, to_warehouse_id)
    if not from_wh or not to_wh:
        raise InventoryServiceException("Invalid warehouse")

    if product.quantity_in_stock < qty:
        raise InventoryServiceException("Insufficient stock for transfer")

    # FIFO consumption globally; transfer does not change total inventory.
    remaining_to_fulfill = qty
    layers = (
        StockTransaction.query.filter(
            StockTransaction.product_id == product.id,
            StockTransaction.remaining_quantity > 0,
            StockTransaction.quantity > 0,
        )
        .order_by(StockTransaction.timestamp.asc(), StockTransaction.id.asc())
        .all()
    )

    for layer in layers:
        if remaining_to_fulfill <= 0:
            break
        taken = min(int(layer.remaining_quantity), remaining_to_fulfill)
        portion_cogs_cost = Decimal(str(layer.unit_cost)) * Decimal(str(taken))
        layer.remaining_quantity -= taken

        # OUT layer
        consume_tx = StockTransaction(
            business_id=business_id,
            product_id=product.id,
            transaction_type='TRANSFER_OUT',
            quantity=-taken,
            remaining_quantity=0,
            unit_cost=layer.unit_cost,
            timestamp=ts,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db.session.add(consume_tx)
        remaining_to_fulfill -= taken

    if remaining_to_fulfill > 0:
        raise InventoryServiceException("FIFO consumption failed for transfer")

    # Create IN layer with same cost approximation: use default unit cost from FIFO at time.
    # For correctness, you'd mirror exact per-layer costs; this version keeps it simple.
    # (StockMovement keeps warehouse-level record for UI/valuation.)
    unit_cost = _get_default_unit_cost(product)
    in_tx = StockTransaction(
        business_id=business_id,
        product_id=product.id,
        transaction_type='TRANSFER_IN',
        quantity=qty,
        remaining_quantity=qty,
        unit_cost=unit_cost,
        timestamp=ts,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(in_tx)

    sm = StockMovement(
        business_id=business_id,
        product_id=product.id,
        warehouse_id=None,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        type='TRANSFER',
        quantity=qty,
        unit_cost=unit_cost,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=created_by,
        notes=notes,
        timestamp=ts,
    )
    db.session.add(sm)
    db.session.commit()

    return sm


def get_valuation_by_warehouse(*, business_id: int | None, warehouse_id: int | None):
    """Compute inventory valuation per warehouse.

    Compatibility approach:
    - Since legacy FIFO layers are not warehouse-scoped, we use StockMovement rows
      to scope valuation instead of remaining StockTransaction layers.

    Returns list of {product, warehouse_id, quantity, valuation}.
    """
    q = db.session.query(StockMovement).filter(StockMovement.product_id.isnot(None))

    if business_id is not None:
        q = q.filter(StockMovement.business_id == business_id)

    if warehouse_id is not None:
        q = q.filter(StockMovement.from_warehouse_id == warehouse_id) | q.filter(StockMovement.to_warehouse_id == warehouse_id)  # type: ignore

    movements = q.all()

    # Naive computation by movements net quantity * unit_cost (for UI only).
    by_product = {}
    for m in movements:
        # Transfer: treat quantity positive as IN if to_warehouse matches; negative as OUT if from matches.
        qty = int(m.quantity or 0)
        unit_cost = Decimal(str(m.unit_cost or 0))

        if m.type == 'TRANSFER':
            if warehouse_id is not None and m.to_warehouse_id == warehouse_id:
                qty_effective = qty
            elif warehouse_id is not None and m.from_warehouse_id == warehouse_id:
                qty_effective = -qty
            else:
                continue
        else:
            # Adjustments and simple IN/OUT apply to warehouse_id field
            if warehouse_id is not None and m.warehouse_id != warehouse_id:
                continue
            qty_effective = qty

        key = (m.product_id, warehouse_id)
        if key not in by_product:
            by_product[key] = {'quantity': 0, 'valuation': Decimal('0.00')}
        by_product[key]['quantity'] += qty_effective
        by_product[key]['valuation'] += (unit_cost * Decimal(str(qty_effective)))

    results = []
    for (product_id, wh_id), agg in by_product.items():
        product = db.session.get(Product, product_id)
        if not product:
            continue
        results.append({
            'product': product,
            'warehouse_id': wh_id,
            'quantity': int(agg['quantity']),
            'valuation': float(agg['valuation']),
        })

    return {
        'warehouse_id': warehouse_id,
        'items': results,
    }