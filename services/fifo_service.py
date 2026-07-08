from datetime import datetime
from models import (
    db,
    Product,
    StockTransaction,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    Expense,
    Setting,
    Customer,
    Supplier,
    Invoice,
    InvoiceItem,
    Receipt,
    Bill,
    BillItem,
)
from app.services.accounting_service import AccountingException, post_entry, get_account_by_code


class InventoryException(Exception):
    pass


ACCOUNT_CODE_CASH = '1000'
ACCOUNT_CODE_AR = '1200'
ACCOUNT_CODE_INVENTORY = '1400'
ACCOUNT_CODE_AP = '2100'
ACCOUNT_CODE_REVENUE = '4000'
ACCOUNT_CODE_COGS = '5000'

_EXPENSE_ACCOUNT_MAP = {
    'Rent': '5100',
    'Utilities': '5200',
    'Salaries': '5300',
    'Marketing': '5400',
    'Logistics': '5900',
    'Tax': '5900',
    'Supplies': '5900',
    'Other': '5900',
}


def get_tax_rate():
    setting = Setting.query.filter_by(key='tax_rate').first()
    if not setting:
        setting = Setting(key='tax_rate', value='30.0')
        db.session.add(setting)
        db.session.commit()
    try:
        return float(setting.value)
    except ValueError:
        return 30.0


def set_tax_rate(rate):
    setting = Setting.query.filter_by(key='tax_rate').first()
    if not setting:
        setting = Setting(key='tax_rate')
        db.session.add(setting)
    setting.value = str(float(rate))
    db.session.commit()
    return float(setting.value)


def _post_receipt_accounting(receipt_date, amount, receipt_id, business_id, created_by):
    if business_id is None:
        return

    lines = []
    cash_acct = get_account_by_code(business_id, ACCOUNT_CODE_CASH)
    if cash_acct:
        lines.append({'account_id': cash_acct.id, 'debit_amount': amount, 'credit_amount': 0})

    ar_acct = get_account_by_code(business_id, ACCOUNT_CODE_AR)
    if ar_acct:
        lines.append({'account_id': ar_acct.id, 'debit_amount': 0, 'credit_amount': amount})

    if len(lines) >= 2:
        post_entry(
            business_id,
            receipt_date,
            f"Receipt #{receipt_id}",
            lines,
            reference_type='Receipt',
            reference_id=receipt_id,
            created_by=created_by,
        )


def _post_payment_accounting(payment_date, amount, payment_id, business_id, created_by):
    if business_id is None:
        return

    lines = []
    ap_acct = get_account_by_code(business_id, ACCOUNT_CODE_AP)
    if ap_acct:
        lines.append({'account_id': ap_acct.id, 'debit_amount': amount, 'credit_amount': 0})

    cash_acct = get_account_by_code(business_id, ACCOUNT_CODE_CASH)
    if cash_acct:
        lines.append({'account_id': cash_acct.id, 'debit_amount': 0, 'credit_amount': amount})

    if len(lines) >= 2:
        post_entry(
            business_id,
            payment_date,
            f"Payment #{payment_id}",
            lines,
            reference_type='Payment',
            reference_id=payment_id,
            created_by=created_by,
        )


def _post_sale_accounting(sale_date, customer_name, total_revenue, total_cogs, sale_id, business_id, created_by):
    if business_id is None:
        return

    lines = []
    ar_acct = get_account_by_code(business_id, ACCOUNT_CODE_AR)
    cash_acct = get_account_by_code(business_id, ACCOUNT_CODE_CASH)
    receiver = ar_acct or cash_acct
    if receiver:
        lines.append({'account_id': receiver.id, 'debit_amount': total_revenue, 'credit_amount': 0})

    revenue_acct = get_account_by_code(business_id, ACCOUNT_CODE_REVENUE)
    if revenue_acct:
        lines.append({'account_id': revenue_acct.id, 'debit_amount': 0, 'credit_amount': total_revenue})

    cogs_acct = get_account_by_code(business_id, ACCOUNT_CODE_COGS)
    if cogs_acct:
        lines.append({'account_id': cogs_acct.id, 'debit_amount': total_cogs, 'credit_amount': 0})

    inventory_acct = get_account_by_code(business_id, ACCOUNT_CODE_INVENTORY)
    if inventory_acct:
        lines.append({'account_id': inventory_acct.id, 'debit_amount': 0, 'credit_amount': total_cogs})

    if len(lines) >= 2:
        post_entry(
            business_id,
            sale_date,
            f"Sale #{sale_id}: {customer_name}",
            lines,
            reference_type='Sale',
            reference_id=sale_id,
            created_by=created_by,
        )


def _post_purchase_accounting(purchase_date, total_amount, purchase_id, business_id, created_by):
    if business_id is None:
        return

    lines = []
    inventory_acct = get_account_by_code(business_id, ACCOUNT_CODE_INVENTORY)
    if inventory_acct:
        lines.append({'account_id': inventory_acct.id, 'debit_amount': total_amount, 'credit_amount': 0})

    ap_acct = get_account_by_code(business_id, ACCOUNT_CODE_AP)
    cash_acct = get_account_by_code(business_id, ACCOUNT_CODE_CASH)
    payer = ap_acct or cash_acct
    if payer:
        lines.append({'account_id': payer.id, 'debit_amount': 0, 'credit_amount': total_amount})

    if len(lines) >= 2:
        post_entry(
            business_id,
            purchase_date,
            f"Purchase #{purchase_id}",
            lines,
            reference_type='Purchase',
            reference_id=purchase_id,
            created_by=created_by,
        )


def _post_expense_accounting(expense_date, category, amount, expense_id, business_id, created_by):
    if business_id is None:
        return

    expense_acct_code = _EXPENSE_ACCOUNT_MAP.get(category, '5900')
    expense_acct = get_account_by_code(business_id, expense_acct_code)
    cash_acct = get_account_by_code(business_id, ACCOUNT_CODE_CASH)

    lines = []
    if expense_acct:
        lines.append({'account_id': expense_acct.id, 'debit_amount': amount, 'credit_amount': 0})
    if cash_acct:
        lines.append({'account_id': cash_acct.id, 'debit_amount': 0, 'credit_amount': amount})

    if len(lines) >= 2:
        post_entry(
            business_id,
            expense_date,
            f"Expense #{expense_id}: {category}",
            lines,
            reference_type='Expense',
            reference_id=expense_id,
            created_by=created_by,
        )


def record_purchase(purchase_date, supplier, notes, items_data, business_id=None, created_by=None):
    if not items_data:
        raise ValueError("Purchase must contain at least one item.")

    total_amount = 0.0
    purchase_items = []

    for item in items_data:
        product_id = item['product_id']
        quantity = int(item['quantity'])
        unit_cost = float(item['unit_cost'])

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if unit_cost < 0:
            raise ValueError("Unit cost cannot be negative.")

        product = db.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        total_amount += quantity * unit_cost

        pi = PurchaseItem(product_id=product_id, quantity=quantity, unit_cost=unit_cost)
        purchase_items.append((pi, product))

    purchase = Purchase(
        purchase_date=purchase_date or datetime.now(),
        supplier=supplier,
        total_amount=total_amount,
        notes=notes,
    )
    db.session.add(purchase)
    db.session.flush()

    supplier_name = (supplier or '').strip()
    supplier_record = None
    if supplier_name and business_id is not None:
        supplier_record = Supplier.query.filter_by(business_id=business_id, name=supplier_name).first()
        if not supplier_record:
            supplier_record = Supplier(business_id=business_id, name=supplier_name, is_active=True)
            db.session.add(supplier_record)
            db.session.flush()

    bill = None
    if supplier_record or supplier_name:
        bill = Bill(
            business_id=business_id,
            supplier_id=supplier_record.id if supplier_record else None,
            bill_number=f"BILL-{purchase.purchase_date.strftime('%Y%m%d')}-{purchase.id}",
            bill_date=purchase.purchase_date,
            due_date=purchase.purchase_date,
            subtotal=total_amount,
            tax_amount=0.0,
            total_amount=total_amount,
            status='received',
            notes=notes,
        )
        db.session.add(bill)
        db.session.flush()

    for pi, product in purchase_items:
        pi.purchase_id = purchase.id
        db.session.add(pi)
        db.session.flush()

        product.quantity_in_stock += pi.quantity

        tx = StockTransaction(
            product_id=product.id,
            transaction_type='PURCHASE',
            quantity=pi.quantity,
            remaining_quantity=pi.quantity,
            unit_cost=pi.unit_cost,
            timestamp=purchase.purchase_date,
            reference_type='PurchaseItem',
            reference_id=pi.id,
        )
        db.session.add(tx)

        if bill is not None:
            db.session.add(BillItem(
                bill_id=bill.id,
                product_id=product.id,
                description=product.name,
                quantity=pi.quantity,
                unit_cost=pi.unit_cost,
                line_total=float(pi.quantity) * float(pi.unit_cost),
            ))

    db.session.commit()

    _post_purchase_accounting(
        purchase.purchase_date, total_amount, purchase.id, business_id, created_by
    )

    return purchase


def record_sale(sale_date, customer_name, items_data, business_id=None, created_by=None):
    if not items_data:
        raise ValueError("Sale must contain at least one item.")

    sale_date = sale_date or datetime.now()
    total_revenue = 0.0
    total_cogs = 0.0
    sale_items = []

    for item in items_data:
        product_id = item['product_id']
        quantity = int(item['quantity'])
        unit_price = float(item['unit_price'])

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if unit_price < 0:
            raise ValueError("Unit price cannot be negative.")

        product = db.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        if product.quantity_in_stock < quantity:
            raise InventoryException(
                f"Insufficient stock for product '{product.name}'. "
                f"Requested: {quantity}, Available: {product.quantity_in_stock}."
            )

        total_revenue += quantity * unit_price

    sale = Sale(
        sale_date=sale_date,
        customer_name=customer_name,
        total_revenue=total_revenue,
        total_cogs=0.0,
    )
    db.session.add(sale)
    db.session.flush()

    customer_name_value = (customer_name or '').strip()
    customer_record = None
    if customer_name_value and business_id is not None:
        customer_record = Customer.query.filter_by(business_id=business_id, name=customer_name_value).first()
        if not customer_record:
            customer_record = Customer(business_id=business_id, name=customer_name_value, is_active=True)
            db.session.add(customer_record)
            db.session.flush()

    sale_items = []
    for item in items_data:
        product_id = item['product_id']
        quantity_to_sell = int(item['quantity'])
        unit_price = float(item['unit_price'])

        product = db.session.get(Product, product_id)

        layers = (
            StockTransaction.query.filter(
                StockTransaction.product_id == product_id,
                StockTransaction.remaining_quantity > 0,
                StockTransaction.quantity > 0,
            )
            .order_by(StockTransaction.timestamp.asc(), StockTransaction.id.asc())
            .all()
        )

        item_cogs = 0.0
        remaining_to_fulfill = quantity_to_sell

        for layer in layers:
            if remaining_to_fulfill <= 0:
                break

            if layer.remaining_quantity >= remaining_to_fulfill:
                portion_cogs = remaining_to_fulfill * float(layer.unit_cost)
                item_cogs += portion_cogs
                layer.remaining_quantity -= remaining_to_fulfill
                consume_tx = StockTransaction(
                    product_id=product_id,
                    transaction_type='SALE',
                    quantity=-remaining_to_fulfill,
                    remaining_quantity=0,
                    unit_cost=layer.unit_cost,
                    timestamp=sale_date,
                    reference_type='SaleItem',
                    reference_id=None,
                )
                db.session.add(consume_tx)
                remaining_to_fulfill = 0
            else:
                taken = layer.remaining_quantity
                portion_cogs = taken * float(layer.unit_cost)
                item_cogs += portion_cogs
                layer.remaining_quantity = 0
                consume_tx = StockTransaction(
                    product_id=product_id,
                    transaction_type='SALE',
                    quantity=-taken,
                    remaining_quantity=0,
                    unit_cost=layer.unit_cost,
                    timestamp=sale_date,
                    reference_type='SaleItem',
                    reference_id=None,
                )
                db.session.add(consume_tx)
                remaining_to_fulfill -= taken

        if remaining_to_fulfill > 0:
            raise InventoryException(f"Inventory mismatch while processing FIFO layers for {product.name}.")

        product.quantity_in_stock -= quantity_to_sell

        si = SaleItem(
            sale_id=sale.id,
            product_id=product_id,
            quantity=quantity_to_sell,
            unit_price=unit_price,
            cogs=item_cogs,
        )
        db.session.add(si)
        db.session.flush()
        sale_items.append(si)
        total_cogs += item_cogs

    invoice = None
    if customer_record or customer_name_value:
        invoice = Invoice(
            business_id=business_id,
            customer_id=customer_record.id if customer_record else None,
            invoice_number=f"INV-{sale_date.strftime('%Y%m%d')}-{sale.id}",
            invoice_date=sale_date,
            due_date=sale_date,
            subtotal=total_revenue,
            tax_amount=0.0,
            total_amount=total_revenue,
            status='issued',
            notes=f"Auto-generated from sale #{sale.id}",
        )
        db.session.add(invoice)
        db.session.flush()

        for si in sale_items:
            db.session.add(InvoiceItem(
                invoice_id=invoice.id,
                product_id=si.product_id,
                description=si.product.name if si.product else None,
                quantity=si.quantity,
                unit_price=si.unit_price,
                line_total=float(si.quantity) * float(si.unit_price),
            ))

        receipt = Receipt(
            business_id=business_id,
            customer_id=customer_record.id if customer_record else None,
            invoice_id=invoice.id,
            receipt_date=sale_date,
            amount=total_revenue,
            payment_method='cash',
            reference=f"Sale {sale.id}",
            notes='Auto-generated receipt',
        )
        db.session.add(receipt)

    sale.total_cogs = total_cogs
    db.session.commit()

    _post_sale_accounting(
        sale_date, customer_name, total_revenue, total_cogs, sale.id, business_id, created_by
    )
    if invoice is not None:
        _post_receipt_accounting(
            sale_date,
            total_revenue,
            invoice.id,
            business_id,
            created_by,
        )

    return sale


def record_expense(expense_date, category, description, amount, business_id=None, created_by=None):
    if amount < 0:
        raise ValueError("Expense amount cannot be negative.")
    if not category:
        raise ValueError("Expense category is required.")
    expense = Expense(
        expense_date=expense_date or datetime.now(),
        category=category,
        description=description,
        amount=float(amount),
    )
    db.session.add(expense)
    db.session.flush()
    db.session.commit()

    _post_expense_accounting(
        expense.expense_date, category, amount, expense.id, business_id, created_by
    )

    return expense


def get_profit_loss(start_date=None, end_date=None):
    sales_query = Sale.query
    if start_date:
        sales_query = sales_query.filter(Sale.sale_date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Sale.sale_date <= end_date)
    sales = sales_query.all()

    total_sales = sum(float(s.total_revenue) for s in sales)
    total_cogs = sum(float(s.total_cogs) for s in sales)
    gross_profit = total_sales - total_cogs

    expenses_query = Expense.query
    if start_date:
        expenses_query = expenses_query.filter(Expense.expense_date >= start_date)
    if end_date:
        expenses_query = expenses_query.filter(Expense.expense_date <= end_date)
    expenses = expenses_query.all()

    total_expenses = sum(float(e.amount) for e in expenses)
    pre_tax_profit = gross_profit - total_expenses
    tax_rate = get_tax_rate()
    tax_amount = max(0.0, pre_tax_profit * (tax_rate / 100.0))
    net_profit = pre_tax_profit - tax_amount

    expense_by_category = {}
    for e in expenses:
        expense_by_category[e.category] = expense_by_category.get(e.category, 0.0) + float(e.amount)

    return {
        'total_sales': total_sales,
        'total_cogs': total_cogs,
        'gross_profit': gross_profit,
        'total_expenses': total_expenses,
        'expense_by_category': expense_by_category,
        'pre_tax_profit': pre_tax_profit,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'net_profit': net_profit,
        'sales_count': len(sales),
        'expenses_count': len(expenses),
    }


def get_inventory_valuation():
    products = Product.query.all()
    product_valuations = []
    total_valuation = 0.0

    for product in products:
        layers = (
            StockTransaction.query.filter(
                StockTransaction.product_id == product.id,
                StockTransaction.remaining_quantity > 0,
                StockTransaction.quantity > 0,
            ).all()
        )
        prod_val = 0.0
        for layer in layers:
            prod_val += float(layer.remaining_quantity) * float(layer.unit_cost)
        total_valuation += prod_val
        product_valuations.append({
            'product': product,
            'valuation': prod_val,
            'quantity': product.quantity_in_stock,
        })

    return {
        'product_valuations': product_valuations,
        'total_valuation': total_valuation,
    }
