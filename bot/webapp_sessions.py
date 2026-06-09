import json
import os
import secrets
from typing import TypedDict

import redis

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


SESSION_TTL_SECONDS = 3600
_SESSION_PREFIX = "prediction_session:"
_USER_PREFIX = "prediction_user:"

_redis: redis.Redis | None = None


class MatchPair(TypedDict):
    firstTeam: str
    secondTeam: str
    firstScore: NotRequired[int]
    secondScore: NotRequired[int]


class PredictionSession(TypedDict):
    matches: list[MatchPair]
    telegram_id: NotRequired[int | None]
    tournament_id: NotRequired[int | None]
    user_id: NotRequired[int | None]


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
    return _redis


def _session_key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


def _user_key(telegram_id: int) -> str:
    return f"{_USER_PREFIX}{telegram_id}"


def create_prediction_session(
    matches: list[MatchPair],
    telegram_id: int | None = None,
    tournament_id: int | None = None,
    user_id: int | None = None,
) -> str:
    session_id = secrets.token_urlsafe(9)
    payload: PredictionSession = {
        "matches": matches,
        "telegram_id": telegram_id,
        "tournament_id": tournament_id,
        "user_id": user_id,
    }
    client = _get_redis()
    client.setex(
        _session_key(session_id),
        SESSION_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False),
    )
    if telegram_id is not None:
        client.setex(_user_key(telegram_id), SESSION_TTL_SECONDS, session_id)
    return session_id


def get_prediction_session(session_id: str) -> PredictionSession | None:
    raw = _get_redis().get(_session_key(session_id))
    if not raw:
        return None
    return json.loads(raw)


def get_latest_session_for_user(telegram_id: int) -> list[MatchPair] | None:
    session_id = _get_redis().get(_user_key(telegram_id))
    if not session_id:
        return None
    session = get_prediction_session(session_id)
    if not session:
        return None
    return session["matches"]
