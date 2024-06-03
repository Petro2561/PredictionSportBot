from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str  # Токен для доступа к телеграм-боту
    admin_ids: list[int] | None  # Список id администраторов бота
    bot_username: str # Username бота


@dataclass
class Config:
    tg_bot: TgBot


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    return Config(
        tg_bot=TgBot(
            token=env("BOT_TOKEN"), admin_ids=list(map(int, env.list("ADMIN_IDS"))), bot_username=("BOT_USERNAME")
        )
    )
