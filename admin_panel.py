import os
import logging
from flask import Flask, render_template, request, redirect, url_for, Response, flash
from sqlalchemy.exc import SQLAlchemyError
from database import get_scoped_session, Product, Order # Используем scoped_session для Flask

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
# Этот блок больше не нужен, так как main.py уже все загружает
# from dotenv import load_dotenv
# load_dotenv()

app = Flask(__name__)
# Устанавливаем секретный ключ для работы флеш-сообщений
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development')

# Конфигурация авторизации
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'secret123')

# Получаем сессию
Session = get_scoped_session()

# Декоратор для автоматического управления сессиями
@app.teardown_request
def remove_session(ex=None):
    Session.remove()

def check_auth(username, password):
    """Проверяет логин и пароль"""
    return username == ADMIN_USER and password == ADMIN_PASSWORD

def authenticate():
    """Отправляет ответ с требованием авторизации"""
    return Response(
        'Требуется авторизация для доступа к админ-панели',
        401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(func):
    """Декоратор для защиты роутов"""
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return func(*args, **kwargs)
    return decorated

@app.route('/admin', endpoint='admin_dashboard_route')
@requires_auth
def admin_dashboard():
    try:
        products_count = Session.query(Product).count()
        orders_count = Session.query(Order).count()
        pending_orders = Session.query(Order).filter_by(status='Обработка').count()

        return render_template(
            'admin_dashboard.html',
            products_count=products_count,
            orders_count=orders_count,
            pending_orders=pending_orders
        )
    except SQLAlchemyError as e:
        logger.error(f"Ошибка получения статистики для админки: {e}", exc_info=True)
        flash("Ошибка при загрузке данных для панели управления.", "danger")
        return render_template('admin_dashboard.html', products_count=0, orders_count=0, pending_orders=0)

@app.route('/admin/products', endpoint='admin_products_route')
@requires_auth
def admin_products():
    try:
        products = Session.query(Product).order_by(Product.id.desc()).all()
        return render_template('admin_products.html', products=products)
    except SQLAlchemyError as e:
        logger.error(f"Ошибка получения списка товаров: {e}", exc_info=True)
        flash("Не удалось загрузить список товаров.", "danger")
        return render_template('admin_products.html', products=[])

@app.route('/admin/orders', endpoint='admin_orders_route')
@requires_auth
def admin_orders():
    try:
        orders = Session.query(Order).order_by(Order.created_at.desc()).all()
        return render_template('admin_orders.html', orders=orders)
    except SQLAlchemyError as e:
        logger.error(f"Ошибка получения списка заказов: {e}", exc_info=True)
        flash("Не удалось загрузить список заказов.", "danger")
        return render_template('admin_orders.html', orders=[])

@app.route('/admin/order/update/<int:order_id>', methods=['POST'], endpoint='update_order_route')
@requires_auth
def update_order(order_id):
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
    return redirect(url_for('admin_orders_route'))

@app.route('/admin/product/delete/<int:product_id>', endpoint='delete_product_route')
@requires_auth
def delete_product(product_id):
    try:
        product = Session.query(Product).get(product_id)
        if product:
            Session.delete(product)
            Session.commit()
            flash(f"Товар '{product.name}' успешно удален.", "success")
        else:
            flash(f"Товар #{product_id} не найден.", "warning")
    except SQLAlchemyError as e:
        Session.rollback()
        logger.error(f"Ошибка удаления товара #{product_id}: {e}", exc_info=True)
        flash("Произошла ошибка при удалении товара.", "danger")
    return redirect(url_for('admin_products_route'))

@app.route('/admin/product/add', methods=['POST'], endpoint='add_product_route')
@requires_auth
def add_product():
    try:
        # Валидация цены
        try:
            price = int(request.form['price'])
            if price < 0:
                raise ValueError("Цена не может быть отрицательной")
        except (ValueError, KeyError):
            flash("Неверный формат цены.", "danger")
            return redirect(url_for('admin_products_route'))

        new_product = Product(
            name=request.form['name'].strip(),
            category=request.form['category'],
            brand=request.form['brand'].strip(),
            size=request.form['size'].strip(),
            price=price,
            description=request.form['description'].strip(),
            image_url=request.form['image_url'].strip()
        )
        Session.add(new_product)
        Session.commit()
        flash(f"Товар '{new_product.name}' успешно добавлен.", "success")
    except SQLAlchemyError as e:
        Session.rollback()
        logger.error(f"Ошибка добавления товара: {e}", exc_info=True)
        flash("Произошла ошибка при добавлении товара.", "danger")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при добавлении товара: {e}", exc_info=True)
        flash("Произошла непредвиденная ошибка.", "danger")
    return redirect(url_for('admin_products_route'))