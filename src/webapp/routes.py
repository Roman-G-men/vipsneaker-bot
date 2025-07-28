# src/webapp/routes.py
from flask import Blueprint, render_template, jsonify
from database import SessionLocal
from database import queries
bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/products')
def api_get_products():
    db = SessionLocal()
    try:
        products = queries.get_active_products_with_variants(db)
        return jsonify(products)
    finally:
        db.close()


@bp.route('/api/product/<int:product_id>')
def api_get_product_details(product_id):
    db = SessionLocal()
    try:
        product = queries.get_product_details(db, product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404

        # Отдаем только варианты, которые есть в наличии
        variants = [
            {'id': v.id, 'size': v.size, 'price': v.price, 'stock': v.stock}
            for v in product.variants if v.stock > 0
        ]

        product_details = {
            'id': product.id, 'name': product.name, 'brand': product.brand,
            'description': product.description, 'composition': product.composition,
            'photo_url': product.photo_url, 'variants': variants
        }
        return jsonify(product_details)
    finally:
        db.close()