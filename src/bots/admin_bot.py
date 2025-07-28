# src/bots/admin_bot.py
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler,
                          filters, ContextTypes, ConversationHandler)

import config
from database import SessionLocal, queries
from services import imgbb
from utils.helpers import create_admin_pagination_keyboard

# ==================== ИСПРАВЛЕНИЕ ЗДЕСЬ ====================
logger = logging.getLogger(__name__)
# ==========================================================

(NAME, BRAND, CATEGORY, DESCRIPTION, COMPOSITION, PHOTO, VARIANTS, CONFIRM) = range(8)


def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in config.ADMIN_IDS:
            # Теперь эта строка будет работать, так как logger определен выше
            logger.warning(f"Неавторизованный доступ в админ-бот от {update.effective_user.id}")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data='add_product')],
        [InlineKeyboardButton("📝 Список товаров", callback_data='list_products_0')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = 'Добро пожаловать в панель администратора!'

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


@restricted
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['product_info'] = {}
    await query.edit_message_text('Введите название товара:')
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_info']['name'] = update.message.text
    await update.message.reply_text('Введите бренд товара:')
    return BRAND


async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_info']['brand'] = update.message.text
    keyboard = [[InlineKeyboardButton("Кроссовки", callback_data='cat_Кроссовки'),
                 InlineKeyboardButton("Одежда", callback_data='cat_Одежда')]]
    await update.message.reply_text('Выберите категорию:', reply_markup=InlineKeyboardMarkup(keyboard))
    return CATEGORY


async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['product_info']['category'] = query.data.split('_')[1]
    await query.edit_message_text('Введите описание товара:')
    return DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_info']['description'] = update.message.text
    await update.message.reply_text('Введите состав (например, "Хлопок 100%"):')
    return COMPOSITION


async def get_composition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_info']['composition'] = update.message.text
    await update.message.reply_text('Отправьте фото товара:')
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    msg = await update.message.reply_text("Загружаю фото на сервер...")
    photo_url = imgbb.upload_image(bytes(photo_bytes))

    if not photo_url:
        await msg.edit_text("Не удалось загрузить фото. Попробуйте снова. Для отмены введите /cancel")
        return PHOTO

    context.user_data['product_info']['photo_url'] = photo_url
    context.user_data['product_info']['variants'] = []

    await msg.edit_text(
        f"Фото успешно загружено!\n\n"
        "Теперь добавляйте варианты товара.\n"
        "Отправляйте сообщения в формате: `размер цена количество`\n"
        "Например: `42 15000 5`\n\n"
        "Когда закончите, отправьте команду /done",
        parse_mode='Markdown'
    )
    return VARIANTS


async def get_variants(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        size, price_str, stock_str = update.message.text.strip().split()
        variant_data = {'size': size, 'price': float(price_str), 'stock': int(stock_str)}

        if any(v['size'] == size for v in context.user_data['product_info']['variants']):
            await update.message.reply_text(f"⚠️ Размер {size} уже добавлен. Вы можете отредактировать его позже.")
            return VARIANTS

        context.user_data['product_info']['variants'].append(variant_data)
        await update.message.reply_text(f"✅ Добавлен размер {size}. Можете добавить еще или отправить /done.")
    except (ValueError, TypeError):
        await update.message.reply_text(
            "Неверный формат. Используйте: `размер цена количество` (например: `L 5000 10`).")
    return VARIANTS


async def done_adding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_info = context.user_data.get('product_info')
    if not product_info or not product_info.get('variants'):
        await update.message.reply_text(
            "Вы не добавили ни одного варианта. Добавьте хотя бы один или отмените /cancel.")
        return VARIANTS

    variants_info = "\n".join(f"  - {v['size']}, {v['price']}₽, {v['stock']} шт." for v in product_info['variants'])
    text = (f"<b>Проверьте данные перед сохранением:</b>\n\n"
            f"<b>Название:</b> {product_info['name']}\n"
            f"<b>Бренд:</b> {product_info['brand']}\n"
            f"<b>Категория:</b> {product_info['category']}\n"
            f"<b>Описание:</b> {product_info['description']}\n"
            f"<b>Состав:</b> {product_info['composition']}\n"
            f"<b>Варианты:</b>\n{variants_info}")

    keyboard = [[InlineKeyboardButton("✅ Сохранить", callback_data='confirm_save'),
                 InlineKeyboardButton("❌ Отмена", callback_data='cancel_save')]]

    await update.message.reply_photo(
        photo=product_info['photo_url'],
        caption=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def save_product_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    product_info = context.user_data.get('product_info')

    db = SessionLocal()
    try:
        new_product = queries.create_product(db, product_info)
        await query.edit_message_caption(
            caption=f"🎉 Товар '{new_product.name}' успешно добавлен с ID {new_product.id}!", reply_markup=None)
        logger.info(f"Админ {update.effective_user.id} добавил товар {new_product.name}")
    except Exception as e:
        logger.error(f"Ошибка сохранения товара в БД: {e}", exc_info=True)
        await query.edit_message_caption(caption="Произошла ошибка при сохранении товара.", reply_markup=None)
    finally:
        db.close()

    context.user_data.clear()
    await start_command(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    if update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
            await update.callback_query.edit_message_text('Действие отменено.')
    else:
        await update.message.reply_text('Действие отменено.')

    await start_command(update, context)
    return ConversationHandler.END


@restricted
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[2])
    items_per_page = 5

    db = SessionLocal()
    try:
        products, total_items = queries.get_paginated_products(db, page, items_per_page)

        if not products and page == 0:
            await query.edit_message_text("Товаров пока нет.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 В главное меню", callback_data='main_menu')]]))
            return

        keyboard = [[InlineKeyboardButton(f"ID {p.id}: {p.name}", callback_data=f'view_product_{p.id}')] for p in
                    products]
        pagination_keys = create_admin_pagination_keyboard(page, total_items, items_per_page, 'list_products')
        keyboard.extend(pagination_keys)
        keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data='main_menu')])

        await query.edit_message_text(f'Список товаров (Страница {page + 1}):',
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db.close()


@restricted
async def view_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split('_')[2])

    db = SessionLocal()
    try:
        product = queries.get_product_details(db, product_id)
        if not product:
            await query.edit_message_text("Товар не найден.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ К списку", callback_data='list_products_0')]]))
            return

        variants_info = "\n".join(
            f"  - {v.size}, {v.price}₽, {v.stock} шт." for v in product.variants) or "Нет вариантов"
        text = (f"<b>ID:</b> {product.id}\n<b>Название:</b> {product.name}\n"
                f"<b>Варианты:</b>\n{variants_info}")

        keyboard = [
            [InlineKeyboardButton("🗑️ Удалить", callback_data=f'delete_confirm_{product.id}')],
            [InlineKeyboardButton("◀️ К списку", callback_data='list_products_0')]
        ]

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=product.photo_url,
            caption=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.message.delete()

    finally:
        db.close()


@restricted
async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    product_id = int(query.data.split('_')[2])
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'delete_do_{product_id}')],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data=f'view_product_{product_id}')]
    ]
    await query.answer()
    await query.edit_message_caption(caption=f"Уверены, что хотите удалить товар ID {product_id}?",
                                     reply_markup=InlineKeyboardMarkup(keyboard))


@restricted
async def delete_do(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    product_id = int(query.data.split('_')[2])
    db = SessionLocal()
    try:
        if queries.delete_product(db, product_id):
            await query.answer("Товар удален!")
            logger.info(f"Админ {update.effective_user.id} удалил товар {product_id}")
            await query.message.delete()
            query.data = 'list_products_0'
            await list_products(update, context)
        else:
            await query.answer("Товар уже был удален.", show_alert=True)
    finally:
        db.close()


def create_admin_bot_app():
    application = Application.builder().token(config.ADMIN_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern='^add_product$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            CATEGORY: [CallbackQueryHandler(get_category, pattern='^cat_')],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            COMPOSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_composition)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            VARIANTS: [CommandHandler('done', done_adding),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, get_variants)],
            CONFIRM: [
                CallbackQueryHandler(save_product_confirmed, pattern='^confirm_save$'),
                CallbackQueryHandler(cancel, pattern='^cancel_save$')
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(cancel, pattern='^main_menu$')],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(list_products, pattern='^list_products_'))
    application.add_handler(CallbackQueryHandler(view_product, pattern='^view_product_'))
    application.add_handler(CallbackQueryHandler(delete_confirm, pattern='^delete_confirm_'))
    application.add_handler(CallbackQueryHandler(delete_do, pattern='^delete_do_'))
    application.add_handler(CallbackQueryHandler(start_command, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern='^noop$'))

    return application