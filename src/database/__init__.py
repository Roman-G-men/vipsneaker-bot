# src/database/__init__.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    # Импортируем модели здесь, чтобы избежать циклических зависимостей
    from database import models
    print("Инициализация базы данных...")
    Base.metadata.create_all(bind=engine)
    print("База данных успешно инициализирована.")