import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage, Redis

from bot.bot import main_bot
from bot.config import load_config
from bot.handlers import (creator_handlers, tournament_menu_handler,
                          user_tournament_handler)
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
    redis = Redis(host='localhost')
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    dp.include_router(user_tournament_handler.router)
    dp.include_router(tournament_menu_handler.router)
    dp.include_router(creator_handlers.router)

    scheduler.start()

    await main_bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(main_bot)


asyncio.run(main())
