# database.py - ФИНАЛЬНАЯ ВЕРСИЯ С ИСПРАВЛЕННЫМ ИМПОРТОМ

import os
import logging
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (create_engine, Column, Integer, String, JSON, DateTime,
                        func, Text, inspect)
# <<< ИСПРАВЛЕНИЕ ЗДЕСЬ: Добавлен `scoped_session` в импорт >>>
from sqlalchemy.orm import sessionmaker, scoped_session, Session, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
# Этот код будет работать везде: и локально, и на PythonAnywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Загрузка .env файла из папки проекта
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"✅ Файл .env загружен из {env_path}")

DB_NAME = 'vip_sneaker.db'
DATABASE_PATH = os.path.join(BASE_DIR, DB_NAME)
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

logger.info(f"Используется путь к БД: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()


# --- Модели данных ---
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String(100))
    full_name = Column(String(200))
    phone = Column(String(20))


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), index=True)
    brand = Column(String(50), index=True)
    size = Column(String(10))
    price = Column(Integer, nullable=False)
    description = Column(Text)
    image_url = Column(String(200))
    is_active = Column(Integer, default=1)
    composition = Column(Text, nullable=True)


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    items = Column(JSON)
    status = Column(String(50), default='Обработка', index=True)
    delivery_type = Column(String(50))
    created_at = Column(DateTime, default=func.now(), index=True)
    total_amount = Column(Integer)
    address = Column(String(200))
    phone = Column(String(20))
    track_number = Column(String(50))


# --- Управление сессиями ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Session:
    """Контекстный менеджер для безопасной работы с сессией БД."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_scoped_session():
    """Возвращает scoped сессию, идеально для Flask."""
    return scoped_session(SessionLocal)


# --- Функции инициализации ---
def create_tables():
    """Создает все таблицы в базе данных."""
    try:
        logger.info("Проверка и создание таблиц...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы успешно проверены/созданы.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}", exc_info=True)
        return False


def add_test_products(session):
    """Добавление тестовых товаров в базу данных."""
    test_products = [
        Product(name="Nike Air Jordan 1", category="sneakers", brand="Nike", size="42", price=12000,
                description="Классические кроссовки Air Jordan 1",
                image_url="https://static.nike.com/a/images/t_PDP_1728_v1/f_auto,q_auto:eco/af53d53d-561f-450a-a483-70a7ceee380f/air-jordan-1-mid-shoes-1zMCFJ.png",
                composition="Верх: кожа. Подошва: резина."),
        Product(name="Adidas Yeezy Boost 350", category="sneakers", brand="Adidas", size="43", price=15000,
                description="Yeezy Boost 350 V2",
                image_url="https://assets.adidas.com/images/w_600,f_auto,q_auto/7a1c2c5c1e3a4a4d8c3aae8a00e5c8b3_9366/Yeezy_Boost_350_V2_Core_Black_Red_CP9652_01_standard.jpg",
                composition="Верх: Primeknit. Подошва: Boost."),
        Product(name="Футболка Supreme", category="clothing", brand="Supreme", size="M", price=5000,
                description="Оригинальная футболка Supreme Box Logo",
                image_url="https://images.stockx.com/images/Supreme-Box-Logo-Tee-Black.jpg", composition="100% хлопок")
    ]
    session.bulk_save_objects(test_products)
    session.commit()


def init_db():
    """Полный цикл инициализации БД: создание таблиц и добавление данных."""
    try:
        if not create_tables():
            return False

        with get_session() as session:
            if session.query(Product).count() == 0:
                logger.info("База данных пуста. Добавление тестовых товаров...")
                add_test_products(session)
                logger.info("✅ Тестовые товары добавлены.")
            else:
                logger.info("✅ Товары уже есть в базе.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        return False


# Этот блок позволяет запустить файл напрямую из консоли для создания/пересоздания БД
if __name__ == "__main__":
    logger.info("--- Запуск ручной инициализации базы данных ---")
    if os.path.exists(DATABASE_PATH):
        logger.warning(f"Найден существующий файл БД. Удаляем для пересоздания...")
        os.remove(DATABASE_PATH)

    init_db()