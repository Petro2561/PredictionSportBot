from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from bot.config import Config, load_config

config: Config = load_config()

_session = AiohttpSession()
_session.timeout = 90

main_bot = Bot(token=config.tg_bot.token, session=_session)
