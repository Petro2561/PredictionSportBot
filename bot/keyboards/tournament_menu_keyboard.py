from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.keyboards.callback_factory import TournamentCallbackFactory
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from bot.utils.utils import get_all_tournaments
from db.models import User
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery


def create_tournament_keyboard(user: User):
    tournaments = get_all_tournaments(user)
    if tournaments:
        keyboard = []
        for tournament in tournaments:
            button = InlineKeyboardButton(
                text=tournament.name,
                callback_data=TournamentCallbackFactory(id=tournament.id).pack()
            )
            keyboard.append([button])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return None

# Провести жеребьевку
# Посмотреть таблицу
# Дать прогноз
# Обнулить очки
# Ввесть матчи тура
# Посмотреть список участников
# Ввести прогнозы


def keyboard_menu(user, tournament):
    kb_builder = ReplyKeyboardBuilder()
    button_players = KeyboardButton(text='Посмотреть список участников')
    button_table = KeyboardButton(text='Посмотреть таблицу')
    button_make_prediction = KeyboardButton(text='Сделать прогноз')
    button_show_predictions = KeyboardButton(text='Посмотреть прогнозы игроков')
    kb_builder.row(button_players, button_table, width=2)
    kb_builder.row(button_make_prediction, button_show_predictions, width=2)

    if user.id == tournament.user.id:
        button_set_null = KeyboardButton(text='Обнулить очки игрокам')
        button_set_matches = KeyboardButton(text='Установить матчи')
        button_make_groups = KeyboardButton(text='Провести жеребьевку')
        kb_builder.row(button_set_null, button_set_matches, width=2)
        kb_builder.row(button_make_groups, width=2)
    keyboard = kb_builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    return keyboard