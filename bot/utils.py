import logging

from db.crud_base import CRUDBase
from db.db import get_async_session
from db.models import Tournament, User


async def create_tournament_db(data):
    tournament_crud = CRUDBase(Tournament)
    async for session in get_async_session():
        tournament = await tournament_crud.create(data, session)
        return tournament


async def create_user(data):
    user_crud = CRUDBase(User)
    async for session in get_async_session():
        try:
            existing_user = await user_crud.get_by_telegram_id(
                data["telegram_id"], session
            )
            if existing_user:
                return existing_user
            tournament = await user_crud.create(data, session)
            return tournament
        except Exception:
            logging.error("Не удалось добавить пользователя в базу", exc_info=True)
