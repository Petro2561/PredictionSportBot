from sqlalchemy import select
from sqlalchemy.orm import joinedload

from bot.utils.common import get_tour
from db.crud.tour import crud_tour
from db.crud.tournament import crud_tournament
from db.db import get_async_session
from db.models import Match, Player, Tournament, TournamentPrediction, User


async def get_tournament(id: int) -> Tournament:
    async for session in get_async_session():
        tournament = await crud_tournament.get_tournament(id, session)
        return tournament


async def get_tournament_for_menu(id: int) -> Tournament:
    async for session in get_async_session():
        return await crud_tournament.get_tournament_for_menu(id, session)


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


async def save_predictions(data: dict) -> TournamentPrediction:
    async for session in get_async_session():
        prediction = TournamentPrediction(**data)
        session.add(prediction)
        await session.commit()
        return prediction


async def create_tour_in_db(data):
    async for session in get_async_session():
        tour = await crud_tour.create(data, session)
        session.add(tour)
        await session.commit()
        return tour


async def set_current_tour(tour, tournament):
    async for session in get_async_session():
        tournament.current_tour_id = tour.id
        session.add(tournament)
        await session.commit()


async def create_tour_for_tournament(data, tour_date):
    tournament = await get_tournament(data["tournament_id"])
    if tournament.current_tour_id:
        tour = await get_tour(tournament)
        data = {
            "number": tour.number + 1,
            "tournament_id": tournament.id,
            "next_deadline": tour_date,
            "split_matches_by_groups": True,
        }
        tour = await create_tour_in_db(data)
    else:
        data = {
            "number": 1,
            "tournament_id": tournament.id,
            "next_deadline": tour_date,
            "split_matches_by_groups": True,
        }
        tour = await create_tour_in_db(data)
    await set_current_tour(tour, tournament)
    return tour
