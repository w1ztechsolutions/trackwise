from flask import jsonify
from flask_login import login_required

from app.models import Product, Supplier
from app.services.accounting_service import verify_balances

from . import api_bp


@api_bp.route('/api/products')
@login_required
def api_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in products])


@api_bp.route('/api/suppliers')
@login_required
def api_suppliers():
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in suppliers])


@api_bp.route('/api/accounting/verify')
@login_required
def api_accounting_verify():
    try:
        from flask_login import current_user
        user = current_user if current_user.is_authenticated else None
        if not user or not user.business_id:
            return jsonify({'error': 'No active business context'}), 400
        result = verify_balances(user.business_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
