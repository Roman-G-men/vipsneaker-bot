# bot.py - ВЕРСИЯ, СОВМЕСТИМАЯ С ЛОКАЛЬНЫМ main.py

import logging
import os
import asyncio
from contextlib import suppress
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext
)
from database import get_session, User, Order

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

if not TOKEN or not WEBAPP_URL:
    raise ValueError("Переменные TOKEN или WEBAPP_URL не найдены в .env файле!")
logger.info("✅ Конфигурация бота успешно загружена.")

# --- Текстовые константы ---
MAIN_MENU_TEXT = (
    "Sneaker SHOP — Продажа только оригинальных вещей\n"
    "Имеется более 2000 отзывов!\n"
    "Москва / Отправка транспортной компанией СДЭК\n\n"
    "Канал с наличием: https://t.me/+8Y8sxODeiQIyYTgy\n"
    "Связь / Покупка: @RSA57 / @che_rnila"
)


# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    try:
        with get_session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                new_user = User(
                    telegram_id=user_id,
                    username=update.effective_user.username or f"user_{user_id}",
                    full_name=update.effective_user.full_name or "Пользователь"
                )
                session.add(new_user)
                session.commit()
                logger.info(f"Создан новый пользователь: {user_id}")
    except Exception as e:
        logger.error(f"Критическая ошибка при регистрации пользователя {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Не удалось зарегистрировать вас в системе. Пожалуйста, попробуйте позже.")
        return
    await show_main_menu(update, user_id)


async def handle_message(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    if text == "📦 Мои заказы":
        await show_orders(update, update.effective_user.id)
    else:
        await show_main_menu(update, update.effective_user.id)


async def show_main_menu(update: Update, user_id: int) -> None:
    keyboard = [[KeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))],
                [KeyboardButton("📦 Мои заказы")]]
    await update.message.reply_text(MAIN_MENU_TEXT, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


async def show_orders(update: Update, user_id: int) -> None:
    try:
        with get_session() as session:
            orders = session.query(Order).filter_by(user_id=user_id).order_by(Order.created_at.desc()).limit(5).all()
            response = "📦 Ваши последние 5 заказов:\n\n" + "\n\n".join(
                [f"Заказ #{o.id} от {o.created_at.strftime('%d.%m.%Y')}\nСтатус: {o.status}" for o in
                 orders]) if orders else "У вас пока нет заказов."
        keyboard = [[KeyboardButton("🏠 На главную")]]
        await update.message.reply_text(response, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    except Exception as e:
        logger.error(f"Ошибка получения заказов для {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Не удалось загрузить историю заказов.")


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ Заказ успешно оформлен! С вами свяжутся для уточнения деталей.")


async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(f"Перехвачена ошибка: {context.error}", exc_info=True)
    if isinstance(update, Update) and update.effective_message:
        with suppress(Exception): await update.effective_message.reply_text("Произошла техническая ошибка.")


# <<< ВОТ ФУНКЦИЯ, КОТОРУЮ ИЩЕТ main.py >>>
async def run_bot_async():
    """Асинхронная функция, которая настраивает и запускает бота."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    application.add_error_handler(error_handler)

    logger.info("Запуск Telegram-бота в режиме polling...")
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        # Этот блок будет работать вечно, пока его не остановит main.py
        while True:
            await asyncio.sleep(3600)


# Этот блок нужен, чтобы можно было запустить bot.py отдельно для теста
if __name__ == "__main__":
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")