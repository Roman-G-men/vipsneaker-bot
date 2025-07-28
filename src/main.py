# src/main.py
import threading
import logging
import asyncio  # <-- Добавляем импорт asyncio
from urllib.parse import urlparse

# Импорты из нашего проекта
import config
from bots.client_bot import create_client_bot_app
from bots.admin_bot import create_admin_bot_app
from webapp import create_app
from database import init_db


def run_flask():
    """Запускает веб-приложение Flask, считывая хост и порт из конфига."""
    try:
        parsed_url = urlparse(config.WEBAPP_URL)
        host = parsed_url.hostname or '127.0.0.1'
        port = int(parsed_url.port or 5000)

        app = create_app()
        logging.info(f"Запуск Flask-приложения на http://{host}:{port}")
        app.run(host=host, port=port)
    except Exception as e:
        logging.error(f"Критическая ошибка в потоке Flask: {e}", exc_info=True)


def run_bot(bot_creator_func, bot_name):
    """Универсальная функция для запуска бота в новом цикле событий."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logging.info(f"Запуск {bot_name}...")
        app = bot_creator_func()
        loop.run_until_complete(app.run_polling())

    except Exception as e:
        logging.error(f"Критическая ошибка в потоке {bot_name}: {e}", exc_info=True)
    finally:
        loop.close()


def main():
    """Главная функция, которая инициализирует и запускает все компоненты."""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    init_db()

    flask_thread = threading.Thread(target=run_flask, name="FlaskThread")
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

    flask_thread.daemon = True
    client_bot_thread.daemon = True
    admin_bot_thread.daemon = True

    flask_thread.start()
    client_bot_thread.start()
    admin_bot_thread.start()

    print("Система запущена. Нажмите Ctrl+C для остановки.")

    try:
        while True:
            if not client_bot_thread.is_alive() or not admin_bot_thread.is_alive():
                logging.warning("Один из потоков бота завершил работу. Проверьте логи.")
                break
            threading.Event().wait(1)

    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки (Ctrl+C). Завершение работы...")
    finally:
        print("Программа завершена.")


if __name__ == "__main__":
    main()