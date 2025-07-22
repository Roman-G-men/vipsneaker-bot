from dotenv import load_dotenv

load_dotenv()

from database import init_db

if __name__ == '__main__':
    print("Инициализация базы данных...")
    if init_db():
        print("✅ База данных успешно инициализирована")
    else:
        print("❌ Ошибка инициализации базы данных")