import select
from datetime import datetime, timedelta

from bot.errors.error import PredictionValidationError
from db.crud.match import crud_match
from db.crud.match_prediction import crud_match_prediction
from db.crud.tour import crud_tour
from db.db import get_async_session
from db.models import Match, MatchPrediction, Tour, Tournament


async def create_match(data, first_team, second_team):
    async for session in get_async_session():
        data_match = {
            "first_team": first_team,
            "second_team": second_team,
            "tournament_id": data["tournament_id"],
            "tour_id": data["tour_id"],
        }
        match = await crud_match.create(data_match, session)
        session.add(match)
        await session.commit()
        return match


async def create_match_prediction(
    match, tournament, first_team_score=0, second_team_score=0
):
    async for session in get_async_session():
        for player in tournament.players:
            data_match = {
                "first_team_score": first_team_score,
                "second_team_score": second_team_score,
                "match_id": match.id,
                "player_id": player.id,
            }
            match_prediction = await crud_match_prediction.create(data_match, session)
            session.add(match_prediction)
        await session.commit()


async def update_match_prediction_for_player(
    match_id, player_id, first_team_score, second_team_score
):
    async for session in get_async_session():
        match_prediction = (
            await crud_match_prediction.get_match_prediction_by_match_id_and_player_id(
                match_id, player_id, session
            )
        )
        if match_prediction:
            match_prediction.first_team_score = first_team_score
            match_prediction.second_team_score = second_team_score
            session.add(match_prediction)
            await session.commit()
            return match_prediction
        else:
            data = {
                "match_id": match_id,
                "player_id": player_id,
                "first_team_score": first_team_score,
                "second_team_score": second_team_score,
            }
            match_prediction = await crud_match_prediction.create(data, session)
            await session.commit()
            return match_prediction


async def get_match_by_id(match_id) -> Match:
    async for session in get_async_session():
        match = await crud_match.get_match_by_id(match_id, session)
        await session.commit()
        return match


async def validate_prediction(match_id, first_team, second_team):
    match = await get_match_by_id(match_id)
    if match.first_team != first_team or match.second_team != second_team:
        raise PredictionValidationError


async def validate_tour_date(tournament: Tournament):
    async for session in get_async_session():
        tour: Tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        if tour.next_deadline - datetime.now() > timedelta(hours=1):
            return True


async def update_match_results(match_id, first_team_score, second_team_score):
    async for session in get_async_session():
        match: Match = await crud_match.get_match_by_id(match_id, session)
        if match:
            match.first_team_score = first_team_score
            match.second_team_score = second_team_score
            session.add(match)
            await session.commit()
            return match


async def get_match_by_teams(tournament, first_team, second_team):
    async for session in get_async_session():
        match: Match = await crud_match.get_match_by_teams(
            first_team, second_team, tournament, session
        )
        return match
