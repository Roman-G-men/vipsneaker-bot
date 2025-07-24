# webapp.py - ФИНАЛЬНАЯ ВЕРСИЯ (ТОЛЬКО МАГАЗИН ДЛЯ КЛИЕНТОВ)

import logging
import json
import os
from flask import Flask, render_template, request, abort
from sqlalchemy.exc import SQLAlchemyError
from database import get_scoped_session, Product, Order, User

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development')
app.config['TEMPLATES_AUTO_RELOAD'] = True

Session = get_scoped_session()

@app.teardown_request
def remove_session(ex=None):
    """Автоматически закрывает сессию после каждого запроса."""
    Session.remove()

@app.route('/')
def index():
    """Главная страница магазина с каталогом товаров."""
    user_id = request.args.get('user_id', '')
    logger.info(f"WEBAPP: Запрос главной страницы от пользователя: {user_id}")
    try:
        products = Session.query(Product).filter_by(is_active=1).order_by(Product.id.desc()).all()
        return render_template('index.html', products=products, user_id=user_id)
    except Exception as e:
        logger.error(f"WEBAPP: Ошибка при загрузке товаров: {e}", exc_info=True)
        return render_template('error.html', message="Не удалось загрузить каталог товаров."), 500

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Страница деталей конкретного товара."""
    user_id = request.args.get('user_id', '')
    logger.info(f"WEBAPP: Запрос товара {product_id} от пользователя: {user_id}")
    try:
        product = Session.query(Product).filter_by(id=product_id, is_active=1).first()
        if not product:
            abort(404)
        return render_template('product.html', product=product, user_id=user_id)
    except Exception as e:
        logger.error(f"WEBAPP: Ошибка при загрузке товара {product_id}: {e}", exc_info=True)
        return render_template('error.html', message="Ошибка при загрузке информации о товаре."), 500

@app.route('/cart')
def cart_page():
    """Отображает страницу корзины."""
    user_id = request.args.get('user_id', '')
    logger.info(f"WEBAPP: Пользователь {user_id} открыл корзину")
    return render_template('cart.html', user_id=user_id)

@app.route('/orders')
def user_orders():
    """Страница заказов пользователя."""
    user_id = request.args.get('user_id')
    if not user_id: return render_template('error.html', message="Не указан ID пользователя."), 400
    try:
        orders = Session.query(Order).filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
        for order in orders:
            if isinstance(order.items, str):
                try:
                    order.items = json.loads(order.items)
                except json.JSONDecodeError:
                    order.items = []
        return render_template('orders.html', orders=orders, user_id=user_id)
    except Exception as e:
        logger.error(f"WEBAPP: Ошибка загрузки заказов {user_id}: {e}", exc_info=True)
        return render_template('error.html', message="Не удалось загрузить историю заказов."), 500