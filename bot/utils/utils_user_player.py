import logging

from db.crud.player import crud_player
from db.crud.user import crud_user
from db.db import get_async_session


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
                await session.refresh(existing_player, ["user", "tournament_predictions", "match_predictions"])
                return existing_player
            player = await crud_player.create(data, session)
            await session.refresh(player, ["user", "match_predictions", "tournament_predictions"])
            logging.info(f"Добавлен новый игрок {player.user.username}")
            return player
        except Exception:
            logging.error("Не удалось добавить пользователя в базу", exc_info=True)

async def eleminate_player(tournament, users_to_eliminate):
    async for session in get_async_session():
        for player in tournament.players:
            if player.user.username in users_to_eliminate:
                player.is_eliminated = True
                session.add(player)
        await session.commit()