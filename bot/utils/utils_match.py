import select
from datetime import datetime, timedelta

from bot.errors.error import PredictionValidationError
from bot.utils.match_groups import (
    get_total_groups,
    match_is_in_first_half,
    player_predicts_first_half,
    splits_matches_by_groups,
)
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
    total_groups = await get_total_groups(tournament)
    is_first_half = match_is_in_first_half(match, tournament)

    async for session in get_async_session():
        for player in tournament.players:
            if splits_matches_by_groups(tournament):
                if not player.group:
                    continue
                predicts_first = player_predicts_first_half(player, total_groups)
                if is_first_half != predicts_first:
                    continue
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


def _current_tour_deadline(tournament: Tournament):
    if not tournament.current_tour_id:
        return None
    if tournament.current_tour:
        return tournament.current_tour.next_deadline
    return None


def tour_has_started(tournament: Tournament) -> bool:
    deadline = _current_tour_deadline(tournament)
    if deadline is None:
        return False
    return datetime.now() >= deadline


def tour_starts_at(tournament: Tournament):
    return _current_tour_deadline(tournament)


async def predictions_allowed(tournament: Tournament) -> bool:
    if not tournament.current_tour_id:
        return False
    async for session in get_async_session():
        tour: Tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        if not tour:
            return False
        now = datetime.now()
        if now >= tour.next_deadline:
            return False
        return tour.next_deadline - now > timedelta(hours=1)


async def validate_tour_date(tournament: Tournament) -> bool:
    return await predictions_allowed(tournament)


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
