# src/webapp/__init__.py
from flask import Flask
from config import FLASK_SECRET_KEY
import logging


def create_app():
    # Указываем, что папки static и templates находятся относительно этого файла
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_mapping(
        SECRET_KEY=FLASK_SECRET_KEY,
    )
    logging.basicConfig(level=logging.INFO)

    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)

    return app