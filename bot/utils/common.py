from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.utils.match_groups import get_matches_for_player, get_total_groups
from db.crud.tour import crud_tour
from db.db import get_async_session
from db.models import Match, MatchPrediction, Player, Tournament


async def get_predictions(player: Player):
    result_message = "\n"
    async for session in get_async_session():
        player_with_predictions = await session.execute(
            select(Player)
            .options(
                selectinload(Player.match_predictions)
                .selectinload(MatchPrediction.match)
                .selectinload(Match.tour),
                selectinload(Player.tournament).selectinload(Tournament.current_tour),
                selectinload(Player.tournament).selectinload(Tournament.matches),
            )
            .where(Player.id == player.id, Player.is_eliminated == False)
        )
        player = player_with_predictions.scalars().first()
        if player:
            total_groups = await get_total_groups(player.tournament)
            allowed_match_ids = {
                match.id
                for match in get_matches_for_player(
                    player, player.tournament, total_groups
                )
            }
            for prediction in player.match_predictions:
                if (
                    prediction.match.tour.id == player.tournament.current_tour_id
                    and prediction.match_id in allowed_match_ids
                ):
                    result_message += f"{(prediction.match.first_team)} - {prediction.match.second_team} {prediction.first_team_score}-{prediction.second_team_score} Очки: {prediction.points} \n"
        return result_message


async def send_long_message(chat_id: int, message: str, bot: Bot):
    max_length = 4096
    parts = [message[i : i + max_length] for i in range(0, len(message), max_length)]
    for part in parts:
        await bot.send_message(chat_id, part)


async def get_tour(tournament: Tournament):
    async for session in get_async_session():
        tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        return tour
