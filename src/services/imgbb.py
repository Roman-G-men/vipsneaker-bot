# src/services/imgbb.py
import requests
import logging
from config import IMGBB_API_KEY

logger = logging.getLogger(__name__)


def upload_image(image_bytes: bytes) -> str | None:
    """Загружает байты изображения на ImgBB и возвращает URL."""
    if not IMGBB_API_KEY:
        logger.error("IMGBB_API_KEY не установлен в .env файле.")
        return None

    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": IMGBB_API_KEY,
    }
    files = {
        "image": image_bytes
    }

    try:
        # Увеличиваем таймаут, так как загрузка может быть долгой
        response = requests.post(url, data=payload, files=files, timeout=60)

        # Проверяем, что запрос был успешным (код 2xx)
        response.raise_for_status()

        result = response.json()

        if result.get('success'):
            image_url = result['data']['url']
            logger.info(f"Изображение успешно загружено на ImgBB: {image_url}")
            return image_url
        else:
            # Логируем ошибку, которую вернуло API
            error_message = result.get('error', {}).get('message', 'Неизвестная ошибка от API ImgBB')
            logger.error(f"Ошибка от API ImgBB: {error_message}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Сетевая ошибка при загрузке на ImgBB: превышен таймаут.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Сетевая ошибка при загрузке на ImgBB: {e}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке изображения на ImgBB: {e}", exc_info=True)
        return None