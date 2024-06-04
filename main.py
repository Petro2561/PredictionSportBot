import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Config, load_config
from bot.handlers import creator_handlers, tournament_menu_user

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
    dp.include_router(tournament_menu_user.router)
    config: Config = load_config()
    bot = Bot(token=config.tg_bot.token)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


asyncio.run(main())
