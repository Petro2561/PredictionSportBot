from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import Config, load_config

config: Config = load_config()

button_tournaments = InlineKeyboardButton(
    text="Мои турниры", callback_data="my_tournaments"
)
button_create = InlineKeyboardButton(
    text="Создать турнир", callback_data="create_tournament"
)

tournament = InlineKeyboardBuilder()
tournament.add(button_tournaments)
tournament.add(button_create)
tournament_keyboard = tournament.as_markup()

button_yes = InlineKeyboardButton(text="Да", callback_data="yes")
button_no = InlineKeyboardButton(text="Нет", callback_data="no")
yes_no_keyboard = InlineKeyboardBuilder()
yes_no_keyboard.add(button_yes)
yes_no_keyboard.add(button_no)
yes_no_keyboard = yes_no_keyboard.as_markup()

def get_add_bot_keyboard(bot_username: str, tournament_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить меня в группу", url=f"https://t.me/{bot_username}?startgroup={tournament_id}")]
        ]
    )

def join_tournament_keyboard(bot_username, tournament_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в турнир", url=f"https://t.me/{bot_username}?start={tournament_id}")]
        ]
    )
