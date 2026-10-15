"""Malawi tax engine tests: seeding, effective-date resolution, line math,
and input/output VAT posting."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from models import db, TaxCode, TaxRate, Product, Purchase
from app.models.accounting import ChartOfAccounts, JournalEntry
from app.services import tax_service
from app.services.fifo_service import record_purchase, record_sale
from tests.conftest import seed_test_business


# ---------- seeding ----------

class TestSeeding:
    def test_ensure_default_tax_codes_seeds_three_vat_codes(self, app, business):
        created = tax_service.ensure_default_tax_codes(business.id)
        assert len(created) == 3
        codes = {tc.code for tc in tax_service.list_tax_codes(business.id)}
        assert codes == {'VAT-S', 'VAT-ZR', 'VAT-E'}

    def test_ensure_is_idempotent(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        created = tax_service.ensure_default_tax_codes(business.id)
        assert created == []
        assert TaxCode.query.filter_by(business_id=business.id).count() == 3

    def test_standard_code_carries_effective_dated_history(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        froms = sorted(r.effective_from for r in std.rates)
        assert froms == [date(2000, 1, 1), date(2026, 1, 1)]

    def test_codes_are_scoped_per_business(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        other = TaxCode.query.filter_by(business_id=business.id + 999).count()
        assert other == 0


# ---------- rate resolution ----------

class TestRateResolution:
    def test_pre_2026_date_resolves_to_16_5(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        assert std.rate_on(date(2025, 6, 15)) == Decimal('16.5000')

    def test_2026_date_resolves_to_17_5(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        assert std.rate_on(date(2026, 1, 1)) == Decimal('17.5000')
        assert std.rate_on(date(2026, 10, 15)) == Decimal('17.5000')

    def test_datetime_is_accepted(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        assert std.rate_on(datetime(2026, 5, 1, 12, 0)) == Decimal('17.5000')

    def test_zero_rated_and_exempt_resolve_to_zero(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        for code, expected in (('VAT-ZR', '0.0000'), ('VAT-E', '0.0000')):
            tc = TaxCode.query.filter_by(business_id=business.id, code=code).one()
            assert tc.rate_on(date(2026, 3, 1)) == Decimal(expected)

    def test_no_applicable_rate_returns_none(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        assert std.rate_on(date(1999, 12, 31)) is None


# ---------- line math ----------

class TestLineMath:
    @pytest.fixture(autouse=True)
    def seeded(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        self.std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()

    def test_exclusive_2026(self, app):
        net, tax, gross = tax_service.calculate_line_tax(
            Decimal('1000.00'), self.std.id, date(2026, 2, 1))
        assert net == Decimal('1000.00')
        assert tax == Decimal('175.00')
        assert gross == Decimal('1175.00')

    def test_exclusive_2025_uses_old_rate(self, app):
        net, tax, _ = tax_service.calculate_line_tax(
            Decimal('1000.00'), self.std.id, date(2025, 2, 1))
        assert tax == Decimal('165.00')

    def test_inclusive_extraction(self, app):
        net, tax, gross = tax_service.calculate_line_tax(
            Decimal('1175.00'), self.std.id, date(2026, 2, 1), tax_inclusive=True)
        assert net == Decimal('1000.00')
        assert tax == Decimal('175.00')
        assert gross == Decimal('1175.00')

    def test_zero_and_missing_code_are_safe(self, app):
        assert tax_service.calculate_line_tax(0, self.std.id, date(2026, 2, 1))[1] == 0
        net, tax, gross = tax_service.calculate_line_tax(500, None, date(2026, 2, 1))
        assert (net, tax, gross) == (Decimal('500.00'), Decimal('0.00'), Decimal('500.00'))

    def test_compute_document_tax_sums_lines(self, app, business):
        zr = TaxCode.query.filter_by(business_id=business.id, code='VAT-ZR').one()
        result = tax_service.compute_document_tax(
            [
                {'line_total': 1000, 'tax_code_id': self.std.id},
                {'line_total': 500, 'tax_code_id': zr.id},
                {'line_total': 200, 'tax_code_id': None},
            ],
            business.id,
            date(2026, 2, 1),
        )
        assert result['subtotal'] == Decimal('1700.00')
        assert result['total_tax'] == Decimal('175.00')
        assert result['total'] == Decimal('1875.00')
        assert result['lines'][1]['tax_amount'] == Decimal('0.00')


# ---------- posting: input VAT on purchases ----------

class TestInputVatPosting:
    def _product(self, business):
        product = Product(
            business_id=business.id,
            name='Crate of Soft Drinks',
            sku='SD-1',
            default_selling_price=Decimal('1500.00'),
        )
        db.session.add(product)
        db.session.commit()
        return product

    def _tax_account_id(self, business):
        acct = ChartOfAccounts.query.filter_by(business_id=business.id, code='2200').one()
        return acct.id

    def _vat_moves(self, business):
        acct_id = self._tax_account_id(business)
        entries = JournalEntry.query.filter_by(business_id=business.id).all()
        debits = credits = Decimal('0')
        for entry in entries:
            for line in entry.lines:
                if line.account_id == acct_id:
                    debits += line.debit_amount or 0
                    credits += line.credit_amount or 0
        return debits, credits

    def test_purchase_with_tax_posts_input_vat_as_debit(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        product = self._product(business)

        purchase = record_purchase(
            purchase_date=datetime(2026, 2, 1, 10, 0),
            supplier='Wholesale Ltd',
            notes='',
            items_data=[{
                'product_id': product.id,
                'quantity': 10,
                'unit_cost': 1000.0,
                'tax_code_id': std.id,
            }],
            business_id=business.id,
            created_by=None,
        )

        assert float(purchase.total_amount) == 11750.0

        debits, credits = self._vat_moves(business)
        assert debits == Decimal('1750.00')  # 10,000 net x 17.5%
        assert credits == Decimal('0.00')

    def test_purchase_without_tax_is_unchanged(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        product = self._product(business)

        purchase = record_purchase(
            purchase_date=datetime(2026, 2, 1, 10, 0),
            supplier='Wholesale Ltd',
            notes='',
            items_data=[{'product_id': product.id, 'quantity': 5, 'unit_cost': 100.0}],
            business_id=business.id,
            created_by=None,
        )
        assert float(purchase.total_amount) == 500.0
        debits, credits = self._vat_moves(business)
        assert debits == Decimal('0.00')

    def test_bill_line_stores_tax_code_and_amount(self, app, business):
        from models import Bill, BillItem
        tax_service.ensure_default_tax_codes(business.id)
        std = TaxCode.query.filter_by(business_id=business.id, code='VAT-S').one()
        product = self._product(business)

        record_purchase(
            purchase_date=datetime(2026, 2, 1, 10, 0),
            supplier='Wholesale Ltd',
            notes='',
            items_data=[{'product_id': product.id, 'quantity': 2, 'unit_cost': 500.0, 'tax_code_id': std.id}],
            business_id=business.id,
            created_by=None,
        )

        bill = Bill.query.filter_by(business_id=business.id).one()
        assert float(bill.tax_amount) == 175.00
        assert float(bill.total_amount) == 1175.00
        item = BillItem.query.filter_by(bill_id=bill.id).one()
        assert item.tax_code_id == std.id
        assert float(item.tax_amount) == 175.00


# ---------- posting: output VAT on sales ----------

class TestOutputVatPosting:
    def test_sale_tax_posts_to_vat_payable_as_credit(self, app, business):
        tax_service.ensure_default_tax_codes(business.id)
        product = Product(
            business_id=business.id,
            name='Selling Item',
            sku='SI-1',
            default_selling_price=Decimal('100.00'),
        )
        db.session.add(product)
        db.session.commit()

        # Build FIFO layers first so the sale can consume them.
        record_purchase(
            purchase_date=datetime(2026, 1, 15, 8, 0),
            supplier='Stock Supplier',
            notes='',
            items_data=[{'product_id': product.id, 'quantity': 20, 'unit_cost': 50.0}],
            business_id=business.id,
            created_by=None,
        )

        record_sale(
            sale_date=datetime(2026, 3, 1, 9, 0),
            customer_name='Walk-in',
            items_data=[{'product_id': product.id, 'quantity': 10, 'unit_price': 100.0}],
            business_id=business.id,
            created_by=None,
            tax_amount=175.00,
        )

        acct = ChartOfAccounts.query.filter_by(business_id=business.id, code='2200').one()
        entries = JournalEntry.query.filter_by(business_id=business.id).all()
        tax_credits = sum(
            (line.credit_amount or 0)
            for entry in entries
            for line in entry.lines
            if line.account_id == acct.id
        )
        assert tax_credits == Decimal('175.00')
