from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Создаем инлайн-кнопки
button_tournaments = InlineKeyboardButton(
    text="Мои турниры", callback_data="my_tournaments"
)
button_create = InlineKeyboardButton(
    text="Создать турнир", callback_data="create_tournament"
)

# Создаем и настраиваем инлайн-клавиатуру
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
