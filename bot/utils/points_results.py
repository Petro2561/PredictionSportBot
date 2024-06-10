from sqlalchemy import select
from db.db import get_async_session
from db.models import MatchPrediction, Player, Tournament
from db.crud.match import crud_match
from db.crud.tour import crud_tour
from sqlalchemy.orm import selectinload


async def calculate_prediction_results(tournament: Tournament):
    async for session in get_async_session():
        tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
        if tour:
            matches = await crud_match.get_matches_by_tour(current_tour=tour.number, tournament_id=tournament.id, session=session)
            for match in matches:
                if match.first_team_score is not None and match.second_team_score is not None:
                    for match_prediction in match.match_predictions:
                        points = 0
                        if (match_prediction.first_team_score == match.first_team_score and 
                                match_prediction.second_team_score == match.second_team_score):
                            points += tournament.exact_score_points
                        elif (match_prediction.first_team_score - match_prediction.second_team_score) == (match.first_team_score - match.second_team_score):
                            points += tournament.difference_points
                        elif ((match_prediction.first_team_score > match_prediction.second_team_score and 
                                match.first_team_score > match.second_team_score) or
                            (match_prediction.first_team_score < match_prediction.second_team_score and 
                                match.first_team_score < match.second_team_score) or
                            (match_prediction.first_team_score == match_prediction.second_team_score and 
                                match.first_team_score == match.second_team_score)):
                            points += tournament.results_points
                        match_prediction.points = points
                        session.add(match_prediction)
            await session.commit()
            return True
        
async def player_points_calculation(tournament: Tournament):
        async for session in get_async_session():
            tour = await crud_tour.get_tour_by_id(tournament.current_tour_id, session)
            if tour and (not tour.is_calculated):
                tournament_with_players = await session.execute(
                    select(Tournament)
                    .options(selectinload(Tournament.players)
                            .selectinload(Player.match_predictions)
                            .selectinload(MatchPrediction.match))
                    .where(Tournament.id == tournament.id)
                ) # вынести в утилс
                tournament = tournament_with_players.scalars().first()
                for player in tournament.players:
                    total_points = 0
                    for prediction in player.match_predictions:
                        if prediction.match.tour == tour.number:
                            total_points += prediction.points
                    player.points += total_points
                    session.add(player)
                tour.is_calculated = True
                session.add(tour)
                await session.commit()


        
              

        
