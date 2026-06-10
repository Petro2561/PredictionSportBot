import asyncio
import logging
import os

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage, Redis

from bot.bot import main_bot
from bot.config import load_config
from bot.handlers import (creator_handlers, error_handler,
                          tournament_menu_handler, user_tournament_handler)
from bot.scheduler.scheduler import scheduler
from bot.webapp_server import start_webapp_server

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s "
        "[%(asctime)s] - %(name)s - %(message)s",
    )

    config = load_config()
    logger.info("Starting bot")
    await start_webapp_server(port=config.webapp.port)
    redis = Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
    )
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    dp.include_router(error_handler.router)
    dp.include_router(user_tournament_handler.router)
    dp.include_router(tournament_menu_handler.router)
    dp.include_router(creator_handlers.router)

    scheduler.start()

    if os.getenv("TELEGRAM_SKIP_DELETE_WEBHOOK", "1") == "0":
        try:
            await asyncio.wait_for(
                main_bot.delete_webhook(drop_pending_updates=False),
                timeout=15,
            )
            logger.info("Webhook cleared")
        except Exception as exc:
            logger.warning("delete_webhook не удался: %s", exc)
    else:
        logger.info("delete_webhook пропущен (polling, TELEGRAM_SKIP_DELETE_WEBHOOK=1)")

    logger.info("Starting polling")
    try:
        await dp.start_polling(main_bot)
    finally:
        await main_bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("Bot stopped with error")
        raise
