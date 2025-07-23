# webapp.py - ПОЛНАЯ ВЕРСИЯ С КОРЗИНОЙ

import logging
import json
from flask import Flask, render_template, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from database import get_scoped_session, Product, Order, User

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_super_secret_key_for_dev_and_prod'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Создаем фабрику сессий, которая будет уникальна для каждого запроса
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
        products = Session.query(Product).filter_by(is_active=1).order_by(Product.name).all()
        return render_template('index.html', products=products, user_id=user_id)
    except SQLAlchemyError as e:
        logger.error(f"WEBAPP: Ошибка при загрузке товаров: {e}", exc_info=True)
        return render_template('error.html', message="Не удалось загрузить каталог товаров."), 500


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Страница деталей конкретного товара."""
    user_id = request.args.get('user_id', '')
    try:
        product = Session.query(Product).filter_by(id=product_id, is_active=1).first()
        if not product:
            return render_template('error.html', message="Товар не найден или снят с продажи."), 404
        return render_template('product.html', product=product, user_id=user_id)
    except SQLAlchemyError as e:
        logger.error(f"WEBAPP: Ошибка при загрузке товара {product_id}: {e}", exc_info=True)
        return render_template('error.html', message="Ошибка при загрузке информации о товаре."), 500


# <<< НОВЫЙ МАРШРУТ ДЛЯ КОРЗИНЫ >>>
@app.route('/cart')
def cart_page():
    """Отображает страницу корзины."""
    user_id = request.args.get('user_id', '')
    logger.info(f"WEBAPP: Пользователь {user_id} открыл корзину")
    # Просто отдаем HTML-шаблон, вся магия будет в JavaScript на стороне клиента
    return render_template('cart.html', user_id=user_id)


@app.route('/create_order', methods=['POST'])
def create_order():
    """API-ручка для создания заказа в базе данных."""
    logger.info("WEBAPP: Поступил запрос на создание заказа")
    try:
        data = request.json
        if not all(k in data for k in ['user_id', 'items', 'delivery_type', 'phone', 'address', 'total_price']):
            logger.error(f"WEBAPP: Неполные данные для создания заказа: {data}")
            return jsonify({"status": "error", "message": "Не все обязательные поля заполнены."}), 400

        # Здесь в будущем будет создание платежа в ЮKassa

        order = Order(
            user_id=data['user_id'],
            items=json.dumps(data['items']),
            delivery_type=data['delivery_type'],
            address=data.get('address', '').strip(),
            phone=data['phone'].strip(),
            total_amount=data['total_price'],
            status='Ожидает оплаты'  # Новый статус
        )
        Session.add(order)
        Session.commit()
        logger.info(f"WEBAPP: Заказ #{order.id} успешно создан для пользователя {order.user_id}")

        # В будущем здесь будем возвращать ссылку на оплату от ЮKassa
        return jsonify({
            "status": "success",
            "order_id": order.id,
            "message": "Заказ успешно создан, перенаправляем на оплату..."
        })

    except SQLAlchemyError as e:
        Session.rollback()
        logger.error(f"WEBAPP: Ошибка БД при создании заказа: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Ошибка базы данных при создании заказа."}), 500
    except Exception as e:
        logger.error(f"WEBAPP: Непредвиденная ошибка при создании заказа: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Внутренняя ошибка сервера."}), 500