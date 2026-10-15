# Tax Engine (Malawi)

TrackWise computes VAT through effective-dated tax codes, not free-typed
percentages. Every document line (sales invoice line, purchase/bill line)
references a `TaxCode`; the rate applied is whatever the code's rate history
says was in force **on the document date**. This is what makes back-dated
entries, rate changes, and defensible VAT returns possible.

## Statutory basis (Malawi, verified October 2026)

| Item | Fact |
|---|---|
| Standard VAT rate | **17.5%** effective 1 January 2026 (raised from 16.5% in the 2025/26 mid-year budget review) |
| Pre-2026 standard rate | 16.5% |
| Registration threshold | MK 25 million taxable turnover in 12 months |
| Returns | Monthly, via Msonkho Online |
| E-invoicing | EFDs ceased 31 January 2026; MRA Electronic Invoicing System (EIS) mandatory for VAT-registered taxpayers |

**Re-verify against mra.mw before any release that touches rates.** The
change history lives in `app/services/tax_service.py`
(`_MALAWI_VAT_STANDARD_HISTORY`); add each verified change there with its
effective date — never edit an existing rate in place.

## Model

- `TaxCode` (`tax_codes`): per-business; `code` (VAT-S, VAT-ZR, VAT-E, and
  future WHT codes), `name`, `tax_type` (vat | wht), `treatment`
  (standard | zero_rated | exempt), `is_active`.
- `TaxRate` (`tax_rates`): `tax_code_id`, `rate` (Decimal 6,4),
  `effective_from` (Date). Unique per (code, date). A code with no rate
  effective on a given date resolves to `None` and posts zero tax.
- `InvoiceItem.tax_code_id`, `BillItem.tax_code_id`: line-level links.

Default codes are seeded lazily and idempotently by
`tax_service.ensure_default_tax_codes(business_id)` (called by
`list_tax_codes`, so the first time any business touches tax UI or API the
codes exist). Users can edit rates; seeding never overwrites existing rates.

## Posting rules

| Event | Journal |
|---|---|
| Sale/invoice line with tax | Dr AR/Cash (gross), Cr Revenue (net), Cr 2200 VAT Payable (output tax), plus COGS/inventory lines |
| Purchase line with tax | Dr Inventory (net), Dr 2200 VAT Payable (input tax), Cr AP/Cash (gross) |

Account 2200 therefore carries output tax (credits) minus recoverable input
tax (debits); its period balance is the VAT payable to MRA. This is the
figure the upcoming VAT return report (Phase 1, next PR) will present per
month.

## Service API (`app/services/tax_service.py`)

- `ensure_default_tax_codes(business_id)` — idempotent seed
- `list_tax_codes(business_id, active_only=True)`
- `get_tax_code(business_id, tax_code_id)`
- `resolve_rate(tax_code_id, on_date)` — Decimal rate in force, or None
- `calculate_line_tax(line_amount, tax_code_id, on_date, tax_inclusive=False)` —
  returns `(net, tax, gross)`; inclusive extracts the net from the gross
- `compute_document_tax(items, business_id, on_date, tax_inclusive=False)` —
  per-line results plus subtotal / total_tax / total

## UI / API surface

- Invoice form (`templates/invoices.html`): per-line **Tax Code** select;
  server resolves the rate by invoice date.
- Purchase form (`static/js/purchases.js`): per-line **VAT Code** select
  (fetched from `GET /api/tax-codes`).
- `GET /api/tax-codes`: the business's codes with today's resolved rate.

## Verification log

| Date | Verified by | Notes |
|---|---|---|
| 2026-10-15 | Agent (web research) | 17.5% standard rate from Jan 2026; 16.5% prior; threshold MK 25m; EIS mandatory from ~1 May 2026. Sources: MRA/VAT news coverage. Re-verify on mra.mw before release. |
