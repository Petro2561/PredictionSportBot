from aiogram import Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.filters.filters import PrivateChatFilter
from bot.keyboards.tournament_menu_keyboard import keyboard_menu
from bot.states.states import PredictionState, TournamentMenu
from bot.utils.utils_tournament import get_tournament, save_predictions
from bot.utils.utils_user_player import (get_or_create_player,
                                         get_or_create_user)
from db.models import Player, TournamentPrediction

ADDING_TO_TOURNAMENT = "Вы успешно добавлены в турнир"


router = Router()


@router.message(CommandStart(deep_link=True), PrivateChatFilter())
async def handler(message: Message, command: CommandObject, state: FSMContext):
    user = await get_or_create_user(message)
    data_for_player = {"user_id": user.id, "tournament_id": int(command.args)}
    player: Player = await get_or_create_player(data_for_player)
    await message.answer(ADDING_TO_TOURNAMENT)

    tournament = await get_tournament(int(command.args))
    await state.update_data(tournament=tournament)
    await state.update_data(user=user)
    await state.update_data(player=player)

    if not player.tournament_predictions or not [
        tournament_prediction
        for tournament_prediction in player.tournament_predictions
        if tournament_prediction.tournament_id == tournament.id
    ]:
        if tournament.winner:
            await message.answer("Угадайте победителя турнира")
            await state.set_state(PredictionState.waiting_for_winner)
        elif tournament.best_striker:
            await message.answer("Угадайте лучшего бомбардира турнира")
            await state.set_state(PredictionState.waiting_for_best_striker)
        elif tournament.best_assistant:
            await message.answer("Угадайте лучшего ассистента турнира")
            await state.set_state(PredictionState.waiting_for_best_assistant)


@router.message(StateFilter(PredictionState.waiting_for_winner))
async def process_winner_prediction(message: Message, state: FSMContext):
    winner_prediction = message.text
    await state.update_data(winner=winner_prediction)

    data = await state.get_data()
    tournament = data["tournament"]

    if tournament.best_striker:
        await message.answer("Угадайте лучшего бомбардира турнира")
        await state.set_state(PredictionState.waiting_for_best_striker)
    elif tournament.best_assistant:
        await message.answer("Угадайте лучшего ассистента турнира")
        await state.set_state(PredictionState.waiting_for_best_assistant)
    else:
        await save_predictions(state)
        await state.set_state(TournamentMenu.tournament_menu)
        await message.answer(
            "Вы в главном меню",
            reply_markup=await keyboard_menu(user=data["user"], tournament=tournament),
        )


@router.message(StateFilter(PredictionState.waiting_for_best_striker))
async def process_best_striker_prediction(message: Message, state: FSMContext):
    best_striker_prediction = message.text
    await state.update_data(best_striker=best_striker_prediction)

    data = await state.get_data()
    tournament = data["tournament"]

    if tournament.best_assistant:
        await message.answer("Угадайте лучшего ассистента турнира")
        await state.set_state(PredictionState.waiting_for_best_assistant)
    else:
        await save_predictions(state)
        await state.set_state(TournamentMenu.tournament_menu)
        await message.answer(
            "Вы в главном меню",
            reply_markup=await keyboard_menu(user=data["user"], tournament=tournament),
        )


@router.message(StateFilter(PredictionState.waiting_for_best_assistant))
async def process_best_assistant_prediction(message: Message, state: FSMContext):
    best_assistant_prediction = message.text
    await state.update_data(best_assistant=best_assistant_prediction)
    data = await state.get_data()
    tournament = data["tournament"]
    player = data["player"]

    prediction_data = {
        "tournament_id": tournament.id,
        "player_id": player.id,
        "winner": data.get("winner"),
        "best_striker": data.get("best_striker"),
        "best_assistant": data.get("best_assistant"),
    }

    await save_predictions(prediction_data)
    await state.set_state(TournamentMenu.tournament_menu)
    await message.answer(
        "Ура! Вы в турнире!",
        reply_markup=await keyboard_menu(user=data["user"], tournament=tournament),
    )
