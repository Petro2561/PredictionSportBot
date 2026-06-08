from aiogram import Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.filters.filters import PrivateChatFilter
from bot.states.states import PredictionState
from bot.utils.tournament_predictions import (
    ensure_tournament_prediction_flags,
    finish_or_continue_predictions,
    get_missing_prediction_fields,
    save_tournament_prediction,
    start_next_prediction_prompt,
)
from bot.utils.utils_tournament import get_tournament
from bot.utils.utils_user_player import get_or_create_player, get_or_create_user
from db.models import Player, User

ADDING_TO_TOURNAMENT = "Вы успешно добавлены в турнир"


router = Router()


@router.message(CommandStart(deep_link=True), PrivateChatFilter())
async def handler(message: Message, command: CommandObject, state: FSMContext):
    user: User = await get_or_create_user(message)
    tournament_id = int(command.args)
    await ensure_tournament_prediction_flags(tournament_id)
    player: Player = await get_or_create_player(
        {"user_id": user.id, "tournament_id": tournament_id}
    )
    await message.answer(ADDING_TO_TOURNAMENT)

    tournament = await get_tournament(tournament_id)
    await state.update_data(
        tournament_id=tournament.id, user_id=user.id, player_id=player.id
    )

    missing = get_missing_prediction_fields(player, tournament)
    if missing:
        await start_next_prediction_prompt(message, state, missing[0])


@router.message(StateFilter(PredictionState.waiting_for_best_striker))
async def process_best_striker_prediction(message: Message, state: FSMContext):
    data = await state.get_data()
    await save_tournament_prediction(
        data["tournament_id"],
        data["player_id"],
        best_striker=message.text.strip(),
    )
    tournament = await get_tournament(data["tournament_id"])
    player = await get_or_create_player(
        {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
    )
    await finish_or_continue_predictions(message, state, tournament, player)


@router.message(StateFilter(PredictionState.waiting_for_best_assistant))
async def process_best_assistant_prediction(message: Message, state: FSMContext):
    data = await state.get_data()
    await save_tournament_prediction(
        data["tournament_id"],
        data["player_id"],
        best_assistant=message.text.strip(),
    )
    tournament = await get_tournament(data["tournament_id"])
    player = await get_or_create_player(
        {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
    )
    await finish_or_continue_predictions(
        message, state, tournament, player, success_text="Ура! Вы в турнире!"
    )
