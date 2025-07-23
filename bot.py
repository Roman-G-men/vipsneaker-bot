# bot.py - ФИНАЛЬНАЯ, МАКСИМАЛЬНО УДОБНАЯ ВЕРСИЯ С ПРОФЕССИОНАЛЬНОЙ АДМИНКОЙ

import logging
import os
import io
import requests
import asyncio
from contextlib import suppress
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext, ConversationHandler,
    CallbackQueryHandler
)
from database import get_session, User, Order, Product, ProductVariant

# Настройка логирования для записи в файл на сервере
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.log')
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# ВАЖНО: Вставьте сюда свой Telegram User ID. Чтобы его узнать, напиши боту @userinfobot
ADMIN_IDS = [8141146399, ]

# --- Состояния для диалога ---
(ADD_NAME, ADD_BRAND, ADD_CATEGORY, ADD_DESCRIPTION, ADD_COMPOSITION, ADD_PHOTO, ADD_VARIANTS) = range(7)
CANCEL = ConversationHandler.END

# --- Текстовые константы ---
MAIN_MENU_TEXT = (
    "Sneaker SHOP — Продажа только оригинальных вещей\n"
    "Имеется более 2000 отзывов!\n"
    "Москва / Отправка транспортной компанией СДЭК\n\n"
    "Канал с наличием: https://t.me/+8Y8sxODeiQIyYTgy\n"
    "Связь / Покупка: @VibeeAdmin / @kir_tg1"
)
ADMIN_WELCOME_TEXT = "Добро пожаловать в админ-панель! Что вы хотите сделать?"
ADD_ITEM_START_TEXT = "Начинаем добавлять новый товар.\n\nШаг 1/7: Введите **название товара** (например, Nike Air Force 1).\n\nДля отмены в любой момент введите /cancel"
ADD_VARIANT_TEXT = "Отлично! Товар создан.\n\nФинальный шаг: **добавьте варианты** (размеры).\nОтправьте размер, цену и количество через пробел. Например: `42 12000 5`.\n\nКогда закончите добавлять размеры, отправьте /done"


# --- Утилиты ---
def admin_only(func):
    """Декоратор для проверки прав администратора."""

    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("Доступ запрещен.", show_alert=True)
            else:
                await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


def upload_to_imgbb(image_bytes, filename="photo.jpg"):
    """Функция для загрузки байтов изображения на ImgBB."""
    if not IMGBB_API_KEY: raise ValueError("IMGBB_API_KEY не установлен!")
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": (filename, image_bytes, "image/jpeg")}
    response = requests.post(url, data=payload, files=files)
    response.raise_for_status()
    result = response.json()
    if result.get("success"):
        logger.info(f"Изображение успешно загружено: {result['data']['url']}")
        return result["data"]["url"]
    else:
        raise Exception(f"Ошибка ImgBB: {result.get('error', {}).get('message', 'Неизвестная ошибка')}")


# --- КЛИЕНТСКАЯ ЧАСТЬ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    try:
        with get_session() as session:
            if not session.query(User).filter_by(telegram_id=user_id).first():
                new_user = User(
                    telegram_id=user_id,
                    username=update.effective_user.username or f"user_{user_id}",
                    full_name=update.effective_user.full_name or "Пользователь"
                )
                session.add(new_user)
                session.commit()
                logger.info(f"Создан новый пользователь: {user_id}")
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {user_id}: {e}", exc_info=True)
    await show_main_menu(update, user_id)


async def show_main_menu(update: Update, user_id: int) -> None:
    keyboard = [[KeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))],
                [KeyboardButton("📦 Мои заказы")]]
    await update.message.reply_text(MAIN_MENU_TEXT, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


# --- АДМИН-ПАНЕЛЬ: ГЛАВНОЕ МЕНЮ ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["➕ Добавить товар", "📝 Список товаров"], ["↩️ Выйти из админки"]]
    await update.message.reply_text(ADMIN_WELCOME_TEXT,
                                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ConversationHandler.END  # Завершаем любой предыдущий диалог


# --- Диалог добавления товара ---
@admin_only
async def add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product'] = {}
    await update.message.reply_text(ADD_ITEM_START_TEXT, parse_mode='Markdown')
    return ADD_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['name'] = update.message.text
    await update.message.reply_text("Шаг 2/7: Введите **бренд**:", parse_mode='Markdown')
    return ADD_BRAND


async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['brand'] = update.message.text
    keyboard = [["кроссовки", "одежда"]]
    await update.message.reply_text("Шаг 3/7: Выберите **категорию**:",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return ADD_CATEGORY


async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['category'] = update.message.text.lower()
    await update.message.reply_text("Шаг 4/7: Введите **описание** товара:",
                                    reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=False))  # Убирает кнопки
    return ADD_DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['description'] = update.message.text
    await update.message.reply_text("Шаг 5/7: Введите **состав** (или напишите 'нет'):")
    return ADD_COMPOSITION


async def get_composition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product'][
        'composition'] = update.message.text if update.message.text.lower() != 'нет' else None
    await update.message.reply_text("Шаг 6/7: Отлично! Теперь отправьте **главное фото** товара.")
    return ADD_PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        await update.message.reply_text("Загружаю фото, это может занять несколько секунд...")
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image_url = upload_to_imgbb(bytes(photo_bytes))
        context.user_data['new_product']['image_url'] = image_url
        await update.message.reply_text(ADD_VARIANT_TEXT, parse_mode='Markdown')
        return ADD_VARIANTS
    except Exception as e:
        logger.error(f"Ошибка на этапе фото: {e}", exc_info=True)
        await update.message.reply_text(f"Ошибка при обработке фото: {e}. Диалог отменен.")
        return await cancel_dialog(update, context)


async def get_variant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parts = update.message.text.split()
    if len(parts) != 3:
        await update.message.reply_text(
            "Неверный формат. Нужно три значения: `размер цена количество`. Например: `42 12000 5`. Попробуйте еще раз или отправьте /done.",
            parse_mode='Markdown')
        return ADD_VARIANTS
    try:
        size, price, stock = parts[0], int(parts[1]), int(parts[2])
        if 'variants' not in context.user_data['new_product']:
            context.user_data['new_product']['variants'] = []
        context.user_data['new_product']['variants'].append({'size': size, 'price': price, 'stock': stock})
        await update.message.reply_text(f"✅ Размер {size} добавлен. Введите следующий или /done для завершения.")
        return ADD_VARIANTS
    except ValueError:
        await update.message.reply_text("Цена и количество должны быть числами. Попробуйте еще раз.")
        return ADD_VARIANTS


async def done_adding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_data = context.user_data.get('new_product')
    if not product_data or not product_data.get('variants'):
        await update.message.reply_text("Вы не добавили ни одного варианта. Добавление отменено.")
        return await cancel_dialog(update, context)
    try:
        with get_session() as session:
            new_product = Product(
                name=product_data['name'], brand=product_data['brand'], category=product_data['category'],
                description=product_data['description'], composition=product_data.get('composition'),
                image_url=product_data['image_url'], is_active=1
            )
            for var_data in product_data['variants']:
                new_product.variants.append(ProductVariant(**var_data))
            session.add(new_product)
            session.commit()
            product_id = new_product.id
        await update.message.reply_text(
            f"✅ Товар '{new_product.name}' (ID: {product_id}) со всеми вариантами успешно сохранен!")
    except Exception as e:
        logger.error(f"Ошибка сохранения товара в БД: {e}", exc_info=True)
        await update.message.reply_text(f"Произошла ошибка при сохранении в базу данных: {e}")

    return await cancel_dialog(update, context)  # Завершаем и очищаем


async def cancel_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.")
    await admin_panel(update, context)
    return CANCEL


# --- Обработчик обычных сообщений ---
async def handle_regular_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "📦 Мои заказы":
        await update.message.reply_text("Раздел 'Мои заказы' в разработке.")
    elif text == "↩️ Выйти из админки":
        await start(update, context)
    else:
        await show_main_menu(update, update.effective_user.id)


async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(f"Перехвачена ошибка: {context.error}", exc_info=True)
    if isinstance(update, Update) and update.effective_message:
        with suppress(Exception): await update.effective_message.reply_text("Произошла техническая ошибка.")


async def run_bot_async():
    """Асинхронная функция, которая настраивает и запускает бота."""
    application = Application.builder().token(TOKEN).build()

    add_item_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Добавить товар$'), add_item_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ADD_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            ADD_CATEGORY: [MessageHandler(filters.Regex('^(кроссовки|одежда)$'), get_category)],
            ADD_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            ADD_COMPOSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_composition)],
            ADD_PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            ADD_VARIANTS: [CommandHandler('done', done_adding),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, get_variant)]
        },
        fallbacks=[CommandHandler('cancel', cancel_dialog)],
    )

    # --- ПРАВИЛЬНЫЙ ПОРЯДОК РЕГИСТРАЦИИ ОБРАБОТЧИКОВ ---
    # 1. Сначала команды с высоким приоритетом
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))

    # 2. Затем сложный обработчик диалогов
    application.add_handler(add_item_handler)

    # 3. В самом конце - общий обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_messages))

    # Глобальный обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("Запуск Telegram-бота в режиме polling...")
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")