from sqlalchemy import select

from bot.utils.match_groups import (
    get_matches_for_player,
    get_total_groups,
    splits_matches_by_groups,
)
from bot.utils.utils_match import (
    get_match_by_teams,
    predictions_allowed,
    update_match_prediction_for_player,
)
from bot.utils.utils_tournament import get_tournament
from bot.utils.utils_user_player import get_or_create_player
from bot.webapp_sessions import MatchPair
from db.db import get_async_session
from db.models import MatchPrediction


async def _load_existing_predictions_by_match(
    player_id: int, match_ids: list[int]
) -> dict[int, MatchPrediction]:
    if not match_ids:
        return {}
    async for session in get_async_session():
        result = await session.execute(
            select(MatchPrediction).where(
                MatchPrediction.player_id == player_id,
                MatchPrediction.match_id.in_(match_ids),
            )
        )
        return {
            prediction.match_id: prediction for prediction in result.scalars()
        }
    return {}


async def build_prediction_form_matches(player, tournament) -> list[MatchPair]:
    total_groups = await get_total_groups(tournament)
    matches = get_matches_for_player(player, tournament, total_groups)
    existing = await _load_existing_predictions_by_match(
        player.id, [match.id for match in matches]
    )

    form_matches: list[MatchPair] = []
    for match in matches:
        prediction = existing.get(match.id)
        form_matches.append(
            {
                "firstTeam": match.first_team,
                "secondTeam": match.second_team,
                "firstScore": (
                    prediction.first_team_score if prediction is not None else 0
                ),
                "secondScore": (
                    prediction.second_team_score if prediction is not None else 0
                ),
            }
        )
    return form_matches


async def save_player_predictions(
    tournament_id: int, user_id: int, predictions: list[dict]
) -> str:
    tournament = await get_tournament(tournament_id)
    if not await predictions_allowed(tournament):
        raise ValueError(
            "Приём прогнозов закрыт — тур уже начался или до начала меньше часа."
        )
    player = await get_or_create_player(
        {"tournament_id": tournament_id, "user_id": user_id}
    )
    if splits_matches_by_groups(tournament) and not player.group:
        raise ValueError(
            "Сначала проведите жеребьевку — от группы зависит, какие 12 матчей тура вы прогнозируете."
        )

    total_groups = await get_total_groups(tournament)
    allowed_match_ids = {
        match.id
        for match in get_matches_for_player(player, tournament, total_groups)
    }

    for match_json in predictions:
        if not match_json:
            continue
        first_team = match_json["firstTeam"]
        second_team = match_json["secondTeam"]
        first_team_score = match_json["firstScore"]
        second_team_score = match_json["secondScore"]
        match = await get_match_by_teams(tournament, first_team, second_team)
        if match.id not in allowed_match_ids:
            continue
        await update_match_prediction_for_player(
            match_id=match.id,
            player_id=player.id,
            first_team_score=first_team_score,
            second_team_score=second_team_score,
        )

    player = await get_or_create_player(
        {"tournament_id": tournament_id, "user_id": user_id}
    )
    message_predictions = "Ваши прогнозы:\n"
    for prediction in player.match_predictions:
        if (
            prediction.match.tour.id == tournament.current_tour_id
            and prediction.match_id in allowed_match_ids
        ):
            message_predictions += (
                f"{prediction.match.first_team}-{prediction.match.second_team}"
                f" {prediction.first_team_score}-{prediction.second_team_score}\n"
            )
    return message_predictions
