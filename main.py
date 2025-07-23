# main.py - ФИНАЛЬНАЯ ВЕРСИЯ ДЛЯ РАБОТЫ С ВНЕШНИМ ТОННЕЛЕМ (Cloudflared)

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

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Константы ---
WEBAPP_PORT = 5000
ADMIN_PORT = 5001  # Админка теперь часть webapp, но порт может быть полезен


def check_db_connection():
    """Проверка подключения к базе данных."""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        logger.info("✅ Проверка подключения к БД успешна")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {str(e)}", exc_info=True)
        return False


def run_webapp():
    """Запуск веб-приложения (магазин + админка)."""
    logger.info(f"Запуск веб-приложения на порту {WEBAPP_PORT}")
    # Важно: мы запускаем только один Flask app, который содержит и магазин, и админку
    web_app.run(host='0.0.0.0', port=WEBAPP_PORT, use_reloader=False)


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

    # Критически важная проверка URL из .env файла
    webapp_url = os.getenv("WEBAPP_URL")
    if not webapp_url or not webapp_url.startswith("https"):
        logger.critical("=" * 50)
        logger.critical("❌ ОШИБКА: WEBAPP_URL не найден или не является HTTPS!")
        logger.critical("1. Запустите `cloudflared tunnel --url http://localhost:5000` в отдельном терминале.")
        logger.critical("2. Скопируйте полученный https-адрес.")
        logger.critical("3. Вставьте его в файл .env и перезапустите проект.")
        logger.critical("=" * 50)
        exit(1)

    logger.info(f"Используется публичный URL: {webapp_url}")

    if not init_db():
        logger.error("Не удалось инициализировать БД. Завершение работы.")
        exit(1)

    if not check_db_connection():
        logger.error("Не удалось подключиться к БД. Завершение работы.")
        exit(1)

    # Запускаем всего два потока
    threads = []

    web_thread = threading.Thread(target=run_webapp, name="WebApp")
    bot_thread = threading.Thread(target=run_telegram_bot_thread, name="TelegramBot")

    for thread in [web_thread, bot_thread]:
        thread.daemon = True
        thread.start()
        logger.info(f"Запущен поток: {thread.name}")

    logger.info("Все компоненты успешно запущены")
    logger.info(f"Магазин доступен по публичному URL: {webapp_url}")
    logger.info(f"Админ-панель доступна локально: http://localhost:{WEBAPP_PORT}/admin")

    try:
        while True:
            # Проверяем, что все потоки живы
            if not all(t.is_alive() for t in threads):
                logger.error("Один из потоков неожиданно завершился. Остановка приложения.")
                break
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Завершение работы по запросу пользователя (Ctrl+C)")
    finally:
        logger.info(" ПРОЕКТ ОСТАНОВЛЕН ")