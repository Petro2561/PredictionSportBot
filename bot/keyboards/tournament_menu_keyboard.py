from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.utils.utils_tournament import get_all_tournaments
from db.models import User
from aiogram.types.web_app_info import WebAppInfo


button_next = InlineKeyboardButton(text="Далее", callback_data="next")
inline_keyboard_next = InlineKeyboardMarkup(inline_keyboard=[[button_next]])

def create_tournament_keyboard(user: User):
    tournaments = get_all_tournaments(user)
    if tournaments:
        keyboard = []
        for tournament in tournaments:
            button = InlineKeyboardButton(
                text=tournament.name,
                callback_data=TournamentCallbackFactory(id=tournament.id).pack(),
            )
            keyboard.append([button])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return None

def generate_link(button):
    # example
    # r'https://d1sney.github.io/WebAppPrediction/prediction-match?matches=[England-Italy,Germany-Netherlands,Belgium-Croatia,Wales-Italy]&anotherParam={another_param}'
    return f'https://d1sney.github.io/WebAppPrediction/prediction-match?matches=[England-Italy,Germany-Netherlands,Belgium-Croatia,Wales-Italy]&button={button}'

def keyboard_menu(user, tournament):
    kb_builder = ReplyKeyboardBuilder()
    button_players = KeyboardButton(text="Посмотреть список участников")
    button_table = KeyboardButton(text="Посмотреть таблицу")
    button_make_prediction = KeyboardButton(text="Сделать прогноз", web_app=WebAppInfo(url=generate_link('button_make_prediction')))
    button_show_predictions = KeyboardButton(text="Посмотреть прогнозы игроков")
    kb_builder.row(button_players, button_table, width=2)
    kb_builder.row(button_make_prediction, button_show_predictions, width=2)

    if user.id == tournament.user.id:
        button_set_null = KeyboardButton(text="Обнулить очки игрокам")
        button_set_matches = KeyboardButton(text="Установить матчи", web_app=WebAppInfo(url='https://d1sney.github.io/WebAppPrediction'))
        button_set_matches_result = KeyboardButton(text="Проставить результаты матчей", web_app=WebAppInfo(url=generate_link('button_set_matches_result')))
        button_make_groups = KeyboardButton(text="Провести жеребьевку")
        button_eliminate_plaayer = KeyboardButton(text="Убрать игрока из турнира")
        kb_builder.row(button_set_null, button_set_matches, width=2)
        kb_builder.row(button_make_groups, button_set_matches_result, button_eliminate_plaayer, width=2)
    keyboard = kb_builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    return keyboard
