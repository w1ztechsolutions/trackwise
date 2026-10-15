"""Malawi tax engine service.

Effective-dated tax codes and rates for VAT (and later WHT), seeded with the
Malawi statutory VAT history:

- Standard rate 17.5% effective 1 January 2026 (mid-year budget review 2025/26
  raised it from 16.5%). Kept alongside the 16.5% baseline so back-dated
  entries resolve to the rate that was actually in force.
- Zero-rated and exempt codes carry a 0% rate; they exist so businesses below
  the MK 25 million registration threshold can still tag transactions.

Rates are re-verified against mra.mw before each release that touches them;
see docs/TAX_ENGINE.md for the verification log.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from models import db, TaxCode, TaxRate

TWO_PLACES = Decimal('0.01')

# Malawi statutory VAT history. Oldest-first.
_MALAWI_VAT_STANDARD_HISTORY = [
    (date(2000, 1, 1), Decimal('16.5000')),
    (date(2026, 1, 1), Decimal('17.5000')),
]

# Default codes seeded for every business. WHT codes arrive in a later phase
# once their rates are verified against the current Taxation Act schedule.
_DEFAULT_CODES = [
    ('VAT-S', 'VAT Standard Rate (17.5%)', 'vat', 'standard', _MALAWI_VAT_STANDARD_HISTORY),
    ('VAT-ZR', 'VAT Zero-Rated (exports, basic food basket)', 'vat', 'zero_rated', [(date(2000, 1, 1), Decimal('0.0000'))]),
    ('VAT-E', 'VAT Exempt (financial, medical, education services)', 'vat', 'exempt', [(date(2000, 1, 1), Decimal('0.0000'))]),
]


def ensure_default_tax_codes(business_id):
    """Idempotently seed the default Malawi tax codes for a business.

    Safe to call repeatedly; existing codes and any rates the user has edited
    are left untouched.
    """
    if business_id is None:
        return []
    created = []
    for code, name, tax_type, treatment, history in _DEFAULT_CODES:
        tax_code = TaxCode.query.filter_by(business_id=business_id, code=code).first()
        if tax_code is None:
            tax_code = TaxCode(
                business_id=business_id,
                code=code,
                name=name,
                tax_type=tax_type,
                treatment=treatment,
            )
            db.session.add(tax_code)
            db.session.flush()
            created.append(tax_code)
        # Query directly: the relationship may hold a stale empty list for
        # codes created earlier in this session.
        existing_froms = {
            r.effective_from for r in TaxRate.query.filter_by(tax_code_id=tax_code.id)
        }
        for effective_from, rate in history:
            if effective_from not in existing_froms:
                db.session.add(TaxRate(
                    tax_code_id=tax_code.id,
                    rate=rate,
                    effective_from=effective_from,
                ))
    if created:
        db.session.flush()
    return created


def list_tax_codes(business_id, active_only=True):
    """Return the business's tax codes, seeding defaults on first use."""
    ensure_default_tax_codes(business_id)
    query = TaxCode.query.filter_by(business_id=business_id)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(TaxCode.code).all()


def get_tax_code(business_id, tax_code_id):
    """Return a tax code owned by the business, or None."""
    if tax_code_id is None:
        return None
    return TaxCode.query.filter_by(business_id=business_id, id=int(tax_code_id)).first()


def resolve_rate(tax_code_id, on_date):
    """Resolve the Decimal rate in force for a tax code on a given date.

    Returns None when the code has no rate effective on or before on_date.
    """
    tax_code = db.session.get(TaxCode, tax_code_id) if tax_code_id is not None else None
    if tax_code is None:
        return None
    return tax_code.rate_on(on_date)


def calculate_line_tax(line_amount, tax_code_id, on_date, tax_inclusive=False):
    """Compute the net, tax, and gross for a document line.

    line_amount is the line total before tax when tax_inclusive is False, and
    the tax-inclusive total when tax_inclusive is True.

    Returns (net, tax, gross) as Decimals rounded to 2 places. A missing or
    unrated tax code yields zero tax and the input back as net.
    """
    amount = Decimal(str(line_amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    rate = resolve_rate(tax_code_id, on_date)
    if rate is None or amount == 0:
        return amount, Decimal('0.00'), amount

    fraction = (rate / Decimal('100')).quantize(Decimal('0.000001'))
    if tax_inclusive:
        net = (amount / (Decimal('1') + fraction)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        tax = (amount - net).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return net, tax, amount
    tax = (amount * fraction).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return amount, tax, (amount + tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_document_tax(items, business_id, on_date, tax_inclusive=False):
    """Compute per-line and total tax for a document.

    ``items`` is a list of dicts, each with ``line_total`` and optionally
    ``tax_code_id``. Returns a dict with per-line results and document totals:

        {
          'lines': [{'tax_code_id': ..., 'tax_rate': Decimal, 'tax_amount': Decimal, 'net': Decimal}],
          'subtotal': Decimal, 'total_tax': Decimal, 'total': Decimal,
        }
    """
    lines = []
    subtotal = Decimal('0.00')
    total_tax = Decimal('0.00')
    for item in items:
        line_total = item.get('line_total') or 0
        tax_code_id = item.get('tax_code_id')
        net, tax, _gross = calculate_line_tax(line_total, tax_code_id, on_date, tax_inclusive)
        rate = resolve_rate(tax_code_id, on_date)
        lines.append({
            'tax_code_id': int(tax_code_id) if tax_code_id is not None else None,
            'tax_rate': rate if rate is not None else Decimal('0.0000'),
            'tax_amount': tax,
            'net': net,
        })
        subtotal += net
        total_tax += tax
    return {
        'lines': lines,
        'subtotal': subtotal.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'total_tax': total_tax.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        'total': (subtotal + total_tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    }
