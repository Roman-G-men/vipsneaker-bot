# main.py - ФИНАЛЬНАЯ ВЕРСИЯ, ЗАПУСКАЮЩАЯ ДВА БОТА И WEBAPP

from dotenv import load_dotenv

load_dotenv()

import threading
import time
import os
import logging
from sqlalchemy import text
from database import get_session, init_db
from bot import main as run_client_bot
from admin_bot import main as run_admin_bot
from webapp import app as web_app

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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

    if not init_db():
        logger.error("Не удалось инициализировать БД. Завершение работы.");
        exit(1)

    if not check_db_connection():
        logger.error("Не удалось подключиться к БД. Завершение работы.");
        exit(1)

    threads = []

    web_thread = threading.Thread(target=run_webapp, name="WebApp")
    client_bot_thread = threading.Thread(target=run_client_bot, name="ClientBot")
    admin_bot_thread = threading.Thread(target=run_admin_bot, name="AdminBot")

    for thread in [web_thread, client_bot_thread, admin_bot_thread]:
        thread.daemon = True
        thread.start()
        logger.info(f"Запущен поток: {thread.name}")

    logger.info("Все компоненты успешно запущены")
    try:
        while True:
            if not all(t.is_alive() for t in threads):
                logger.error("Один из потоков неожиданно завершился. Остановка приложения.")
                break
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя (Ctrl+C)")
    finally:
        logger.info(" ПРОЕКТ ОСТАНОВЛЕН ")