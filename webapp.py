# webapp.py - ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ (МАГАЗИН + АДМИН-ПАНЕЛЬ)

import logging
import json
import os
import requests
from flask import Flask, render_template, request, jsonify, Response, flash, redirect, url_for, abort
from sqlalchemy.exc import SQLAlchemyError
from database import get_scoped_session, Product, Order

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ImgBB ---
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

app = Flask(__name__)
# Устанавливаем секретный ключ для работы flash-сообщений
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Создаем фабрику сессий, которая будет уникальна для каждого запроса
Session = get_scoped_session()


@app.teardown_request
def remove_session(ex=None):
    """Автоматически закрывает сессию после каждого запроса."""
    Session.remove()


# --- АДМИН-ПАНЕЛЬ: АУТЕНТИФИКАЦИЯ ---
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret123')


def check_auth(username, password):
    """Проверяет логин и пароль."""
    return username == ADMIN_USER and password == ADMIN_PASSWORD


def authenticate():
    """Отправляет ответ с требованием авторизации."""
    return Response('Требуется авторизация для доступа к админ-панели.', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    """Декоратор для защиты роутов админ-панели."""

    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


# --- МАРШРУТЫ МАГАЗИНА (ДЛЯ ПОЛЬЗОВАТЕЛЕЙ) ---
@app.route('/')
def index():
    user_id = request.args.get('user_id', '')
    try:
        products = Session.query(Product).filter_by(is_active=1).order_by(Product.name).all()
        return render_template('index.html', products=products, user_id=user_id)
    except SQLAlchemyError as e:
        logger.error(f"WEBAPP: Ошибка при загрузке товаров: {e}", exc_info=True)
        return render_template('error.html', message="Не удалось загрузить каталог товаров."), 500


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    user_id = request.args.get('user_id', '')
    product = Session.query(Product).filter_by(id=product_id, is_active=1).first()
    if not product:
        abort(404)  # Если товар не найден или неактивен, возвращаем стандартную ошибку 404
    return render_template('product.html', product=product, user_id=user_id)


@app.route('/cart')
def cart_page():
    user_id = request.args.get('user_id', '')
    return render_template('cart.html', user_id=user_id)


@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.json
        required_fields = ['user_id', 'items', 'delivery_type', 'phone', 'address', 'total_price']
        if not all(k in data for k in required_fields):
            return jsonify({"status": "error", "message": "Не все обязательные поля заполнены."}), 400

        order = Order(
            user_id=data['user_id'],
            items=json.dumps(data['items']),
            delivery_type=data['delivery_type'],
            address=data.get('address', '').strip(),
            phone=data['phone'].strip(),
            total_amount=data['total_price'],
            status='Ожидает оплаты'
        )
        Session.add(order)
        Session.commit()
        logger.info(f"WEBAPP: Заказ #{order.id} успешно создан для пользователя {order.user_id}")
        return jsonify({"status": "success", "order_id": order.id})
    except Exception as e:
        Session.rollback()
        logger.error(f"WEBAPP: Ошибка при создании заказа: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Внутренняя ошибка сервера."}), 500


# --- МАРШРУТЫ АДМИН-ПАНЕЛИ (ДЛЯ АДМИНИСТРАТОРА) ---
def upload_to_imgbb(image_file):
    """Функция для загрузки изображения на ImgBB."""
    if not IMGBB_API_KEY:
        raise ValueError("IMGBB_API_KEY не установлен в .env файле!")

    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": (image_file.filename, image_file.read(), image_file.mimetype)}

    response = requests.post(url, data=payload, files=files)
    response.raise_for_status()

    result = response.json()
    if result.get("success"):
        logger.info(f"Изображение успешно загружено: {result['data']['url']}")
        return result["data"]["url"]
    else:
        error_message = result.get('error', {}).get('message', 'Неизвестная ошибка ImgBB')
        raise Exception(f"Ошибка ImgBB: {error_message}")


@app.route('/admin')
@requires_auth
def admin_dashboard():
    products_count = Session.query(Product).count()
    orders_count = Session.query(Order).count()
    pending_orders = Session.query(Order).filter(Order.status.in_(['Ожидает оплаты', 'Обработка'])).count()
    return render_template('admin/dashboard.html', products_count=products_count, orders_count=orders_count,
                           pending_orders=pending_orders)


@app.route('/admin/products')
@requires_auth
def admin_products():
    products = Session.query(Product).order_by(Product.id.desc()).all()
    return render_template('admin/products.html', products=products)


@app.route('/admin/orders')
@requires_auth
def admin_orders():
    try:
        orders = Session.query(Order).order_by(Order.created_at.desc()).all()
        for order in orders:
            if isinstance(order.items, str):
                order.items = json.loads(order.items)
        return render_template('admin/orders.html', orders=orders)
    except Exception as e:
        logger.error(f"Ошибка получения списка заказов: {e}", exc_info=True)
        flash("Не удалось загрузить список заказов.", "danger")
        return render_template('admin/orders.html', orders=[])


@app.route('/admin/product/add', methods=['GET', 'POST'])
@requires_auth
def add_product():
    if request.method == 'POST':
        try:
            image_url = ""
            if 'image_file' in request.files and request.files['image_file'].filename != '':
                image_file = request.files['image_file']
                image_url = upload_to_imgbb(image_file)
            else:
                image_url = request.form.get('image_url', '').strip()

            if not image_url:
                flash("Нужно либо загрузить файл, либо указать URL картинки.", "warning")
                return redirect(url_for('add_product'))

            new_product = Product(
                name=request.form['name'], category=request.form['category'], brand=request.form['brand'],
                size=request.form['size'], price=int(request.form['price']), description=request.form['description'],
                composition=request.form.get('composition'), image_url=image_url,
                is_active=1 if 'is_active' in request.form else 0
            )
            Session.add(new_product)
            Session.commit()
            flash(f"Товар '{new_product.name}' успешно добавлен!", "success")
            return redirect(url_for('admin_products'))
        except Exception as e:
            Session.rollback()
            logger.error(f"Ошибка при добавлении товара: {e}", exc_info=True)
            flash(f"Ошибка при добавлении товара: {e}", "danger")

    return render_template('admin/product_form.html', title="Добавить товар", product=None)


@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@requires_auth
def edit_product(product_id):
    product = Session.query(Product).get(product_id)
    if not product: abort(404)

    if request.method == 'POST':
        try:
            image_url = product.image_url
            if 'image_file' in request.files and request.files['image_file'].filename != '':
                image_file = request.files['image_file']
                image_url = upload_to_imgbb(image_file)
            elif request.form.get('image_url'):
                image_url = request.form.get('image_url').strip()

            product.name = request.form['name'];
            product.category = request.form['category'];
            product.brand = request.form['brand']
            product.size = request.form['size'];
            product.price = int(request.form['price']);
            product.description = request.form['description']
            product.composition = request.form.get('composition');
            product.image_url = image_url
            product.is_active = 1 if 'is_active' in request.form else 0

            Session.commit()
            flash(f"Товар '{product.name}' успешно обновлен!", "success")
            return redirect(url_for('admin_products'))
        except Exception as e:
            Session.rollback()
            logger.error(f"Ошибка при редактировании товара {product_id}: {e}", exc_info=True)
            flash(f"Ошибка при редактировании товара: {e}", "danger")

    return render_template('admin/product_form.html', title="Редактировать товар", product=product)


@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@requires_auth
def delete_product(product_id):
    product = Session.query(Product).get(product_id)
    if not product: abort(404)

    try:
        Session.delete(product)
        Session.commit()
        flash(f"Товар '{product.name}' успешно удален.", "success")
    except Exception as e:
        Session.rollback()
        logger.error(f"Ошибка удаления товара {product_id}: {e}", exc_info=True)
        flash(f"Ошибка удаления товара: {e}", "danger")

    return redirect(url_for('admin_products'))


@app.route('/admin/order/update/<int:order_id>', methods=['POST'])
@requires_auth
def update_order_route(order_id):
    try:
        order = Session.query(Order).get(order_id)
        if order:
            order.status = request.form['status']
            order.track_number = request.form.get('track_number', '').strip()
            Session.commit()
            flash(f"Статус заказа #{order_id} успешно обновлен.", "success")
        else:
            flash(f"Заказ #{order_id} не найден.", "warning")
    except (SQLAlchemyError, KeyError) as e:
        Session.rollback()
        logger.error(f"Ошибка обновления заказа #{order_id}: {e}", exc_info=True)
        flash("Произошла ошибка при обновлении заказа.", "danger")
    return redirect(url_for('admin_orders'))