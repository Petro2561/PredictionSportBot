import socket

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from bot.config import Config, load_config

config: Config = load_config()


def _telegram_session() -> AiohttpSession:
    """IPv4-only: на VPS без IPv6 в Docker иначе Network is unreachable (errno 101)."""
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET
    return session


main_bot = Bot(token=config.tg_bot.token, session=_telegram_session())
