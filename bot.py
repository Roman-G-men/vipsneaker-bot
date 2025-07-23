# bot.py - ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ С ПРОДВИНУТОЙ АДМИНКОЙ И ПРАВИЛЬНЫМИ ЗАКАЗАМИ

import logging
import os
import io
import requests
import asyncio
import json
from contextlib import suppress
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, \
    InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext, ConversationHandler,
    CallbackQueryHandler
)
from database import get_session, User, Order, Product, ProductVariant

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
ADMIN_IDS = [8141146399, ]  # Убедись, что твой ID правильный

# --- Состояния для диалога ---
(ADMIN_MENU, ADD_NAME, ADD_BRAND, ADD_CATEGORY, ADD_DESCRIPTION, ADD_COMPOSITION, ADD_PHOTO, ADD_VARIANTS) = range(8)
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
ADD_ITEM_START_TEXT = "Начинаем добавлять новый товар.\n\nШаг 1/7: Введите **название товара**.\n\nДля отмены: /cancel"
ADD_VARIANT_TEXT = "Отлично! Товар создан.\n\nФинальный шаг: **добавьте варианты** (размеры).\nОтправьте: `размер цена количество`.\nПример: `42 12000 5`.\n\nКогда закончите, отправьте /done"


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
    if not IMGBB_API_KEY:
        raise ValueError("IMGBB_API_KEY не установлен!")
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


# --- КЛИЕНТСКАЯ ЧАСТЬ И ВЫХОД ИЗ АДМИНКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выход из админки и показ главного меню."""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил/перезапустил бота.")
    context.user_data.clear()  # Очищаем любые данные от админ-диалогов
    await show_main_menu(update, user_id)
    return CANCEL  # Гарантированно выходим из любого диалога


async def show_main_menu(update: Update, user_id: int) -> None:
    keyboard = [[KeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))],
                [KeyboardButton("📦 Мои заказы")]]
    await update.message.reply_text(MAIN_MENU_TEXT, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))


# --- АДМИН-ПАНЕЛЬ ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Вход в админ-панель и показ админ-меню."""
    context.user_data.clear()
    keyboard = [["➕ Добавить товар", "📝 Список товаров"], ["↩️ Выйти из админки"]]
    await update.message.reply_text(ADMIN_WELCOME_TEXT,
                                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ADMIN_MENU


# --- Диалог добавления товара ---
@admin_only
async def add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product'] = {}
    await update.message.reply_text(ADD_ITEM_START_TEXT, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
    return ADD_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['name'] = update.message.text
    await update.message.reply_text("Шаг 2/7: Введите **бренд**:", parse_mode='Markdown')
    return ADD_BRAND


async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['brand'] = update.message.text
    keyboard = [["кроссовки", "одежда"]]
    await update.message.reply_text("Шаг 3/7: Выберите **категорию**:",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return ADD_CATEGORY


async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product']['category'] = update.message.text.lower()
    await update.message.reply_text("Шаг 4/7: Введите **описание** товара:", reply_markup=ReplyKeyboardRemove())
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
        await update.message.reply_text("Загружаю фото...")
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
        await update.message.reply_text("Неверный формат. Пример: `42 12000 5`. Попробуйте еще раз или /done.",
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
    return await admin_panel(update, context)


async def cancel_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.")
    return await admin_panel(update, context)


# --- Интерактивный список товаров ---
async def list_products_paginated(message, context: ContextTypes.DEFAULT_TYPE, page: int = 0, is_edit=False):
    """Отображает список товаров с пагинацией."""
    with get_session() as session:
        per_page = 5
        offset = page * per_page
        products = session.query(Product).order_by(Product.id.desc()).limit(per_page).offset(offset).all()
        total_products = session.query(Product).count()
        total_pages = -(-total_products // per_page) if total_products > 0 else 1

    message_text = f"Товары (Страница {page + 1} из {total_pages}):"
    keyboard = []
    if not products:
        message_text = "В каталоге пока нет товаров."
    else:
        for product in products:
            keyboard.append(
                [InlineKeyboardButton(f"#{product.id} {product.name}", callback_data=f"prod_view_{product.id}_{page}")])

    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prod_page_{page - 1}"))
    if (page + 1) * per_page < total_products:
        pagination_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"prod_page_{page + 1}"))
    if pagination_buttons:
        keyboard.append(pagination_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if is_edit:
            await message.edit_text(text=message_text, reply_markup=reply_markup)
        else:
            await message.reply_text(text=message_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при отображении списка товаров: {e}")


@admin_only
async def list_products_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await list_products_paginated(update.message, context, page=0)


async def product_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[-1])
    await list_products_paginated(query.message, context, page=page, is_edit=True)


async def view_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, _, product_id, page = query.data.split('_')
    with get_session() as session:
        product = session.query(Product).get(product_id)
    if not product:
        await query.edit_message_text("Товар не найден.");
        return
    variants_text = "\n".join([f"  - {v.size}, {v.price} руб., {v.stock} шт." for v in product.variants])
    text = (f"**Товар #{product.id}: {product.name}**\n\n"
            f"**Бренд:** {product.brand}\n"
            f"**Активен:** {'Да' if product.is_active else 'Нет'}\n\n"
            f"**Варианты:**\n{variants_text}")
    keyboard = [
        [InlineKeyboardButton("🗑️ Удалить товар", callback_data=f"prod_delete_{product.id}")],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data=f"prod_page_{page}")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def delete_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    product_id = int(query.data.split('_')[-1])
    with get_session() as session:
        product = session.query(Product).get(product_id)
        if product:
            session.delete(product);
            session.commit()
            await query.answer(f"Товар #{product_id} удален!", show_alert=True)
            await list_products_paginated(query.message, context, page=0, is_edit=True)
        else:
            await query.answer("Товар уже был удален.", show_alert=True)


# --- Обработчик данных из WebApp ---
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user
        logger.info(f"Получены данные из WebApp от {user.id}: {data}")

        if data.get('type') == 'newOrder':
            with get_session() as session:
                new_order = Order(
                    user_id=user.id, items=json.dumps(data.get('items')), delivery_type=data.get('delivery_type'),
                    address=data.get('address'), phone=data.get('phone'), total_amount=data.get('total_price'),
                    status='Обработка'
                )
                session.add(new_order);
                session.commit()
                order_id = new_order.id
            logger.info(f"Заказ #{order_id} от пользователя {user.id} успешно сохранен в БД.")

            order_text = f"✅ **Ваш заказ #{order_id} успешно оформлен!**\n\n"
            order_text += "**Состав заказа:**\n"
            for item in data.get('items', []):
                order_text += f"- {item.get('name')} ({item.get('size')}) - {item.get('price')} руб.\n"
            order_text += f"\n**Итого:** {data.get('total_price')} руб.\n\n"
            order_text += "Мы скоро свяжемся с вами для подтверждения.\nДля связи: @VibeeAdmin / @kir_tg1"
            await update.message.reply_text(order_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка обработки данных из WebApp: {e}", exc_info=True)


# --- Обработчик обычных сообщений ---
async def handle_regular_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id
    if text == "📦 Мои заказы":
        await show_user_orders(update, context)
    else:
        await show_main_menu(update, user_id)


async def show_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    with get_session() as session:
        orders = session.query(Order).filter_by(user_id=user_id).order_by(Order.created_at.desc()).limit(5).all()
    if not orders:
        await update.message.reply_text("У вас пока нет оформленных заказов.")
        return

    response = "📦 **Ваши последние 5 заказов:**\n\n"
    for order in orders:
        items_list = json.loads(order.items)
        items_text = ", ".join([f"{item['name']} ({item['size']})" for item in items_list])
        response += (f"**Заказ #{order.id}** от {order.created_at.strftime('%d.%m.%Y')}\n"
                     f"Статус: `{order.status}`\n"
                     f"Сумма: {order.total_amount} руб.\n"
                     f"Состав: {items_text}\n\n")
    await update.message.reply_text(response, parse_mode='Markdown')


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
        allow_reentry=True
    )

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={
            ADMIN_MENU: [
                MessageHandler(filters.Regex('^➕ Добавить товар$'), add_item_start),
                MessageHandler(filters.Regex('^📝 Список товаров$'), list_products_start),
            ],
            # Перенаправляем состояния диалога добавления сюда
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ADD_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            ADD_CATEGORY: [MessageHandler(filters.Regex('^(кроссовки|одежда)$'), get_category)],
            ADD_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            ADD_COMPOSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_composition)],
            ADD_PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            ADD_VARIANTS: [CommandHandler('done', done_adding),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, get_variant)]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_dialog),
            CommandHandler('admin', admin_panel),
            MessageHandler(filters.Regex('^↩️ Выйти из админки$'), start)
        ],
        allow_reentry=True
    )

    # --- ПРАВИЛЬНЫЙ ПОРЯДОК РЕГИСТРАЦИИ ОБРАБОТЧИКОВ ---
    application.add_handler(admin_handler)
    application.add_handler(CommandHandler("start", start))

    # Обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(product_page_callback, pattern='^prod_page_'))
    application.add_handler(CallbackQueryHandler(view_product_callback, pattern='^prod_view_'))
    application.add_handler(CallbackQueryHandler(delete_product_callback, pattern='^prod_delete_'))

    # Обработчик данных из Mini App
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    # Обработчик обычных текстовых сообщений (самый низкий приоритет)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_messages))

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