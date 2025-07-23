# database.py - ФИНАЛЬНАЯ ВЕРСИЯ С ВАРИАНТАМИ ТОВАРОВ

import os
import logging
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (create_engine, Column, Integer, String, JSON, DateTime,
                        func, Text, ForeignKey, inspect)
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship, scoped_session

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

DB_NAME = 'vip_sneaker.db'
DATABASE_PATH = os.path.join(BASE_DIR, DB_NAME)
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

logger.info(f"Используется путь к БД: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()


# --- Новые модели данных ---
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String(100))
    full_name = Column(String(200))


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    brand = Column(String(50), index=True)
    category = Column(String(50), index=True)
    description = Column(Text)
    composition = Column(Text, nullable=True)
    image_url = Column(String(200))
    is_active = Column(Integer, default=1)

    # Связь с вариантами товара
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = 'product_variants'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    size = Column(String(10), nullable=False)
    price = Column(Integer, nullable=False)
    stock = Column(Integer, default=0, nullable=False)

    # Обратная связь
    product = relationship("Product", back_populates="variants")


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


# --- Управление сессиями ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback();
        raise
    finally:
        session.close()


def get_scoped_session():
    return scoped_session(SessionLocal)


# --- Функции инициализации ---
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы успешно проверены/созданы.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}", exc_info=True)
        return False


def add_test_products(session):
    # Создаем основной товар
    product1 = Product(name="Nike Air Jordan 1", brand="Nike", category="sneakers", description="Классика",
                       image_url="https://static.nike.com/a/images/t_PDP_1728_v1/f_auto,q_auto:eco/af53d53d-561f-450a-a483-70a7ceee380f/air-jordan-1-mid-shoes-1zMCFJ.png",
                       composition="Кожа, резина")

    # Создаем варианты для него
    variant1_1 = ProductVariant(product=product1, size="41", price=12000, stock=5)
    variant1_2 = ProductVariant(product=product1, size="42", price=12000, stock=10)
    variant1_3 = ProductVariant(product=product1, size="43", price=12500, stock=0)  # Нет в наличии

    # Создаем второй товар
    product2 = Product(name="Футболка Supreme", brand="Supreme", category="clothing", description="Box Logo",
                       image_url="https://images.stockx.com/images/Supreme-Box-Logo-Tee-Black.jpg",
                       composition="100% хлопок")
    variant2_1 = ProductVariant(product=product2, size="M", price=5000, stock=3)
    variant2_2 = ProductVariant(product=product2, size="L", price=5000, stock=7)

    session.add_all([product1, variant1_1, variant1_2, variant1_3, product2, variant2_1, variant2_2])
    session.commit()


def init_db():
    try:
        if not create_tables(): return False
        with get_session() as session:
            if session.query(Product).count() == 0:
                logger.info("Добавление тестовых товаров...")
                add_test_products(session)
                logger.info("✅ Тестовые товары добавлены.")
            else:
                logger.info("✅ Товары уже есть в базе.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("--- Запуск ручной инициализации базы данных ---")
    if os.path.exists(DATABASE_PATH):
        logger.warning(f"Найден существующий файл БД. Удаляем для пересоздания...")
        os.remove(DATABASE_PATH)
    init_db()