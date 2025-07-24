# admin_bot.py - ОТДЕЛЬНЫЙ, НАДЕЖНЫЙ БОТ ДЛЯ АДМИНИСТРИРОВАНИЯ

import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from database import get_session, Product, ProductVariant

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_IDS = [8141146399, ]


def admin_only(func):
    """Декоратор для проверки прав администратора."""

    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("Это не ваш админ-бот.", show_alert=True)
            else:
                await update.message.reply_text("⛔️ Вы не являетесь администратором.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню админки."""
    keyboard = [[InlineKeyboardButton("📝 Список товаров", callback_data="admin_list_0")]]
    await update.message.reply_text("Админ-панель VibeResell:", reply_markup=InlineKeyboardMarkup(keyboard))


async def list_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает список товаров с пагинацией."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[-1])

    with get_session() as session:
        per_page = 5;
        offset = page * per_page
        products = session.query(Product).order_by(Product.id.desc()).limit(per_page).offset(offset).all()
        total_products = session.query(Product).count()
        total_pages = -(-total_products // per_page) if total_products > 0 else 1

    message_text = f"Товары (Стр. {page + 1}/{total_pages}):"
    keyboard = []
    if not products:
        message_text = "В каталоге пока нет товаров."
    else:
        for product in products:
            keyboard.append([InlineKeyboardButton(f"#{product.id} {product.name}",
                                                  callback_data=f"admin_view_{product.id}_{page}")])

    pagination_buttons = []
    if page > 0: pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"admin_list_{page - 1}"))
    if (page + 1) * per_page < total_products: pagination_buttons.append(
        InlineKeyboardButton("➡️", callback_data=f"admin_list_{page + 1}"))
    if pagination_buttons: keyboard.append(pagination_buttons)

    await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def view_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию о товаре и кнопку удаления."""
    query = update.callback_query
    await query.answer()
    _, _, product_id, page = query.data.split('_')
    with get_session() as session:
        product = session.query(Product).get(product_id)
    if not product:
        await query.edit_message_text("Товар не найден.");
        return
    variants_text = "\n".join([f"- {v.size}, {v.price} руб, {v.stock} шт." for v in product.variants])
    text = f"**Товар #{product.id}**: {product.name}\n\n{variants_text}"
    keyboard = [
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"admin_delete_confirm_{product.id}_{page}")],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data=f"admin_list_{page}")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def delete_product_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает подтверждение на удаление."""
    query = update.callback_query
    await query.answer()
    _, _, _, product_id, page = query.data.split('_')
    keyboard = [
        [InlineKeyboardButton("✅ ДА, УДАЛИТЬ", callback_data=f"admin_delete_execute_{product_id}")],
        [InlineKeyboardButton("❌ НЕТ", callback_data=f"admin_view_{product_id}_{page}")]
    ]
    await query.edit_message_text(f"Удалить товар #{product_id}?", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_product_execute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Окончательно удаляет товар."""
    query = update.callback_query
    product_id = int(query.data.split('_')[-1])
    with get_session() as session:
        product = session.query(Product).get(product_id)
        if product:
            session.delete(product);
            session.commit()
            await query.answer(f"Товар удален!", show_alert=True)
            # Возвращаемся к списку, "обманув" систему
            query.data = "admin_list_0"
            await list_products_callback(update, context)
        else:
            await query.answer("Товар уже был удален.", show_alert=True)


def main():
    """Основная функция для запуска админ-бота."""
    if not ADMIN_BOT_TOKEN:
        logger.critical("Токен админ-бота (ADMIN_BOT_TOKEN) не найден!")
        return

    application = Application.builder().token(ADMIN_BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))

    # Инлайн-кнопки
    application.add_handler(CallbackQueryHandler(list_products_callback, pattern='^admin_list_'))
    application.add_handler(CallbackQueryHandler(view_product_callback, pattern='^admin_view_'))
    application.add_handler(CallbackQueryHandler(delete_product_confirm_callback, pattern='^admin_delete_confirm_'))
    application.add_handler(CallbackQueryHandler(delete_product_execute_callback, pattern='^admin_delete_execute_'))

    logger.info("Админ-бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()