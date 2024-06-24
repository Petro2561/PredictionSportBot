from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton)
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder, ReplyKeyboardMarkup

from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.utils.utils_match import validate_tour_date
from bot.utils.utils_tournament import get_all_tournaments, get_tournament
from db.models import User

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


async def generate_link(tournament):
    teams = ""
    tournament = await get_tournament(tournament.id)
    matches = [
        match
        for match in tournament.matches
        if tournament.current_tour_id == match.tour.id
    ]
    matches.sort(key=lambda match: match.id)
    if matches:
        for match in matches:
            teams += f"{match.first_team}-{match.second_team},"
        teams = teams.rstrip(",")
        return f"https://d1sney.github.io/WebAppPrediction/prediction-match?matches=[{teams}]"
    else:
        return f"https://d1sney.github.io/WebAppPrediction/prediction-match?matches=[{teams}]"


async def keyboard_menu(user_id, tournament_id):
    kb_builder = ReplyKeyboardBuilder()
    button_players = KeyboardButton(text="Посмотреть список участников")
    button_table = KeyboardButton(text="Посмотреть таблицу")
    tournament = await get_tournament(tournament_id)
    if tournament.current_tour_id:
        date_validation = await validate_tour_date(tournament)
        if date_validation:
            button_make_prediction = KeyboardButton(
                text="Сделать прогноз",
                web_app=WebAppInfo(url=await generate_link(tournament=tournament)),
            )
        else:
            button_make_prediction = KeyboardButton(text="Сделать прогноз")
        button_show_predictions = KeyboardButton(text="Посмотреть прогнозы игроков")
        kb_builder.row(button_show_predictions, button_make_prediction, width=2)
    button_text = KeyboardButton(text="Сделать прогноз через текст")
    kb_builder.row(button_players, button_table, button_text, width=2)    

    if user_id == tournament.user.id:
        button_set_null = KeyboardButton(text="Обнулить очки игрокам")
        button_set_matches = KeyboardButton(text="Установить матчи")
        button_set_matches_result = KeyboardButton(text="Проставить результаты матчей")
        button_make_groups = KeyboardButton(text="Провести жеребьевку")
        button_eliminate_plaayer = KeyboardButton(text="Убрать игрока из турнира")
        kb_builder.row(button_set_null, button_set_matches, width=2)
        kb_builder.row(
            button_make_groups,
            button_set_matches_result,
            button_eliminate_plaayer,
            width=2,
        )
    keyboard = kb_builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    return keyboard


def webapp_keyboard():
    kb_builder = ReplyKeyboardBuilder()
    webapp_button = KeyboardButton(
        text="Перейти к установке матчей",
        web_app=WebAppInfo(url="https://d1sney.github.io/WebAppPrediction"),
    )
    kb_builder.add(webapp_button)
    return kb_builder.as_markup(resize_keyboard=True)
