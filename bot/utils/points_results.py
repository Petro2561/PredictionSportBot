from db.db import get_async_session
from db.models import Match, MatchPrediction, Tournament
from db.crud.match import crud_match


async def get_prediction_results(tournament: Tournament):
    async for session in get_async_session():
        matches = await crud_match.get_matches_by_tour(tournament.current_tour, session)
        await session.refresh(matches, ["match_predictions"])
        for player in tournament.players:
            points = 0
            for match in matches:
                match_prediction = next((mp for mp in match.match_predictions if mp.player_id == player.id), None)
                if match_prediction:
                    if (match_prediction.first_team_score == match.first_team_score and 
                            match_prediction.second_team_score == match.second_team_score):
                        points += tournament.exact_score_points

                    elif (abs(match_prediction.first_team_score - match_prediction.second_team_score) ==
                            abs(match.first_team_score - match.second_team_score)):
                        points += tournament.difference_points

                    elif ((match_prediction.first_team_score > match_prediction.second_team_score and 
                            match.first_team_score > match.second_team_score) or
                          (match_prediction.first_team_score < match_prediction.second_team_score and 
                            match.first_team_score < match.second_team_score) or
                          (match_prediction.first_team_score == match_prediction.second_team_score and 
                            match.first_team_score == match.second_team_score)):
                        points += tournament.results_points
            
            player.points += points
            session.add(player)
        
        await session.commit()
              

        
