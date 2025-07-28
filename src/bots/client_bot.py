# src/bots/client_bot.py
import json
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config  # <--- Вот эта строка
from database import SessionLocal
from database import queries
from services import order_processor
from utils.helpers import format_order_message

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        user = queries.get_or_create_user(db, update.effective_user)
        logger.info(f"Пользователь {user.telegram_id} запустил бота.")
    finally:
        db.close()

    keyboard = [
        [KeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url=config.WEBAPP_URL))],
        [KeyboardButton("📦 Мои заказы")]
    ]
    text = (
        "Sneaker SHOP — Продажа только оригинальных вещей\n"
        "Имеется более 2000 отзывов!\n"
        "Москва / Отправка транспортной компанией СДЭК\n\n"
        "Канал с наличием: https://t.me/+8Y8sxODeiQIyYTgy\n"
        "Связь / Покупка: @VibeeAdmin / @kir_tg1"
    )
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        user = queries.get_or_create_user(db, update.effective_user)
        orders = queries.get_user_orders(db, user)
        if not orders:
            await update.message.reply_text("У вас пока нет заказов.")
            return

        response_text = "<b>Ваши последние 5 заказов:</b>\n\n"
        for order in orders:
            response_text += (
                f"<b>Заказ №{order.id}</b> от {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Статус: <i>{order.status}</i>\n"
                f"Сумма: {order.total_amount:.2f} ₽\n"
                "--------------------\n"
            )
        await update.message.reply_html(response_text)
    finally:
        db.close()


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = json.loads(update.effective_message.web_app_data.data)
    if data.get('event') == 'newOrder':
        order_data = data.get('data', {})
        items = order_data.get('items', [])
        if not items:
            logger.warning(f"Получен пустой заказ от {update.effective_user.id}")
            return

        db = SessionLocal()
        try:
            user = queries.get_or_create_user(db, update.effective_user)
            new_order = order_processor.process_new_order(db, user, order_data)

            if new_order:
                caption, photo_url = format_order_message(new_order, items)
                if photo_url:
                    await context.bot.send_photo(chat_id=user.telegram_id, photo=photo_url, caption=caption,
                                                 parse_mode='HTML')
                else:
                    await context.bot.send_message(chat_id=user.telegram_id, text=caption, parse_mode='HTML')
                logger.info(f"Создан заказ #{new_order.id} для пользователя {user.telegram_id}")
            else:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text="Произошла ошибка при оформлении заказа. Возможно, некоторых товаров уже нет в наличии. Пожалуйста, попробуйте снова."
                )

        except Exception as e:
            logger.error(f"Критическая ошибка обработки web_app_data: {e}", exc_info=True)
            await update.message.reply_text("Произошла внутренняя ошибка при оформлении заказа. Попробуйте позже.")
        finally:
            db.close()


def create_client_bot_app():
    application = Application.builder().token(config.TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^📦 Мои заказы$'), my_orders))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    return application