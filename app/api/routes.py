from flask import jsonify
from flask_login import current_user, login_required

from app.models import Product, Supplier
from app.services.accounting_service import verify_balances

from . import api_bp


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
def api_products():
    business_id = _business_id()
    query = Product.query
    if business_id is not None:
        query = query.filter_by(business_id=business_id)
    products = query.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in products])


@api_bp.route('/api/suppliers')
@login_required
def api_suppliers():
    business_id = _business_id()
    query = Supplier.query
    if business_id is not None:
        query = query.filter_by(business_id=business_id)
    suppliers = query.order_by(Supplier.name.asc()).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in suppliers])


@api_bp.route('/api/accounting/verify')
@login_required
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
