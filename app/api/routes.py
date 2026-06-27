from flask import jsonify

from models import Product

from . import api_bp


@api_bp.route('/api/products')
def api_products():
    products = Product.query.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in products])

