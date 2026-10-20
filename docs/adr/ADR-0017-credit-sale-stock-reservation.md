# ADR-0017: Derived Stock Reservation for Credit Sales

**Feature:** Issuing a credit invoice reserves its lines against on-hand stock;
walk-in sales can no longer sell units promised to an open invoice.

**Why chosen:**
> The retailer workflow audit found credit invoices did not reserve stock: a
> cash sale could consume the same units an open invoice promised, so the
> delivery against the invoice failed later with no warning.

**Decision:**
- Reservations are **derived live from invoice lines**, not stored: an
  invoice reserves its quantities while its status is one of
  `draft / issued / sent / partially_paid` AND no `Sale` has been recorded
  against it (`app/services/inventory_service.reserved_quantities`).
- `available = on-hand − reserved` is enforced server-side in three places:
  invoice creation (`ensure_lines_available` rejects before any rows are
  written), walk-in `record_sale` (raises the existing InventoryException
  with a reservation-aware message), and the sales checkout UI
  (`/api/products` exposes `available_quantity`; the client blocks early).
- Fulfilling an invoice's own reservation (`record_sale(invoice_id=...)`)
  checks raw on-hand — the reserved units are physically on the shelf.
- Issuing a credit invoice now **requires the stock to be available**: the
  retailer flow does not support pre-order invoicing. Voiding an invoice,
  manually marking it paid, or recording the sale releases the units
  automatically (status leaves the reserved set).

**Strengths:**
- No schema change, no migration, no backfill: existing open invoices in
  production start reserving correctly the moment the code ships.
- Release logic is automatic — no reservation rows can leak or dangle.
- One grouped SQL query per availability check; the API route batches it
  for all products in one query.

**Alternatives considered:**
- A `StockTransaction(type='RESERVATION')` layer — rejected: pollutes FIFO
  cost layers with non-cost rows and requires a backfill migration for
  existing open invoices.
- A `reserved_quantity` column on Product — rejected: denormalized state
  must be maintained on every lifecycle transition (void, pay, credit
  note), with leak risk on partial failures.
- Warn-only on invoice creation — rejected: the integrity hole stays open;
  negative availability would silently poison the checkout math.
- Allow pre-order invoicing (reserve below zero) — deferred: one-line
  policy change in `ensure_lines_available` if the market asks for it.
