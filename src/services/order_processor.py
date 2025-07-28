# src/services/order_processor.py
import logging
from sqlalchemy.orm import Session
from database import queries
from database.models import User, Order

logger = logging.getLogger(__name__)

def process_new_order(db: Session, user: User, order_data: dict) -> Order | None:
    """
    Сохраняет заказ в БД, уменьшает сток и возвращает созданный объект заказа.
    Возвращает None в случае ошибки (например, нехватки товара).
    """
    try:
        # Транзакция будет либо выполнена полностью, либо отменена благодаря SQLAlchemy
        new_order = queries.create_order(db, user, order_data)
        logger.info(f"Успешно обработан и сохранен заказ #{new_order.id} для пользователя {user.telegram_id}")
        return new_order
    except ValueError as e:
        logger.warning(f"Ошибка при обработке заказа для {user.telegram_id}: {e}")
        db.rollback() # Откатываем изменения в сессии
        return None
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке заказа: {e}", exc_info=True)
        db.rollback()
        return None