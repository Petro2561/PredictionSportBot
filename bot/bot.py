import asyncio
import logging
import os
import socket

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from bot.config import load_config

logger = logging.getLogger(__name__)
config = load_config()


class BotSession(AiohttpSession):
    """Сессия для VPS: без keep-alive, опционально IPv6/IPv4, повтор при сбое сети."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connector_init["force_close"] = True
        self._connector_init["enable_cleanup_closed"] = True
        # Timeweb: IPv4 к api.telegram.org часто таймаутит, нужен IPv6 (TELEGRAM_IPV6=1)
        if os.getenv("TELEGRAM_IPV4", "0") == "1":
            self._connector_init["family"] = socket.AF_INET
        elif os.getenv("TELEGRAM_IPV6", "0") == "1":
            self._connector_init["family"] = socket.AF_INET6

    async def make_request(self, bot, method, timeout=None):
        retries = int(os.getenv("TELEGRAM_RETRIES", "3"))
        delay = float(os.getenv("TELEGRAM_RETRY_DELAY", "1"))
        last_exc: TelegramNetworkError | None = None
        for attempt in range(retries):
            try:
                return await super().make_request(bot, method, timeout)
            except TelegramNetworkError as exc:
                last_exc = exc
                method_name = getattr(method, "__api_method__", "?")
                if attempt + 1 >= retries:
                    logger.warning(
                        "Telegram API %s: сеть недоступна после %s попыток: %s",
                        method_name,
                        retries,
                        exc,
                    )
                    raise
                logger.info(
                    "Telegram API %s: повтор %s/%s (%s)",
                    method_name,
                    attempt + 2,
                    retries,
                    exc,
                )
                self._should_reset_connector = True
                await asyncio.sleep(delay * (attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError("unreachable")


def _telegram_family_label() -> str:
    if os.getenv("TELEGRAM_IPV4", "0") == "1":
        return "IPv4"
    if os.getenv("TELEGRAM_IPV6", "0") == "1":
        return "IPv6"
    return "auto"


_proxy = os.getenv("TELEGRAM_PROXY") or None
_session = BotSession(proxy=_proxy) if _proxy else BotSession()
_session.timeout = int(os.getenv("TELEGRAM_TIMEOUT", "30"))

main_bot = Bot(token=config.tg_bot.token, session=_session)
logger.info(
    "Telegram client: family=%s, timeout=%ss, retries=%s",
    _telegram_family_label(),
    _session.timeout,
    os.getenv("TELEGRAM_RETRIES", "3"),
)
