# ADR-0016: Output VAT on Walk-in Cash Sales

**Feature:** Cash checkout sales charge VAT through the effective-dated tax engine and store it on the Sale row.

**Why chosen:**
> The retailer workflow audit found walk-in sales posting zero output VAT —
> tax was only pulled from a linked invoice, so POS sales of a
> VAT-registered business produced revenue with no VAT Payable credit, an
> MRA compliance hole (17.5% standard rate since Jan 2026).

**Decision:**
- `sales.tax_amount` (Numeric(14,2), default 0) added via migration
  `20261020_vat_document_tax` (which also merges the four outstanding
  migration heads into one lineage). `total_revenue` stays NET; the cash/AR
  side posts GROSS (net + tax).
- The checkout form submits a per-line **tax code id** (same contract as
  invoices and purchases, ADR-0015); the rate is resolved server-side by
  sale date, never client-supplied.
- The UI preselects the standard-rate code (VAT-S) because the target user
  is a VAT-registered Malawian retailer; "None" remains a one-click opt-out
  for non-registered businesses or zero-rated/exempt sales.
- Tax precedence in `record_sale`: (1) linked invoice tax wins, (2) explicit
  tax_amount for legacy callers, (3) per-line codes computed at sale date.
- Input VAT on purchases needed no change: Bills already carry it
  (Dr 2200), and the VAT return report already nets output minus input.

**Strengths:**
- One control account (2200) carries output credits and input debits, so
  the VAT return and the monthly Msonkho figure derive directly from the GL.
- Legacy behavior preserved: sales without codes post exactly as before;
  imports pass explicit tax_amount.
- Migration is additive with a server default, so existing rows read 0 tax.

**Alternatives considered:**
- Separate "VAT Input" asset account — rejected: the VAT return already
  nets within 2200 and the report/UI read that account; a new account would
  complicate the return for no statutory benefit.
- Tax-inclusive shelf pricing (extract VAT from gross) — deferred: Malawian
  POS practice in the target segment is tax-exclusive entry; the engine's
  `tax_inclusive` path exists when needed.
