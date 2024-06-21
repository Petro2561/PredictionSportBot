from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.crud.match import crud_match
from db.crud.reset_points import crud_resetpoints
from db.crud.tour import crud_tour
from db.db import get_async_session
from db.models import MatchPrediction, Player, Tournament


async def calculate_prediction_results(tournament: Tournament):
    async for session in get_async_session():
        tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        if tour:
            matches = await crud_match.get_matches_by_tour(
                current_tour=tour.id, tournament_id=tournament.id, session=session
            )
            for match in matches:
                if (
                    match.first_team_score is not None
                    and match.second_team_score is not None
                ):
                    for match_prediction in match.match_predictions:
                        points = 0
                        if (
                            match_prediction.first_team_score == match.first_team_score
                            and match_prediction.second_team_score
                            == match.second_team_score
                        ):
                            points += tournament.exact_score_points
                        elif (
                            match_prediction.first_team_score
                            - match_prediction.second_team_score
                        ) == (match.first_team_score - match.second_team_score):
                            points += tournament.difference_points
                        elif (
                            (
                                match_prediction.first_team_score
                                > match_prediction.second_team_score
                                and match.first_team_score > match.second_team_score
                            )
                            or (
                                match_prediction.first_team_score
                                < match_prediction.second_team_score
                                and match.first_team_score < match.second_team_score
                            )
                            or (
                                match_prediction.first_team_score
                                == match_prediction.second_team_score
                                and match.first_team_score == match.second_team_score
                            )
                        ):
                            points += tournament.results_points
                        match_prediction.points = points
                        session.add(match_prediction)
            await session.commit()
            return True


async def player_points_calculation(tournament: Tournament):
    async for session in get_async_session():
        tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        if tour:
            tournament_with_players = await session.execute(
                select(Tournament)
                .options(
                    selectinload(Tournament.players)
                    .selectinload(Player.match_predictions)
                    .selectinload(MatchPrediction.match)
                )
                .where(Tournament.id == tournament.id)
            )  # вынести в утилс
            tournament = tournament_with_players.scalars().first()
            for player in tournament.players:
                total_points = 0
                for prediction in player.match_predictions:
                    if (
                        prediction.match.tour_id == tour.id
                        and prediction.match.first_team_score is not None
                        and prediction.match.second_team_score is not None
                        and not prediction.is_calculated
                    ):
                        total_points += prediction.points
                        prediction.is_calculated = True
                        session.add(prediction)
                player.points += total_points
                session.add(player)
            await session.commit()


async def create_reset_points_obj(tournament: Tournament):
    async for session in get_async_session():
        data = {"tournament_id": tournament.id, "tour_id": tournament.current_tour_id}
        reset_points = await crud_resetpoints.create(data, session)
        return reset_points


async def reset_points(tournament):
    async for session in get_async_session():
        for player in tournament.players:
            player.points = 0
            session.add(player)
            await session.commit()
