# src/config.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Находим путь к корню проекта (поднимаемся на один уровень из `src/`)
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env, который лежит в корне
# Убедитесь, что файл .env существует в папке 'Bot'
load_dotenv(BASE_DIR / '.env')

# --- Основные настройки ---
TOKEN = os.getenv('TOKEN')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

# --- Настройки администраторов ---
try:
    # Разделяем строку с ID по запятым и преобразуем в целые числа
    # Пример в .env: ADMIN_IDS=123456,789012
    ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '')
    if ADMIN_IDS_STR:
        ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    else:
        ADMIN_IDS = []
except (AttributeError, ValueError) as e:
    print(f"ПРЕДУПРЕЖДЕНИЕ: Не удалось прочитать ADMIN_IDS из .env файла. Ошибка: {e}. Убедитесь, что они указаны правильно.")
    ADMIN_IDS = []

# --- Настройки базы данных ---
# Формируем путь к файлу БД относительно корня проекта
DATABASE_URL = f"sqlite:///{BASE_DIR / 'vibesresell.db'}"

# --- Проверка критически важных переменных ---
if not TOKEN:
    print("КРИТИЧЕСКАЯ ОШИБКА: TOKEN не найден в .env файле!")
if not ADMIN_BOT_TOKEN:
    print("КРИТИЧЕСКАЯ ОШИБКА: ADMIN_BOT_TOKEN не найден в .env файле!")
if not ADMIN_IDS:
    print("ПРЕДУПРЕЖДЕНИЕ: ADMIN_IDS не указаны в .env файле. Админ-бот не будет работать для вас.")