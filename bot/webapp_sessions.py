import secrets
import time
from typing import NotRequired, TypedDict


SESSION_TTL_SECONDS = 3600


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


_sessions: dict[str, tuple[float, PredictionSession]] = {}
_user_sessions: dict[int, str] = {}


def create_prediction_session(
    matches: list[MatchPair],
    telegram_id: int | None = None,
    tournament_id: int | None = None,
    user_id: int | None = None,
) -> str:
    _cleanup_expired()
    session_id = secrets.token_urlsafe(9)
    _sessions[session_id] = (
        time.time(),
        {
            "matches": matches,
            "telegram_id": telegram_id,
            "tournament_id": tournament_id,
            "user_id": user_id,
        },
    )
    if telegram_id is not None:
        _user_sessions[telegram_id] = session_id
    return session_id


def get_prediction_session(session_id: str) -> PredictionSession | None:
    _cleanup_expired()
    entry = _sessions.get(session_id)
    if not entry:
        return None
    return entry[1]


def get_latest_session_for_user(telegram_id: int) -> list[MatchPair] | None:
    _cleanup_expired()
    session_id = _user_sessions.get(telegram_id)
    if not session_id:
        return None
    session = get_prediction_session(session_id)
    if not session:
        return None
    return session["matches"]


def _cleanup_expired() -> None:
    now = time.time()
    expired = [
        sid
        for sid, (created_at, _) in _sessions.items()
        if now - created_at > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)
    for telegram_id, session_id in list(_user_sessions.items()):
        if session_id not in _sessions:
            _user_sessions.pop(telegram_id, None)
