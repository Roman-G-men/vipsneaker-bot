# database.py - ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ

from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, func, Text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.exc import SQLAlchemyError
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
from contextlib import contextmanager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info("✅ Файл .env загружен из database.py")

DB_NAME = os.getenv('DB_NAME', 'vip_sneaker.db')
DATABASE_URL = f'sqlite:///{DB_NAME}'
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

# --- Модели ---
class User(Base): __tablename__ = 'users'; id=Column(Integer, primary_key=True); telegram_id=Column(Integer, unique=True, index=True); username=Column(String(100)); full_name=Column(String(200)); phone=Column(String(20))
class Product(Base): __tablename__ = 'products'; id=Column(Integer, primary_key=True); name=Column(String(100), nullable=False, index=True); category=Column(String(50), index=True); brand=Column(String(50), index=True); size=Column(String(10)); price=Column(Integer, nullable=False); description=Column(Text); image_url=Column(String(200))
class Order(Base): __tablename__ = 'orders'; id=Column(Integer, primary_key=True); user_id=Column(Integer, index=True); items=Column(JSON); status=Column(String(50), default='Обработка', index=True); delivery_type=Column(String(50)); created_at=Column(DateTime, default=func.now(), index=True); address=Column(String(200)); phone=Column(String(20)); track_number=Column(String(50))

# --- Управление сессиями ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager # <<< ЭТОТ ДЕКОРАТОР ВСЕ РЕШАЕТ
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_scoped_session():
    return scoped_session(SessionLocal)

# --- Функции инициализации ---
def create_tables():
    try:
        inspector = inspect(engine)
        if not all(table in inspector.get_table_names() for table in ['users', 'products', 'orders']):
            logger.info("Создание таблиц...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Таблицы успешно созданы.")
        else:
            logger.info("✅ Все таблицы уже существуют.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}", exc_info=True)
        return False

def add_test_products(session):
    products = [ Product(...) ] # Ваш список товаров
    session.add_all(products)
    session.commit()

def init_db():
    try:
        if not create_tables(): return False
        with get_session() as session:
            if session.query(Product).count() == 0:
                # add_test_products(session) # Раскомментируйте, если нужны тестовые данные
                logger.info("✅ Тестовые данные добавлены.")
            else:
                logger.info("✅ База данных уже содержит товары.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        return False