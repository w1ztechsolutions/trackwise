# REVIEW: Operational domain models re-exporting product, sales, purchasing, and inventory classes.
"""Inventory, sales, purchases, production, subscription, and business domain models.

This module provides a clean namespace for all operational (non-accounting) models.
All classes are defined in the legacy ``models`` module for backward compatibility
and re-exported here for organized imports.
"""

from models import (
    Product,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    Expense,
    Setting,
    StockTransaction,
    Warehouse,
    StockMovement,
    Customer,
    Supplier,
    Invoice,
    InvoiceItem,
    Receipt,
    Bill,
    BillItem,
    Payment,
    ProductionBatch,
    MaterialUsage,
    FinishedGoodOutput,
    Plan,
    Subscription,
    # REVIEW: explicit re-exports — app.models.__init__ pulls TaxCode/TaxRate from here;
    # REVIEW: the canonical definitions are in root models.py.
    TaxCode as TaxCode,
    TaxRate as TaxRate,
    FinancialCategory,
    LineItem,
    Staff,
)

__all__ = [
    "Product",
    "Purchase",
    "PurchaseItem",
    "Sale",
    "SaleItem",
    "Expense",
    "Setting",
    "StockTransaction",
    "Warehouse",
    "StockMovement",
    "Customer",
    "Supplier",
    "Invoice",
    "InvoiceItem",
    "Receipt",
    "Bill",
    "BillItem",
    "Payment",
    "ProductionBatch",
    "MaterialUsage",
    "FinishedGoodOutput",
    "Plan",
    "Subscription",
    "FinancialCategory",
    "LineItem",
    "Staff",
]
