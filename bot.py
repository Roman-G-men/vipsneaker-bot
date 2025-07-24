# bot.py - КЛИЕНТСКИЙ БОТ (ПРОСТАЯ И НАДЕЖНАЯ ВЕРСИЯ)

import logging
import os
import json
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import get_session, User, Order

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

# --- Текстовые константы ---
MAIN_MENU_TEXT = (
    "Sneaker SHOP — Продажа только оригинальных вещей\n"
    "Имеется более 2000 отзывов!\n"
    "Москва / Отправка транспортной компанией СДЭК\n\n"
    "Канал с наличием: https://t.me/+8Y8sxODeiQIyYTgy\n"
    "Связь / Покупка: @VibeeAdmin / @kir_tg1"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает /start, регистрирует пользователя и показывает главное меню."""
    user_id = update.effective_user.id
    logger.info(f"Клиентский бот: Пользователь {user_id} запустил /start.")
    try:
        with get_session() as session:
            if not session.query(User).filter_by(telegram_id=user_id).first():
                new_user = User(telegram_id=user_id, username=update.effective_user.username or f"user_{user_id}",
                                full_name=update.effective_user.full_name or "Пользователь")
                session.add(new_user)
                session.commit()
                logger.info(f"Клиентский бот: Создан новый пользователь: {user_id}")
    except Exception as e:
        logger.error(f"Клиентский бот: Ошибка регистрации пользователя {user_id}: {e}", exc_info=True)

    keyboard = [[KeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))],
                [KeyboardButton("📦 Мои заказы")]]
    await update.message.reply_text(MAIN_MENU_TEXT, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


async def my_orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает пользователю его заказы."""
    user_id = update.effective_user.id
    logger.info(f"Клиентский бот: Пользователь {user_id} запросил 'Мои заказы'.")
    with get_session() as session:
        orders = session.query(Order).filter_by(user_id=user_id).order_by(Order.created_at.desc()).limit(5).all()
    if not orders:
        await update.message.reply_text("У вас пока нет оформленных заказов.");
        return

    response = "📦 **Ваши последние 5 заявок/заказов:**\n\n"
    for order in orders:
        items_list = json.loads(order.items)
        items_text = ", ".join([f"{item['name']} ({item['size']})" for item in items_list])
        response += f"**Заказ #{order.id}** от {order.created_at.strftime('%d.%m.%Y')}\nСтатус: `{order.status}`\nСумма: {order.total_amount} руб.\n\n"
    await update.message.reply_text(response, parse_mode='Markdown')


async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принимает данные из Mini App и создает заказ."""
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user
        if data.get('type') == 'newOrder':
            with get_session() as session:
                new_order = Order(user_id=user.id, items=json.dumps(data.get('items')),
                                  total_amount=data.get('total_price'), status='Обработка')
                session.add(new_order);
                session.commit()
                order_id = new_order.id

            items_list = data.get('items', [])
            preview_image_url = items_list[0].get('image_url') if items_list else None
            order_text = f"📝 **Сформирована заявка на заказ #{order_id}**\n\n" + "**Состав:**\n" + "\n".join(
                [f" • {i.get('name')} ({i.get('size')})" for i in items_list])
            order_text += f"\n\n**Итого:** {data.get('total_price')} руб.\n\n" + "👇 **Для оформления заказа... перешлите это сообщение менеджеру:**\n" + "➡️ @VibeeAdmin или @kir_tg1"
            if preview_image_url:
                await update.message.reply_photo(photo=preview_image_url, caption=order_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(order_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Клиентский бот: Ошибка обработки WebApp данных: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при формировании заказа. Свяжитесь с @VibeeAdmin")


def main():
    """Основная функция для запуска клиентского бота."""
    if not TOKEN:
        logger.critical("Токен клиентского бота (TOKEN) не найден!")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(MessageHandler(filters.Regex('^📦 Мои заказы$'), my_orders_handler))

    logger.info("Клиентский бот VIPSneakerBot_bot запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()