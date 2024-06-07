from db.crud.crud_base import CRUDBase
from db.models import Tournament
from db.db import get_async_session
import logging
from db.crud.player import crud_player
from db.crud.user import crud_user
from db.crud.tournament import crud_tournament
from aiogram.types import CallbackQuery


async def create_tournament_db(data):
    tournament_crud = CRUDBase(Tournament)
    async for session in get_async_session():
        tournament = await tournament_crud.create(data, session)
        return tournament
    
async def get_tournament(id):
    async for session in get_async_session():
        tournament = await crud_tournament.get(id, session)
        await session.refresh(tournament, ['user'])
        await session.refresh(tournament, ['players'])
        for player in tournament.players:
            await session.refresh(player, ['user'])
        return tournament
    
def get_all_tournaments(user):
    tournaments = set(user.tournaments)
    for player in user.players:
        if player.tournament:
            tournaments.add(player.tournament)
    return list(tournaments)
    
async def get_or_create_user(callback_query):
    data = {
        'username': callback_query.from_user.username,
        'name': f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}',
        'telegram_id': callback_query.from_user.id
        }
    async for session in get_async_session():
        try:
            existing_user = await crud_user.get_by_telegram_id(data['telegram_id'], session)
            if existing_user:
                await session.refresh(existing_user, ['tournaments', 'players'])
                for player in existing_user.players:
                    await session.refresh(player, ['tournament'])
                return existing_user
            user = await crud_user.create(data, session)
            logging.info(f'Добавлен новый пользователь {user.username}')
            await session.refresh(user, ['tournaments', 'players'])
            for player in user.players:
                await session.refresh(player, ['tournament'])
            return user
        except Exception:
            logging.error('Не удалось добавить пользователя в базу', exc_info=True)


async def create_player(data):
    async for session in get_async_session():
        try:
            existing_player = await crud_player.get_by_user_id(data['user_id'], data['tournament_id'], session)
            if existing_player:
                return existing_player
            player = await crud_player.create(data, session)
            await session.refresh(player, ['user'])
            logging.info(f'Добавлен новый игрок {player.user.username}')
            return player
        except Exception:
            logging.error('Не удалось добавить пользователя в базу', exc_info=True)


async def get_users_from_bd():
    async for session in get_async_session():
        await crud_user.get_multi()