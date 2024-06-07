from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.filters.filters import IsTournamentOwner
from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.keyboards.tournament_menu_keyboard import create_tournament_keyboard, keyboard_menu
from bot.states.states import TournamentMenu
from bot.utils.utils import get_all_tournaments, get_or_create_user, get_tournament
from db.models import Tournament, User
from aiogram.filters import StateFilter

router = Router()

@router.callback_query(lambda callback: callback.data == "my_tournaments")
async def create_tournament_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    user: User = await get_or_create_user(callback_query)
    await state.update_data(user=user)
    await state.set_state(TournamentMenu.tournament_menu)
    tournaments = get_all_tournaments(user)
    if len(tournaments) > 1:
        await callback_query.message.answer('Выберите турнир', reply_markup=create_tournament_keyboard(user))
    elif len(tournaments) == 1:
        tournament = await get_tournament(tournaments[0].id)
        await state.update_data(tournament=tournament)
        await callback_query.message.answer(f'Вы в турнире {tournament.name}', reply_markup=keyboard_menu(tournament=tournament, user=user))
    else:
        await callback_query.message.answer('У вас нет турниров')

@router.callback_query(TournamentCallbackFactory.filter(), StateFilter(TournamentMenu.tournament_menu))
async def process_callback_tournament(callback_query: CallbackQuery, callback_data: TournamentCallbackFactory, state: FSMContext):
    tournament: Tournament = await get_tournament(callback_data.id)
    data = await state.get_data()
    await callback_query.message.answer(f'Вы в турнире {tournament.name}', reply_markup=keyboard_menu(tournament=tournament, user=data['user'] ))
    await callback_query.message.delete()
    await state.update_data(tournament=tournament)

@router.message(lambda message: message.text == "Посмотреть список участников", IsTournamentOwner(), StateFilter(TournamentMenu.tournament_menu))
async def get_users(message: Message, state: FSMContext):
    data = await state.get_data()
    players = data['tournament'].players
    users_info = "\n".join([f"{player.user.name} (@{player.user.username})" for player in players])
    if not users_info:
        await message.answer("Нет участников в этом турнире.")
    else:
        await message.answer(users_info)

# @router.message(lambda message: message.text == "Провести жеребьевку", IsTournamentOwner(), StateFilter(TournamentMenu.tournament_menu))
# async def get_users(message: Message, state: FSMContext):
#     data = await state.get_data()
#     players = data['tournament'].players
#     users_info = "\n".join([f"{player.user.name} (@{player.user.username})" for player in players])
#     await message.answer(users_info)










# Провести жеребьевку
# Посмотреть участников
# Провести жеребьевку
# Обнулить очки