from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from bot.config import Config, load_config

config: Config = load_config()


class BotSession(AiohttpSession):
    """Не переиспользуем keep-alive: на VPS NAT рвёт простаивающие TCP-соединения."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connector_init["force_close"] = True
        self._connector_init["enable_cleanup_closed"] = True


_session = BotSession()
_session.timeout = 90

main_bot = Bot(token=config.tg_bot.token, session=_session)
