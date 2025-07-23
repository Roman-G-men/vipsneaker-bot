# bot.py - ФИНАЛЬНАЯ ВЕРСИЯ С ВСТРОЕННОЙ TELEGRAM-АДМИНКОЙ И ОБНОВЛЕННЫМИ КОНТАКТАМИ

import logging
import os
import io
import requests
import asyncio
from contextlib import suppress
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext, ConversationHandler
)
from database import get_session, User, Order, Product

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# Вставь сюда свой Telegram User ID. Чтобы его узнать, напиши боту @userinfobot
ADMIN_IDS = [8141146399, ]  # Можешь добавить несколько ID через запятую

# --- Состояния для диалога добавления товара ---
(NAME, BRAND, CATEGORY, SIZE, PRICE, DESCRIPTION, COMPOSITION, PHOTO) = range(8)
CANCEL = ConversationHandler.END

# --- Текстовые константы ---
MAIN_MENU_TEXT = (
    "Sneaker SHOP — Продажа только оригинальных вещей\n"
    "Имеется более 2000 отзывов!\n"
    "Москва / Отправка транспортной компанией СДЭК\n\n"
    "Канал с наличием: https://t.me/+8Y8sxODeiQIyYTgy\n"
    # <<< ИЗМЕНЕНИЕ ЗДЕСЬ >>>
    "Связь / Покупка: @VibeeAdmin / @kir_tg1"
)


# --- КЛИЕНТСКАЯ ЧАСТЬ БОТА ---
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


# --- АДМИНСКАЯ ЧАСТЬ БОТА ---
def admin_only(func):
    """Декоратор для проверки, является ли пользователь админом."""

    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            logger.warning(f"Пользователь {user_id} попытался получить доступ к админ-команде.")
            await update.message.reply_text("У вас нет прав для выполнения этой команды.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["Добавить товар"], ["Список товаров (скоро)"], ["Выйти из админки"]]
    await update.message.reply_text("Добро пожаловать в админ-панель!",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


def upload_to_imgbb(image_bytes, filename="photo.jpg"):
    """Функция для загрузки байтов изображения на ImgBB."""
    if not IMGBB_API_KEY: raise ValueError("IMGBB_API_KEY не установлен!")
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY}
    files = {"image": (filename, image_bytes, "image/jpeg")}
    response = requests.post(url, data=payload, files=files)
    result = response.json()
    if result.get("success"):
        return result["data"]["url"]
    else:
        raise Exception(f"Ошибка ImgBB: {result.get('error', {}).get('message', 'Неизвестная ошибка')}")


@admin_only
async def add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product'] = {}
    await update.message.reply_text("Введите название товара (или /cancel для отмены):")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['name'] = update.message.text
    await update.message.reply_text("Теперь введите бренд:")
    return BRAND


async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['brand'] = update.message.text
    keyboard = [["кроссовки", "одежда"]]
    await update.message.reply_text("Выберите категорию:",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return CATEGORY


async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['category'] = update.message.text.lower()
    await update.message.reply_text("Введите размер:")
    return SIZE


async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['size'] = update.message.text
    await update.message.reply_text("Введите цену (только цифры):")
    return PRICE


async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['new_product']['price'] = int(update.message.text)
        await update.message.reply_text("Введите описание товара:")
        return DESCRIPTION
    except ValueError:
        await update.message.reply_text("Цена должна быть числом. Попробуйте еще раз.")
        return PRICE


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['description'] = update.message.text
    await update.message.reply_text("Введите состав (или напишите 'нет'):")
    return COMPOSITION


async def get_composition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product'][
        'composition'] = update.message.text if update.message.text.lower() != 'нет' else None
    await update.message.reply_text("Отлично! Теперь отправьте главное фото товара.")
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        await update.message.reply_text("Загружаю фото, пожалуйста, подождите...")
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image_url = upload_to_imgbb(bytes(photo_bytes))

        product_data = context.user_data['new_product']
        with get_session() as session:
            new_product = Product(
                name=product_data['name'], brand=product_data['brand'], category=product_data['category'],
                size=product_data['size'], price=product_data['price'], description=product_data['description'],
                composition=product_data.get('composition'), image_url=image_url, is_active=1
            )
            session.add(new_product)
            session.commit()
            product_id = new_product.id

        await update.message.reply_text(f"Товар '{new_product.name}' успешно добавлен! ID: {product_id}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении товара: {e}", exc_info=True)
        await update.message.reply_text(f"Произошла ошибка: {e}. Попробуйте снова.")

    context.user_data.clear()
    await admin_panel(update, context)
    return CANCEL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.")
    await admin_panel(update, context)
    return CANCEL


async def handle_regular_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Здесь можно добавить логику ответа на "Мои заказы" и другие кнопки
    # Но пока просто показываем главное меню
    await show_main_menu(update, update.effective_user.id)


async def run_bot_async():
    """Асинхронная функция, которая настраивает и запускает бота."""
    application = Application.builder().token(TOKEN).build()

    add_item_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Добавить товар$'), add_item_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            CATEGORY: [MessageHandler(filters.Regex('^(кроссовки|одежда)$'), get_category)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_size)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            COMPOSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_composition)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(add_item_handler)
    # Обычные сообщения должны идти после ConversationHandler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_messages))

    logger.info("Запуск Telegram-бота в режиме polling...")
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        while True:
            await asyncio.sleep(3600)