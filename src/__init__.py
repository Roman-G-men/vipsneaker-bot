# src/webapp/__init__.py
from flask import Flask
from config import FLASK_SECRET_KEY
import logging


def create_app():
    # Указываем, что папки static и templates находятся в этой же директории
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_mapping(
        SECRET_KEY=FLASK_SECRET_KEY,
    )

    # Отключаем кеширование для разработки, чтобы изменения в JS/CSS применялись сразу
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    logging.getLogger('werkzeug').setLevel(logging.ERROR)  # Убираем лишние логи от Flask

    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)

    return app