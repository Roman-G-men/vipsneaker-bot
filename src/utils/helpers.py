# src/utils/helpers.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def format_order_message(order, items):
    """Формирует красивое сообщение-карточку о заказе."""
    order_details = ""
    for item in items:
        item_total = item['price'] * item['quantity']
        order_details += (f"• {item['product_name']} ({item['size']}) x {item['quantity']} шт. "
                          f"- {item_total:.2f} ₽\n")

    caption = (
        f"✅ <b>Заказ №{order.id} успешно сформирован!</b>\n\n"
        f"<b>Состав заказа:</b>\n{order_details}\n"
        f"<b>Итоговая сумма: {order.total_amount:.2f} ₽</b>\n\n"
        "Для оформления заказа и уточнения деталей, пожалуйста, "
        "<b>перешлите это сообщение</b> менеджеру @VibeeAdmin или @kir_tg1"
    )
    first_item_photo = items[0]['photo_url'] if items else None
    return caption, first_item_photo


def create_admin_pagination_keyboard(page: int, total_items: int, per_page: int, callback_prefix: str):
    """Создает клавиатуру для пагинации в админ-панели."""
    keyboard = []
    nav_buttons = []

    total_pages = (total_items + per_page - 1) // per_page

    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'{callback_prefix}_{page - 1}'))

    if total_pages > 1:
        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data='noop'))  # noop - no operation

    if (page + 1) * per_page < total_items:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f'{callback_prefix}_{page + 1}'))

    if nav_buttons:
        keyboard.append(nav_buttons)

    return keyboard