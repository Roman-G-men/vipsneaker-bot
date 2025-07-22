from dotenv import load_dotenv

load_dotenv()

import threading
import time
import os
import logging
import asyncio
from sqlalchemy import text
from database import get_session, init_db
from bot import run_bot_async
from webapp import app as web_app
from admin_panel import app as admin_app

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Константы ---
WEBAPP_PORT = 5000
ADMIN_PORT = 5001


def check_db_connection():
    """Проверка подключения к базе данных"""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        logger.info("✅ Проверка подключения к БД успешна")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {str(e)}", exc_info=True)
        return False


def run_webapp():
    logger.info(f"Запуск основного веб-приложения на порту {WEBAPP_PORT}")
    web_app.run(host='0.0.0.0', port=WEBAPP_PORT, use_reloader=False)


def run_admin_panel():
    logger.info(f"Запуск админ-панели на порту {ADMIN_PORT}")
    admin_app.run(host='0.0.0.0', port=ADMIN_PORT, use_reloader=False)


def run_telegram_bot_thread():
    """Обертка для запуска асинхронного бота в отдельном потоке."""
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

    # Критически важная проверка
    if not os.getenv("WEBAPP_URL") or not os.getenv("WEBAPP_URL").startswith("https"):
        logger.critical("❌ URL для WebApp не найден или не является HTTPS!")
        logger.critical("Пожалуйста, запустите тоннель (например, cloudflared) и добавьте WEBAPP_URL в .env файл.")
        exit(1)

    logger.info(f"Используется публичный URL: {os.getenv('WEBAPP_URL')}")

    if not init_db():
        logger.error("Не удалось инициализировать БД. Завершение работы.")
        exit(1)

    if not check_db_connection():
        logger.error("Не удалось подключиться к БД. Завершение работы.")
        exit(1)

    threads = []
    web_thread = threading.Thread(target=run_webapp, name="WebApp")
    admin_thread = threading.Thread(target=run_admin_panel, name="AdminPanel")
    bot_thread = threading.Thread(target=run_telegram_bot_thread, name="TelegramBot")

    for thread in [web_thread, admin_thread, bot_thread]:
        thread.daemon = True
        thread.start()

    logger.info("Все компоненты успешно запущены")
    try:
        while True:
            if not bot_thread.is_alive():
                logger.error("Поток бота неожиданно завершился. Завершение работы.")
                break
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя (Ctrl+C)")
    finally:
        logger.info(" ПРОЕКТ ОСТАНОВЛЕН ")