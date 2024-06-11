from db.crud.crud_base import CRUDBase
from db.crud.tournament import crud_tournament
from db.db import get_async_session
from db.models import Player, Tournament, User


async def create_tournament_db(data: dict) -> Tournament:
    tournament_crud = CRUDBase(Tournament)
    async for session in get_async_session():
        tournament = await tournament_crud.create(data, session)
        return tournament


async def get_tournament(id: int) -> Tournament:
    async for session in get_async_session():
        tournament = await crud_tournament.get(id, session)
        await session.refresh(tournament, ["user"])
        await session.refresh(tournament, ["players"])
        await session.refresh(tournament, ["current_tour_id"])
        for player in tournament.players:
            await session.refresh(player, ["user"])
        return tournament


def get_all_tournaments(user: User) -> Tournament:
    tournaments = set(user.tournaments)
    for player in user.players:
        if player.tournament:
            tournaments.add(player.tournament)
    return list(tournaments)


def eleminated_to_front(player: Player) -> str:
    return "Выбыл ❌" if player.is_eliminated else "В игре 💪"

async def eliminate_player_from_tournament(tournament: Tournament, players):
    pass