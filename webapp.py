# webapp.py - ПОЛНАЯ ВЕРСИЯ С АДМИН-ПАНЕЛЬЮ И IMGBB

import logging
import json
import os
import requests
from flask import Flask, render_template, request, jsonify, Response, flash, redirect, url_for
from sqlalchemy.exc import SQLAlchemyError
from database import get_scoped_session, Product, Order

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ImgBB ---
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

app = Flask(__name__)
# Убедитесь, что SECRET_KEY установлен для работы flash-сообщений
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development')
app.config['TEMPLATES_AUTO_RELOAD'] = True

Session = get_scoped_session()


@app.teardown_request
def remove_session(ex=None):
    """Автоматически закрывает сессию после каждого запроса."""
    Session.remove()


# --- АДМИН-ПАНЕЛЬ: АУТЕНТИФИКАЦИЯ ---
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret123')


def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASSWORD


def authenticate():
    return Response('Требуется авторизация.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    decorated.__name__ = f.__name__  # Важно для Flask
    return decorated


# --- МАРШРУТЫ МАГАЗИНА ---
@app.route('/')
def index():
    user_id = request.args.get('user_id', '')
    products = Session.query(Product).filter_by(is_active=1).order_by(Product.name).all()
    return render_template('index.html', products=products, user_id=user_id)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    user_id = request.args.get('user_id', '')
    product = Session.query(Product).filter_by(id=product_id, is_active=1).first_or_404()
    return render_template('product.html', product=product, user_id=user_id)


@app.route('/cart')
def cart_page():
    user_id = request.args.get('user_id', '')
    return render_template('cart.html', user_id=user_id)


@app.route('/create_order', methods=['POST'])
def create_order():
    # ... (код без изменений) ...
    return jsonify({"status": "success", "order_id": 123})


# --- МАРШРУТЫ АДМИН-ПАНЕЛИ ---
def upload_to_imgbb(image_file):
    """Функция для загрузки изображения на ImgBB."""
    if not IMGBB_API_KEY:
        raise ValueError("IMGBB_API_KEY не установлен в .env файле!")

    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": (image_file.filename, image_file.read(), image_file.mimetype)}

    response = requests.post(url, data=payload, files=files)
    response.raise_for_status()  # Вызовет ошибку, если запрос неудачный

    result = response.json()
    if result.get("success"):
        logger.info(f"Изображение успешно загружено: {result['data']['url']}")
        return result["data"]["url"]
    else:
        error_message = result.get('error', {}).get('message', 'Неизвестная ошибка ImgBB')
        logger.error(f"Ошибка загрузки на ImgBB: {error_message}")
        raise Exception(f"Ошибка ImgBB: {error_message}")


@app.route('/admin')
@requires_auth
def admin_dashboard():
    products_count = Session.query(Product).count()
    orders_count = Session.query(Order).count()
    return render_template('admin/dashboard.html', products_count=products_count, orders_count=orders_count)


@app.route('/admin/products')
@requires_auth
def admin_products():
    products = Session.query(Product).order_by(Product.id.desc()).all()
    return render_template('admin/products.html', products=products)


@app.route('/admin/product/add', methods=['GET', 'POST'])
@requires_auth
def add_product():
    if request.method == 'POST':
        try:
            image_url = ""
            # Проверяем, был ли загружен файл
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
    product = Session.query(Product).get_or_404(product_id)
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
    product = Session.query(Product).get_or_404(product_id)
    Session.delete(product)
    Session.commit()
    flash(f"Товар '{product.name}' успешно удален.", "success")
    return redirect(url_for('admin_products'))