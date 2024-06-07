from aiogram import Bot

from bot.config import Config, load_config

config: Config = load_config()

main_bot = Bot(token=config.tg_bot.token)
