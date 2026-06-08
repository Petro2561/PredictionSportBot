from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot.states.states import PredictionState, TournamentMenu
from db.db import get_async_session
from db.models import Player, Tournament, TournamentPrediction


PREDICTION_PROMPTS = {
    "best_striker": (
        "Угадайте лучшего бомбардира турнира",
        PredictionState.waiting_for_best_striker,
    ),
    "best_assistant": (
        "Угадайте лучшего ассистента турнира",
        PredictionState.waiting_for_best_assistant,
    ),
}


async def ensure_tournament_prediction_flags(tournament_id: int) -> None:
    async for session in get_async_session():
        tournament = await session.get(Tournament, tournament_id)
        if not tournament:
            return
        updated = False
        if tournament.winner:
            tournament.winner = False
            updated = True
        if not tournament.best_striker:
            tournament.best_striker = True
            updated = True
        if not tournament.best_assistant:
            tournament.best_assistant = True
            updated = True
        if updated:
            session.add(tournament)
            await session.commit()


def get_player_tournament_prediction(
    player: Player, tournament_id: int
) -> TournamentPrediction | None:
    return next(
        (
            prediction
            for prediction in player.tournament_predictions
            if prediction.tournament_id == tournament_id
        ),
        None,
    )


def get_missing_prediction_fields(player: Player, tournament: Tournament) -> list[str]:
    prediction = get_player_tournament_prediction(player, tournament.id)
    missing = []
    if tournament.best_striker and (not prediction or not prediction.best_striker):
        missing.append("best_striker")
    if tournament.best_assistant and (not prediction or not prediction.best_assistant):
        missing.append("best_assistant")
    return missing


async def save_tournament_prediction(
    tournament_id: int,
    player_id: int,
    *,
    winner: str | None = None,
    best_striker: str | None = None,
    best_assistant: str | None = None,
) -> TournamentPrediction:
    async for session in get_async_session():
        result = await session.execute(
            select(TournamentPrediction).where(
                TournamentPrediction.tournament_id == tournament_id,
                TournamentPrediction.player_id == player_id,
            )
        )
        prediction = result.scalars().first()
        if prediction:
            if winner is not None:
                prediction.winner = winner
            if best_striker is not None:
                prediction.best_striker = best_striker
            if best_assistant is not None:
                prediction.best_assistant = best_assistant
        else:
            prediction = TournamentPrediction(
                tournament_id=tournament_id,
                player_id=player_id,
                winner=winner,
                best_striker=best_striker,
                best_assistant=best_assistant,
            )
            session.add(prediction)
        await session.commit()
        await session.refresh(prediction)
        return prediction


async def start_next_prediction_prompt(
    message: Message, state: FSMContext, missing_field: str
) -> None:
    prompt, next_state = PREDICTION_PROMPTS[missing_field]
    await message.answer(prompt)
    await state.set_state(next_state)


async def finish_or_continue_predictions(
    message: Message,
    state: FSMContext,
    tournament: Tournament,
    player: Player,
    *,
    success_text: str = "Вы в главном меню",
) -> None:
    from bot.keyboards.tournament_menu_keyboard import keyboard_menu

    data = await state.get_data()
    missing = get_missing_prediction_fields(player, tournament)
    if missing:
        await start_next_prediction_prompt(message, state, missing[0])
        return

    await state.set_state(TournamentMenu.tournament_menu)
    await message.answer(
        success_text,
        reply_markup=await keyboard_menu(
            tournament_id=tournament.id, user_id=data["user_id"]
        ),
    )
