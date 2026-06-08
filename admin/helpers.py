from functools import lru_cache

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload

from db.db import DATABASE_URL
from db.models import Player, TournamentPrediction

SYNC_DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")


@lru_cache(maxsize=1)
def _sync_engine():
    return create_engine(SYNC_DATABASE_URL)


def get_player_label(player_id: int | None) -> str:
    if not player_id:
        return "—"
    with Session(_sync_engine()) as session:
        player = session.execute(
            select(Player)
            .options(joinedload(Player.user))
            .where(Player.id == player_id)
        ).scalar_one_or_none()
        if not player:
            return f"#{player_id}"
        user = player.user
        if user:
            return user.name or user.username or f"#{player_id}"
        return f"#{player_id}"


def get_tournament_prediction(
    player_id: int, tournament_id: int | None = None
) -> TournamentPrediction | None:
    with Session(_sync_engine()) as session:
        query = select(TournamentPrediction).where(
            TournamentPrediction.player_id == player_id
        )
        if tournament_id is not None:
            query = query.where(TournamentPrediction.tournament_id == tournament_id)
        return session.execute(query).scalar_one_or_none()


def get_prediction_striker(player_id: int, tournament_id: int | None = None) -> str:
    prediction = get_tournament_prediction(player_id, tournament_id)
    return prediction.best_striker if prediction and prediction.best_striker else "—"


def get_prediction_assistant(player_id: int, tournament_id: int | None = None) -> str:
    prediction = get_tournament_prediction(player_id, tournament_id)
    return prediction.best_assistant if prediction and prediction.best_assistant else "—"
