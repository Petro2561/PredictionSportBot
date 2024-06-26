import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage, Redis

from bot.bot import main_bot
from bot.handlers import (creator_handlers, tournament_menu_handler,
                          user_tournament_handler)
from bot.scheduler.scheduler import scheduler

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s "
        "[%(asctime)s] - %(name)s - %(message)s",
    )

    logger.info("Starting bot")
    redis = Redis(host='localhost')
    storage = RedisStorage(redis=redis)
    dp = Dispatcher(storage=storage)
    dp.include_router(user_tournament_handler.router)
    dp.include_router(creator_handlers.router)
    dp.include_router(tournament_menu_handler.router)

    scheduler.start()

    await main_bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(main_bot)


asyncio.run(main())
