import logging
from typing import List

from bot.config import load_config
from bot.utils.random_distribution import add_player_to_group
from bot.utils.utils_tournament import get_tournament, get_tournament_for_menu
from db.crud.player import crud_player
from db.crud.user import crud_user
from db.db import get_async_session
from db.models import Player, Tournament, User
from sqlalchemy.orm import joinedload, object_session


async def get_or_create_user(callback_query):
    data = {
        "username": callback_query.from_user.username,
        "name": f"{callback_query.from_user.first_name} {callback_query.from_user.last_name}",
        "telegram_id": callback_query.from_user.id,
    }
    async for session in get_async_session():
        try:
            existing_user = await crud_user.get_by_telegram_id(
                data["telegram_id"], session
            )
            if existing_user:
                await session.refresh(existing_user, ["tournaments", "players"])
                for player in existing_user.players:
                    await session.refresh(player, ["tournament"])
                return existing_user
            user = await crud_user.create(data, session)
            logging.info(f"Добавлен новый пользователь {user.username}")
            await session.refresh(user, ["tournaments", "players"])
            for player in user.players:
                await session.refresh(player, ["tournament"])
            return user
        except Exception:
            logging.error("Не удалось добавить пользователя в базу", exc_info=True)


async def get_or_create_player(data):
    async for session in get_async_session():
        try:
            existing_player = await crud_player.get_by_user_id(
                data["user_id"], data["tournament_id"], session
            )
            if existing_player:
                await session.refresh(
                    existing_player,
                    ["user", "tournament_predictions", "match_predictions"],
                )
                return existing_player
            player = await crud_player.create(data, session)
            await session.refresh(
                player, ["user", "match_predictions", "tournament_predictions"]
            )
            logging.info(f"Добавлен новый игрок {player.user.username}")
            await session.commit()
            return player
        except Exception:
            logging.error("Не удалось добавить пользователя в базу", exc_info=True)


async def refresh_user(user_id: int) -> User | None:
    from sqlalchemy import select

    async for session in get_async_session():
        result = await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                joinedload(User.players).joinedload(Player.tournament),
                joinedload(User.tournaments),
            )
        )
        return result.scalars().first()


async def ensure_user_in_default_tournament(user: User) -> bool:
    config = load_config()
    tournament = await get_tournament_for_menu(config.default_tournament_id)
    if not tournament:
        logging.warning("Турнир id=%s не найден", config.default_tournament_id)
        return False

    async for session in get_async_session():
        existing_player = await crud_player.get_by_user_id(
            user.id, tournament.id, session
        )
        is_new = existing_player is None

    player = await get_or_create_player(
        {"user_id": user.id, "tournament_id": tournament.id}
    )
    if not player:
        return False

    from bot.utils.match_groups import splits_matches_by_groups

    if splits_matches_by_groups(tournament) and not player.group:
        await add_player_to_group(player, tournament)

    return is_new


async def eleminate_player(tournament: Tournament, users_to_eliminate: List[str]):
    async for session in get_async_session():
        for player in tournament.players:
            if player.user.username in users_to_eliminate:
                player.is_eliminated = True
                await session.merge(player)
        await session.commit()
