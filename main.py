import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.bot import main_bot
from bot.config import Config, load_config
from bot.handlers import creator_handlers, tournament_menu

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s "
        "[%(asctime)s] - %(name)s - %(message)s",
    )

    logger.info("Starting bot")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(creator_handlers.router)
    dp.include_router(tournament_menu.router)

    await main_bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(main_bot)


asyncio.run(main())
