# run.py (СЕРВЕРНАЯ ВЕРСИЯ)
import sys
from pathlib import Path
import asyncio
import threading
import logging

# 1. Находим и добавляем путь к 'src'
SRC_DIR = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(SRC_DIR))

# 2. Импортируем наши компоненты уже после настройки пути
from bots.client_bot import create_client_bot_app
from bots.admin_bot import create_admin_bot_app
from database import init_db

# 3. Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def run_bot(bot_creator_func, bot_name):
    """
    Универсальная функция для запуска бота в новом цикле событий,
    адаптированная для сервера.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logging.info(f"Запуск {bot_name}...")
        app = bot_creator_func()

        # Запускаем run_polling БЕЗ обработки сигналов,
        # чтобы избежать ошибки 'set_wakeup_fd'
        loop.run_until_complete(
            app.run_polling(stop_signals=None)
        )

    except Exception as e:
        logging.error(f"Критическая ошибка в потоке {bot_name}: {e}", exc_info=True)
    finally:
        loop.close()


def main():
    """
    Главная функция, которая запускает ТОЛЬКО ботов.
    Веб-приложение запускается отдельно через WSGI.
    """
    init_db()
    logging.info("База данных инициализирована.")

    # Создаем и запускаем потоки для ботов
    client_bot_thread = threading.Thread(
        target=run_bot,
        args=(create_client_bot_app, "клиентского бота"),
        name="ClientBotThread"
    )
    admin_bot_thread = threading.Thread(
        target=run_bot,
        args=(create_admin_bot_app, "административного бота"),
        name="AdminBotThread"
    )

    client_bot_thread.daemon = True
    admin_bot_thread.daemon = True

    client_bot_thread.start()
    admin_bot_thread.start()

    logging.info("Боты запущены в фоновых потоках. Основной процесс продолжает работу.")

    # Этот цикл просто держит основной процесс живым
    client_bot_thread.join()
    admin_bot_thread.join()


if __name__ == "__main__":
    main()