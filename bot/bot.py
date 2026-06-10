from aiogram import Bot

from bot.config import load_config

config = load_config()
main_bot = Bot(token=config.tg_bot.token)
