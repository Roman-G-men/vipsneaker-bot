# main.py - ФИНАЛЬНАЯ ВЕРСЯ С ПРАВИЛЬНЫМ ASYNCIO

from dotenv import load_dotenv

load_dotenv()

import threading
import time
import os
import logging
import asyncio
from sqlalchemy import text
from database import get_session, init_db
from bot import run_bot_async  # <<< Возвращаем импорт async функции
from webapp import app as web_app

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Константы ---
WEBAPP_PORT = 5000


def check_db_connection():
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        logger.info("✅ Проверка подключения к БД успешна")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {str(e)}", exc_info=True)
        return False


def run_webapp():
    logger.info(f"Запуск веб-приложения на порту {WEBAPP_PORT}")
    web_app.run(host='0.0.0.0', port=WEBAPP_PORT, use_reloader=False)


# <<< ВОЗВРАЩАЕМ ПРАВИЛЬНУЮ ФУНКЦИЮ-ОБЕРТКУ ДЛЯ ASYNCIO >>>
def run_telegram_bot_thread():
    """Обертка, которая создает и запускает event loop для асинхронной функции бота."""
    logger.info("Поток для Telegram-бота запущен.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot_async())
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка в потоке бота: {e}", exc_info=True)
    finally:
        loop.close()
        logger.info("Цикл событий Telegram-бота закрыт.")


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info(" ЗАПУСК ПРОЕКТА VIP SNEAKER BOT ")
    logger.info("=" * 50)

    webapp_url = os.getenv("WEBAPP_URL")
    if not webapp_url or not webapp_url.startswith("https"):
        logger.critical("=" * 50);
        logger.critical("❌ ОШИБКА: WEBAPP_URL не найден или не HTTPS!");
        logger.critical("1. Запустите `cloudflared`");
        logger.critical("2. Скопируйте https-адрес");
        logger.critical("3. Вставьте его в .env и перезапустите.");
        logger.critical("=" * 50)
        exit(1)

    init_db()
    check_db_connection()

    threads = []
    web_thread = threading.Thread(target=run_webapp, name="WebApp")
    bot_thread = threading.Thread(target=run_telegram_bot_thread, name="TelegramBot")

    for thread in [web_thread, bot_thread]:
        thread.daemon = True
        thread.start()
        logger.info(f"Запущен поток: {thread.name}")

    logger.info("Все компоненты успешно запущены")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя (Ctrl+C)")
    finally:
        logger.info(" ПРОЕКТ ОСТАНОВЛЕН ")