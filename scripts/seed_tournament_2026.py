"""Создание турнира «Турнир прогнозов 2026» с очками 4/2/1 и матчами 1-го тура."""

import asyncio
import os
from datetime import datetime

from sqlalchemy import delete, select, text

from bot.config import load_config
from db.db import AsyncSessionLocal
from db.models import Match, MatchPrediction, Tour, Tournament, User

TOURNAMENT_NAME = "Турнир прогнозов 2026"
COMPETITION_NAME = "FIFA World Cup 2026"
EXACT_SCORE_POINTS = 4
RESULTS_POINTS = 2
DIFFERENCE_POINTS = 1
TOUR_DEADLINE = datetime(2026, 6, 11, 18, 0, 0)

MATCHES = [
    ("Mexico", "South Africa"),
    ("Korea Republic", "Czechia"),
    ("Canada", "Bosnia and Herzegovina"),
    ("United States", "Paraguay"),
    ("Haiti", "Scotland"),
    ("Australia", "Turkey"),
    ("Brazil", "Morocco"),
    ("Qatar", "Switzerland"),
    ("Côte d'Ivoire", "Ecuador"),
    ("Germany", "Curaçao"),
    ("Netherlands", "Japan"),
    ("Sweden", "Tunisia"),
    ("Saudi Arabia", "Uruguay"),
    ("Spain", "Cabo Verde"),
    ("Belgium", "Egypt"),
    ("Iran", "New Zealand"),
    ("France", "Senegal"),
    ("Iraq", "Norway"),
    ("Argentina", "Algeria"),
    ("Austria", "Jordan"),
    ("Ghana", "Panama"),
    ("England", "Croatia"),
    ("Portugal", "Congo DR"),
    ("Uzbekistan", "Colombia"),
]


async def _get_or_create_owner(session, admin_telegram_id: int) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == admin_telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        username=f"admin_{admin_telegram_id}",
        name="Admin",
        telegram_id=admin_telegram_id,
    )
    session.add(user)
    await session.flush()
    return user


async def seed() -> None:
    config = load_config()
    admin_telegram_id = config.tg_bot.admin_ids[0] if config.tg_bot.admin_ids else 0
    tournament_id = config.default_tournament_id

    async with AsyncSessionLocal() as session:
        owner = await _get_or_create_owner(session, admin_telegram_id)

        tournament = await session.get(Tournament, tournament_id)
        if tournament is None:
            tournament = Tournament(
                id=tournament_id,
                name=TOURNAMENT_NAME,
                exact_score_points=EXACT_SCORE_POINTS,
                results_points=RESULTS_POINTS,
                difference_points=DIFFERENCE_POINTS,
                competition_official_name=COMPETITION_NAME,
                user_id=owner.id,
            )
            session.add(tournament)
            await session.flush()
        else:
            tournament.name = TOURNAMENT_NAME
            tournament.exact_score_points = EXACT_SCORE_POINTS
            tournament.results_points = RESULTS_POINTS
            tournament.difference_points = DIFFERENCE_POINTS
            tournament.competition_official_name = COMPETITION_NAME
            tournament.user_id = owner.id

        tour = tournament.current_tour
        if tour is None:
            result = await session.execute(
                select(Tour).where(
                    Tour.tournament_id == tournament.id,
                    Tour.number == 1,
                )
            )
            tour = result.scalar_one_or_none()

        if tour is None:
            tour = Tour(
                number=1,
                tournament_id=tournament.id,
                next_deadline=TOUR_DEADLINE,
                split_matches_by_groups=True,
            )
            session.add(tour)
            await session.flush()
        else:
            tour.number = 1
            tour.next_deadline = TOUR_DEADLINE
            tour.split_matches_by_groups = True

        tournament.current_tour_id = tour.id

        await session.execute(
            delete(MatchPrediction).where(
                MatchPrediction.match_id.in_(
                    select(Match.id).where(Match.tournament_id == tournament.id)
                )
            )
        )
        await session.execute(
            delete(Match).where(Match.tournament_id == tournament.id)
        )
        for first_team, second_team in MATCHES:
            session.add(
                Match(
                    first_team=first_team,
                    second_team=second_team,
                    tour_id=tour.id,
                    tournament_id=tournament.id,
                )
            )

        await session.commit()

        if os.getenv("DATABASE_URL", "").startswith("postgresql"):
            async with AsyncSessionLocal() as seq_session:
                await seq_session.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence('tournament', 'id'), "
                        "COALESCE((SELECT MAX(id) FROM tournament), 1))"
                    )
                )
                await seq_session.commit()

    print(f"Турнир создан: {TOURNAMENT_NAME} (id={tournament_id})")
    print(f"Очки: точный счёт={EXACT_SCORE_POINTS}, исход={RESULTS_POINTS}, разница={DIFFERENCE_POINTS}")
    print(f"Тур 1, дедлайн: {TOUR_DEADLINE}")
    print(f"Матчей: {len(MATCHES)}")


if __name__ == "__main__":
    asyncio.run(seed())
