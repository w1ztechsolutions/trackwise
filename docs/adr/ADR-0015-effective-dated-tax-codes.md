# ADR-0015: Effective-dated tax codes for the Malawi tax engine

- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Roadmap Phase 1 (docs/2026-10-15-critical-review-and-roadmap.md)
  requires rate-versioned tax codes because Malawi's standard VAT rate moved
  from 16.5% to 17.5% effective 1 January 2026, and MRA returns must state
  the rate that was legally in force per period. Before this ADR, invoice
  lines carried a free-typed `tax_rate` (client-supplied percentage, defaulted
  to a flat business "tax rate" setting of 30% — an income-tax estimate, not
  VAT), and purchases posted no input VAT at all.

## Decision

1. Introduce per-business `TaxCode` (VAT standard / zero-rated / exempt;
   WHT types later) and effective-dated `TaxRate` rows. The applied rate is
   resolved **server-side by document date**; clients submit a code, never a
   percentage.
2. Seed defaults idempotently (`ensure_default_tax_codes`) with the verified
   Malawi history (16.5% baseline, 17.5% from 2026-01-01). Never edit a rate
   in place — append a new effective-dated row.
3. Post input VAT on purchases as a **debit** to account 2200 alongside the
   existing output-tax **credit** on sales, so 2200's balance is net VAT
   payable — the number the MRA return needs.
4. Backward compatibility: the legacy `tax_rate`/`tax_amount` columns and the
   `Setting`-based `get_tax_rate` remain (used for the income-tax estimate
   in reports); only the document-entry path moved to codes.

## Consequences

- Historical documents keep their stored `tax_rate`/`tax_amount`; only new
  entries resolve from the code history, so a rate change never rewrites
  posted entries.
- Existing forms/tests that free-typed a rate had to move to the code
  select; the route contract changed from `tax_rate[]` to `tax_code[]`.
- A code with no rate effective on a date (e.g., pre-2000) resolves to zero
  tax rather than erroring — deliberate, to keep import/backfill paths
  working.
- The next step (VAT return report) reads journal lines on 2200, splitting
  debits (input) from credits (output) per period.
