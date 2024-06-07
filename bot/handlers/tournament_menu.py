from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.bot import main_bot
from bot.filters.filters import IsTournamentOwner
from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.keyboards.tournament_menu_keyboard import (
    create_tournament_keyboard,
    keyboard_menu,
)
from bot.states.states import TournamentMenu
from bot.utils.random_distribution import random_distribution
from bot.utils.utils_tournament import (
    eleminated_to_front,
    get_all_tournaments,
    get_tournament,
)
from bot.utils.utils_user_player import get_or_create_user
from db.models import Tournament, User

router = Router()


@router.callback_query(lambda callback: callback.data == "my_tournaments")
async def create_tournament_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    user: User = await get_or_create_user(callback_query)
    await state.update_data(user=user)
    await state.set_state(TournamentMenu.tournament_menu)
    tournaments = get_all_tournaments(user)
    if len(tournaments) > 1:
        await callback_query.message.answer(
            "Выберите турнир", reply_markup=create_tournament_keyboard(user)
        )
    elif len(tournaments) == 1:
        tournament = await get_tournament(tournaments[0].id)
        await state.update_data(tournament=tournament)
        await callback_query.message.answer(
            f"Вы в турнире {tournament.name}",
            reply_markup=keyboard_menu(tournament=tournament, user=user),
        )
    else:
        await callback_query.message.answer("У вас нет турниров")


@router.callback_query(
    TournamentCallbackFactory.filter(), StateFilter(TournamentMenu.tournament_menu)
)
async def process_callback_tournament(
    callback_query: CallbackQuery,
    callback_data: TournamentCallbackFactory,
    state: FSMContext,
):
    tournament: Tournament = await get_tournament(callback_data.id)
    data = await state.get_data()
    await callback_query.message.answer(
        f"Вы в турнире {tournament.name}",
        reply_markup=keyboard_menu(tournament=tournament, user=data["user"]),
    )
    await callback_query.message.delete()

    await state.update_data(tournament=tournament)


@router.message(
    lambda message: message.text == "Посмотреть список участников",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_users(message: Message, state: FSMContext):
    data = await state.get_data()
    players = data["tournament"].players
    users_info = "\n".join(
        [
            f"{player.user.name} (@{player.user.username}) {eleminated_to_front(player)}"
            for player in players
        ]
    )
    if not users_info:
        await message.answer("Нет участников в этом турнире.")
    else:
        await message.answer(users_info)


@router.message(
    lambda message: message.text == "Провести жеребьевку",
    IsTournamentOwner(),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_users(message: Message, state: FSMContext):
    data = await state.get_data()
    players = data["tournament"].players
    await message.answer(f"В турнире {len(players)} участников")
    await message.answer(f"Введите число групп:")
    await state.set_state(TournamentMenu.groups)


@router.message(IsTournamentOwner(), StateFilter(TournamentMenu.groups))
async def get_users(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    number_of_groups = int(message.text)
    await message.answer(f"В турнире будет {number_of_groups}")
    result = await random_distribution(tournament, number_of_groups)
    # В идеале сразу отправлять в группу сообщения
    await message.answer(result)
    await state.clear()
