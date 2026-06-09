import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)

router = Router()


@router.errors()
async def handle_errors(event: ErrorEvent) -> bool:
    exc = event.exception
    update_id = event.update.update_id if event.update else "?"

    if isinstance(exc, TelegramNetworkError):
        logger.warning(
            "Сеть Telegram недоступна (update %s): %s",
            update_id,
            exc,
        )
        return True

    if isinstance(exc, TelegramAPIError):
        logger.warning(
            "Ошибка Telegram API (update %s): %s",
            update_id,
            exc,
        )
        return True

    logger.exception("Необработанная ошибка (update %s)", update_id)
    return True
