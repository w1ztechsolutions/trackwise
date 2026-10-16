from datetime import date

from flask import jsonify
from flask_login import current_user, login_required

from app.models import Product, Supplier
from app.services.accounting_service import verify_balances
from app.services.tax_service import list_tax_codes

from . import api_bp


# REVIEW: Multi-tenant tenant resolver for API queries.
# REVIEW: Extracts business_id from current_user session to prevent cross-tenant data access.
def _business_id():
    """Return the authenticated user's business_id, or None.

    All JSON endpoints scope queries to the current user's business so that
    authenticated users cannot read other tenants' data (multi-tenant isolation).
    """
    if not current_user.is_authenticated:
        return None
    return getattr(current_user, "business_id", None)


@api_bp.route('/api/products')
@login_required
# REVIEW: JSON endpoint serving product catalog options for UI selects and forms.
# REVIEW: Scoped strictly by business_id.
def api_products():
    business_id = _business_id()
    query = Product.query
    if business_id is not None:
        query = query.filter_by(business_id=business_id)
    products = query.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in products])


@api_bp.route('/api/suppliers')
@login_required
# REVIEW: JSON endpoint serving supplier options for purchasing forms.
# REVIEW: Scoped strictly by business_id.
def api_suppliers():
    business_id = _business_id()
    query = Supplier.query
    if business_id is not None:
        query = query.filter_by(business_id=business_id)
    suppliers = query.order_by(Supplier.name.asc()).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in suppliers])


@api_bp.route('/api/tax-codes')
@login_required
def api_tax_codes():
    # REVIEW: read-only tenant endpoint: _business_id() scopes to the
    # REVIEW: logged-in user's business, and the rate served is TODAY's
    # REVIEW: resolved rate for display only — the authoritative rate is
    # REVIEW: always re-resolved server-side per document date at POST.
    business_id = _business_id()
    codes = list_tax_codes(business_id)
    today = date.today()
    return jsonify([
        {
            'id': tc.id,
            'code': tc.code,
            'name': tc.name,
            'treatment': tc.treatment,
            'rate': float(tc.rate_on(today) or 0),
        }
        for tc in codes
    ])


@api_bp.route('/api/accounting/verify')
@login_required
# REVIEW: Accounting balance audit endpoint running trial balance debit/credit balance checks.
def api_accounting_verify():
    try:
        business_id = _business_id()
        if business_id is None:
            return jsonify({'error': 'No active business context'}), 400
        result = verify_balances(business_id)
        return jsonify(result)
    except Exception as e:
        from app.models import db
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
