from aiogram import Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.bot import main_bot
from bot.filters.filters import IsTournamentOwner
from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.keyboards.tournament_menu_keyboard import (
    create_tournament_keyboard,
    keyboard_menu,
    inline_keyboard_next
)
from bot.states.states import TournamentMenu
from bot.utils.common import send_long_message
from bot.utils.points_results import calculate_prediction_results, player_points_calculation, reset_points
from bot.utils.random_distribution import get_group_history, random_distribution, show_distribution
from bot.utils.utils_tournament import (
    eleminated_to_front,
    get_all_tournaments,
    get_tournament,
)
from bot.utils.utils_user_player import get_or_create_user
from bot.utils.points_results import create_reset_points_obj
from db.db import get_async_session
from db.models import Tournament, User
from db.crud.group_history import crud_group_history
from bot.keyboards.creator_keyboard import yes_no_keyboard

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
async def get_group_number(message: Message, state: FSMContext):
    data = await state.get_data()
    players = data["tournament"].players
    await message.answer(f"В турнире {len(players)} участников")
    await message.answer(f"Введите число групп:")
    await state.set_state(TournamentMenu.groups)


@router.message(IsTournamentOwner(), StateFilter(TournamentMenu.groups))
async def get_random_distribution(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    number_of_groups = int(message.text)
    await message.answer(f"В турнире будет {number_of_groups} групп")
    result = await random_distribution(tournament, number_of_groups)
    # В идеале сразу отправлять в группу сообщения
    await message.answer(result)
    await state.clear()

@router.message(
    lambda message: message.text == "Посмотреть таблицу",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_results(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    result = await calculate_prediction_results(tournament)
    if result:
        await player_points_calculation(tournament)
        groups = await get_group_history(tournament)
        if groups:
            tournament = await get_tournament(tournament.id)
            results = await show_distribution(groups.group_distribution, tournament.players)
            await message.answer(results)
        else:
            await message.answer('Пока нет групп!')
    else:
        await message.answer('Пока турнир не начался')


@router.message(
    lambda message: message.text == "Установить мачти",
    StateFilter(TournamentMenu.tournament_menu),
    IsTournamentOwner()
)
async def set_matches(message: Message, state: FSMContext):
    ### Вот здесь хэндлер для webapp
    pass


@router.message(
    lambda message: message.text == "Посмотреть прогнозы игроков",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_predictions(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    groups = await get_group_history(tournament)
    predictions = await show_distribution(groups.group_distribution, tournament.players, with_match_prediction=True)
    await send_long_message(message.chat.id, predictions, message.bot)


@router.message(
    lambda message: message.text == "Обнулить очки игрокам",
    StateFilter(TournamentMenu.tournament_menu),
    IsTournamentOwner()
)
async def set_matches(message: Message, state: FSMContext):
    await message.answer('Вы уверены?', reply_markup=yes_no_keyboard)
    await state.set_state(TournamentMenu.reset_points)

@router.callback_query(
    lambda callback: callback.data == "yes",
    StateFilter(TournamentMenu.reset_points),
    IsTournamentOwner()
)
async def fill_winner(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    await state.update_data(winner=callback_query.data == "yes")
    await callback_query.message.delete()
    await create_reset_points_obj(tournament)
    await reset_points(tournament)
    groups = await get_group_history(tournament)
    tournament = await get_tournament(tournament.id)
    results = await show_distribution(groups.group_distribution, tournament.players)
    await callback_query.message.answer(results)

@router.callback_query(
    lambda callback: callback.data == "no",
    IsTournamentOwner(),
    StateFilter(TournamentMenu.reset_points),
)
async def fill_winner(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    data = await state.get_data()
    await state.set_state(TournamentMenu.tournament_menu)
    await callback_query.message.answer(
        'Все хорошо ничего не удалилось',
        reply_markup=keyboard_menu(tournament=data["tournament"], user=data["user"]),
    )
    
@router.message(
    lambda message: message.text == "Убрать игрока из турнира",
    IsTournamentOwner(),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_predictions(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    players = data["tournament"].players
    users_info = "\n".join(
        [
            f"{player.user.name} (@{player.user.username}) {eleminated_to_front(player)}"
            for player in players
        ]
    )
    await message.answer(users_info)
    await message.answer("Вводите username игроков для выбывания, без @:")

@router.message(StateFilter(TournamentMenu.tournament_menu), IsTournamentOwner())
async def input_players_to_eliminate(message: Message, state: FSMContext):
    data = await state.get_data()
    users_to_eliminate = data.get("users_to_eliminate", [])
    users_to_eliminate.append(message.text)
    await state.update_data(users_to_eliminate=users_to_eliminate)
    await message.answer(f"Игрок {message.text} добавлен в список для выбывания.")
    await message.answer('Если всех ввели, то нажмите "Далее', reply_markup=inline_keyboard_next)

@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.tournament_menu),
    IsTournamentOwner(),
)
async def process_callback_next_button(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = data["tournament"]
    users_to_eliminate = data.get("users_to_eliminate", [])
    
    async for session in get_async_session():
        for player in tournament.players:
            if player.user.username in users_to_eliminate or player.user.name in users_to_eliminate:
                player.is_eliminated = True
                session.add(player)
        await session.commit()
    
    await callback_query.message.answer("Игроки удалены из турнира.")
    await state.update_data(users_to_eliminate=[])

    await callback_query.message.delete()
    players = data["tournament"].players    
    users_info = "\n".join(
        [
            f"{player.user.name} (@{player.user.username}) {eleminated_to_front(player)}"
            for player in players
        ]
    )
    await callback_query.message.answer(users_info)

    
