from aiogram import Bot, Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
import json

from bot.bot import main_bot
from bot.errors.error import PredictionValidationError
from bot.filters.filters import IsTournamentOwner
from bot.keyboards.callback_factory import TournamentCallbackFactory
from bot.keyboards.tournament_menu_keyboard import (
    create_tournament_keyboard,
    keyboard_menu,
    inline_keyboard_next,
    webapp_keyboard,
)
from bot.states.states import TournamentMenu
from bot.utils.common import get_tour, send_long_message
from bot.utils.points_results import calculate_prediction_results, player_points_calculation, reset_points
from bot.utils.random_distribution import get_group_history, get_tournament_prediction, random_distribution, show_distribution
from bot.utils.utils_match import create_match, create_match_prediction, get_match_by_id, get_match_by_teams, update_match_prediction_for_player, update_match_results, validate_prediction, validate_tour_date
from bot.utils.utils_tournament import (
    create_tour_for_tournament,
    eleminated_to_front,
    get_all_tournaments,
    get_tournament,
)
from bot.utils.utils_user_player import eleminate_player, get_or_create_player, get_or_create_user
from bot.utils.points_results import create_reset_points_obj
from db.db import get_async_session
from db.models import MatchPrediction, Player, Tour, Tournament, User
from bot.keyboards.creator_keyboard import yes_no_keyboard
from datetime import datetime, timedelta
import os
from pathlib import Path

router = Router()


@router.callback_query(lambda callback: callback.data == "my_tournaments")
async def create_tournament_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    user: User = await get_or_create_user(callback_query)
    await state.update_data(user=user)
    await state.set_state(TournamentMenu.tournament_menu)
    tournaments = get_all_tournaments(user)
    if not tournaments:
        await state.clear()
        await callback_query.message.answer("У вас нет турниров")
    elif len(tournaments) > 1:
        await callback_query.message.answer(
            "Выберите турнир", reply_markup=create_tournament_keyboard(user)
        )
    elif len(tournaments) == 1:
        tournament = await get_tournament(tournaments[0].id)
        player = await get_or_create_player({
            "tournament_id": tournament.id,
            "user_id": user.id
        })
        await state.update_data(player=player)
        await state.update_data(tournament=tournament)
        await callback_query.message.answer(
            f"Вы в турнире {tournament.name}",
            reply_markup= await keyboard_menu(tournament=tournament, user=user),
        )


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
        reply_markup=await keyboard_menu(tournament=tournament, user=data["user"]),
    )
    data = {
            "tournament_id": tournament.id,
            "user_id": data["user"].id
        }
    player = await get_or_create_player(data)
    await state.update_data(player=player)
    await callback_query.message.delete()

    await state.update_data(tournament=tournament)


@router.message(
    lambda message: message.text == "Посмотреть список участников",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_users(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament: Tournament = await get_tournament(data["tournament"].id)
    players = tournament.players
    users_info = "\n".join(
        [
            f"{index + 1}. {player.user.name} (@{player.user.username}) {eleminated_to_front(player)} {await get_tournament_prediction(player)}"
            for index, player in enumerate(players)
        ]
    )
    if not users_info:
        await message.answer("Нет участников в этом турнире.")
        await message.answer('Вы в главном меню', reply_markup=await keyboard_menu(user=data["user"], tournament=data["tournament"]))
    else:
        await message.answer(users_info, reply_markup=await keyboard_menu(user=data["user"], tournament=data["tournament"]))


@router.message(
    lambda message: message.text == "Провести жеребьевку",
    IsTournamentOwner(),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_group_number(message: Message, state: FSMContext):
    data = await state.get_data()
    players = data["tournament"].players
    player_in_play = [player for player in players if player.is_eliminated == False]
    await message.answer(f"В турнире {len(player_in_play)} участников")
    await message.answer(f"Введите число групп:")
    await state.set_state(TournamentMenu.groups)


@router.message(IsTournamentOwner(), StateFilter(TournamentMenu.groups))
async def get_random_distribution(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    number_of_groups = int(message.text)
    await message.answer(f"В турнире будет {number_of_groups} групп")
    result = await random_distribution(tournament, number_of_groups)
    # В идеале сразу отправлять в группу сообщения
    await message.answer(result)
    await state.set_state(TournamentMenu.tournament_menu)
    await message.answer('Вы в главном меню', reply_markup= await keyboard_menu(user=data["user"], tournament=tournament))

@router.message(
    lambda message: message.text == "Посмотреть таблицу",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_results(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    result = await calculate_prediction_results(tournament)
    if result:
        await player_points_calculation(tournament)
        groups = await get_group_history(tournament)
        if groups:
            tournament = await get_tournament(tournament.id)
            results = await show_distribution(groups.group_distribution, tournament.players)
            await message.answer(results, reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))
        else:
            await message.answer('Пока нет групп!', reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))
    else:
        await message.answer('Пока турнир не начался', reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))

@router.message(
    lambda message: message.text == "Установить матчи",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_date(message: Message, state: FSMContext):
    await message.answer('Введите дату начала тура в формате "2024-06-11 18:00:00" без кавычек:')
    await state.set_state(TournamentMenu.tour_date)

@router.message(StateFilter(TournamentMenu.tour_date))
async def validate_date(message: Message, state: FSMContext):
    date_text = message.text
    try:
        tour_date = datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S")
        data = await state.get_data()
        tour = await create_tour_for_tournament(data, tour_date)
        await state.update_data(tour=tour)
        await state.set_state(TournamentMenu.webapp_matches)
        await message.answer(f'Дата тура {tour_date} установлена. Теперь нажмите кнопку для ввода матча тура.', reply_markup=webapp_keyboard())
    except ValueError:
        await message.answer('Неправильный формат даты. Пожалуйста, введите дату в формате "2024-06-11 18:00:00" без кавычек.')


@router.message(lambda message: message.web_app_data, StateFilter(TournamentMenu.webapp_matches))
async def set_matches(web_app_message: Message, state: FSMContext):
    first_team = json.loads(web_app_message.web_app_data.data)['firstTeam']
    second_team = json.loads(web_app_message.web_app_data.data)['secondTeam']
    await web_app_message.answer(f'Матч: {first_team}-{second_team} добавлен!')
    data = await state.get_data()
    match = await create_match(data, first_team, second_team)
    await create_match_prediction(match, data["tournament"])
    await web_app_message.answer('Нажмите далее, если закончили', reply_markup=inline_keyboard_next)


@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.webapp_matches),
    IsTournamentOwner(),
)
async def process_callback_next_button(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(TournamentMenu.tournament_menu)
    data = await state.get_data()
    await callback_query.message.delete()
    await callback_query.message.answer('Матчи тура успешно заполнены', reply_markup=await keyboard_menu(user=data["user"], tournament=data["tournament"]))


@router.message(
    lambda message: message.text == "Посмотреть прогнозы игроков",
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_predictions(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    tour: Tour = await get_tour(tournament)
    if tour:
        if tour.next_deadline - datetime.now() < timedelta(hours=1):
            groups = await get_group_history(tournament)
            if groups:
                predictions = await show_distribution(groups.group_distribution, tournament.players, with_match_prediction=True)
                await send_long_message(message.chat.id, predictions, message.bot)
                await message.answer("Вы в главном меню", reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))
            else:
                await message.answer("Вначале проведите жеребьевку", reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))
        else:
            await message.answer('Прогнозы игроков будут доступны за час до тура', reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))
    else:
        await message.answer('Админ еще не установил матчи')

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
async def set_null(callback_query: CallbackQuery, state: FSMContext):
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
    await state.set_state(TournamentMenu.tournament_menu)
    await callback_query.message.answer('Вы в главном меню', reply_markup=await keyboard_menu(user=data["user"], tournament=tournament))

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
        reply_markup=await keyboard_menu(tournament=data["tournament"], user=data["user"]),
    )
    
@router.message(
    F.text == "Убрать игрока из турнира",
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
    await state.set_state(TournamentMenu.eleminate_player)
    await message.answer("Вводите username игроков для выбывания, без @:")

@router.message(StateFilter(TournamentMenu.eleminate_player), IsTournamentOwner())
async def input_players_to_eliminate(message: Message, state: FSMContext):
    data = await state.get_data()
    users_to_eliminate = data.get("users_to_eliminate", [])
    users_to_eliminate.append(message.text)
    await state.update_data(users_to_eliminate=users_to_eliminate)
    await message.answer(f"Игрок {message.text} добавлен в список для выбывания.")
    await message.answer('Если всех ввели, то нажмите "Далее', reply_markup=inline_keyboard_next)

@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.eleminate_player),
    IsTournamentOwner(),
)
async def process_callback_next_button(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    users_to_eliminate = data.get("users_to_eliminate", [])
    
    await eleminate_player(data["tournament"], users_to_eliminate)
    
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
    await state.set_state(TournamentMenu.tournament_menu)
    await callback_query.message.answer('Вы в главном меню', reply_markup=await keyboard_menu(user=data["user"], tournament=data["tournament"]))

    
@router.message(
    lambda message: message.text == "Сделать прогноз",
    StateFilter(TournamentMenu.tournament_menu),
)
async def give_prediction(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer('Тур уже начался или начинается раньше чем через час. Если вы не успели 😔, бот проставил вам 0-0 все матчи')


@router.message(lambda message: message.web_app_data,
    StateFilter(TournamentMenu.tournament_menu)
)
async def receive_prediction(web_app_message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    player: Player = await get_or_create_player(
        {
            "tournament_id": data["tournament"].id,
            "user_id": data["user"].id
        }
    )
    for match_json in json.loads(web_app_message.web_app_data.data):
        if match_json:
            first_team = match_json['firstTeam']
            second_team = match_json['secondTeam']
            first_team_score = match_json['firstScore']
            second_team_score = match_json['secondScore']
            match = await get_match_by_teams(tournament, first_team, second_team)
            await update_match_prediction_for_player(match_id=match.id, player_id=player.id, first_team_score=first_team_score, second_team_score=second_team_score)
    message_predictions = "Ваши прогнозы:\n"
    player: Player = await get_or_create_player(
        {
            "tournament_id": data["tournament"].id,
            "user_id": data["user"].id
        }
    )
    for prediction in player.match_predictions:
        if prediction.match.tour.id == tournament.current_tour_id:
            message_predictions += (f"{prediction.match.first_team}-{prediction.match.second_team}"
                                f" {prediction.first_team_score}-{prediction.second_team_score}\n")
    await web_app_message.answer(message_predictions, reply_markup= await keyboard_menu(user=data["user"], tournament=data["tournament"]))

@router.message(
    lambda message: message.text == "Сделать прогноз через текст",
    StateFilter(TournamentMenu.tournament_menu),
)
async def give_prediction(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    if tournament.current_tour_id:
        date_validation = await validate_tour_date(tournament)
        if date_validation:
            matches = [match for match in tournament.matches if tournament.current_tour_id == match.tour.id]
            matches.sort(key=lambda match: match.id)
            message_result = "Ваши матчи:"
            await message.answer(message_result)
            for match in matches:
                message_result = f'{match.id}.{match.first_team}-{match.second_team}'
                await message.answer(message_result)
            await state.set_state(TournamentMenu.match_predictions)
            await message.answer('Пишите каждый матч отдельным сообщением. \nНапример, 1.Германия-Шотландия 1-0\nОбязательно с номером и точкой.')
            await message.answer('Каждый матч отправляем отдельно.')
        else:
            await message.answer('Тур уже начался или начинается раньше чем через час. вы не успели 😔, бот проставил вам 0-0 все матчи')
    else:
        await message.answer('Админ еще не установил матчи')

@router.message(
    StateFilter(TournamentMenu.match_predictions),
)
async def receive_prediction(message: Message, state: FSMContext):
    try:
        prediction_text = message.text.strip()
        match_info, score_str = prediction_text.split(" ")
        match_id_str, teams_str = match_info.split(".")
        match_id = int(match_id_str)
        first_team, second_team = teams_str.split("-")
        first_team_score, second_team_score = map(int, score_str.split('-'))
        await validate_prediction(match_id, first_team, second_team)
        data = await state.get_data()
        player: Player = await get_or_create_player(
            {
                "tournament_id": data["tournament"].id,
                "user_id": data["user"].id
            }
        )
        await update_match_prediction_for_player(match_id=match_id, player_id=player.id, first_team_score=first_team_score, second_team_score=second_team_score)
        await message.answer("Ваш прогноз сохранен.")
        await message.answer('Нажмите далее, если закончили давать прогнозы', reply_markup=inline_keyboard_next)
    except ValueError:
        await message.answer(f"Скорее всего вы ошиблись при написании, пропробуйте еще. У вас получится. \nСо следующего тура будет удобнее!")
    except PredictionValidationError as e:
        await message.answer(e.message)

@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.match_predictions),
)
async def process_callback_next_button(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(TournamentMenu.tournament_menu)
    data = await state.get_data()
    await callback_query.message.delete()
    player: Player = await get_or_create_player(
        {
            "tournament_id": data["tournament"].id,
            "user_id": data["user"].id
        }
    )
    tournament = data["tournament"]
    current_tour_id = tournament.current_tour_id
    message_predictions = "Ваши прогнозы:\n"
    for prediction in player.match_predictions:
        if prediction.match.tour.id == current_tour_id:
            message_predictions += (f"{prediction.match.first_team}-{prediction.match.second_team}"
                                f" {prediction.first_team_score}-{prediction.second_team_score}\n")

    await callback_query.message.answer('Прогнозы на матчи тура успешно заполнены', reply_markup= await keyboard_menu(user=data["user"], tournament=data["tournament"]))
    await callback_query.message.answer(message_predictions)
    await callback_query.message.answer(f'Если хотите поменять прогнозы, просто начните заново и поменяйте нужный матч')
    root_dir = Path(os.getcwd())
    file_path = root_dir / 'prediction.txt'
    with file_path.open('w', encoding='utf-8') as txtfile:
        message_predictions += f'{player.user.username}_{player.user.name}'
        txtfile.write(message_predictions)


@router.message(
    lambda message: message.text == "Проставить результаты матчей",
    StateFilter(TournamentMenu.tournament_menu),
    IsTournamentOwner()
)
async def give_prediction(message: Message, state: FSMContext):
    data = await state.get_data()
    tournament = await get_tournament(data["tournament"].id)
    matches = [match for match in tournament.matches if tournament.current_tour_id == match.tour.id]
    matches.sort(key=lambda match: match.id)
    message_result = "Ваши матчи:"
    await message.answer(message_result)
    for match in matches:
        message_result = f'{match.id}.{match.first_team}-{match.second_team}'
        await message.answer(message_result)
    await state.set_state(TournamentMenu.match_results)
    await message.answer('Пишите каждый матч отдельным сообщением 1.Германия-Шотландия')


@router.message(
    StateFilter(TournamentMenu.match_results),
)
async def receive_prediction(message: Message, state: FSMContext):
    try:
        match_text = message.text.strip()
        match_info, score_str = match_text.split(" ")
        match_id_str, teams_str = match_info.split(".")
        match_id = int(match_id_str)
        first_team, second_team = teams_str.split("-")
        first_team_score, second_team_score = map(int, score_str.split('-'))
        await validate_prediction(match_id, first_team, second_team)
        await update_match_results(match_id, first_team_score, second_team_score)
        await message.answer("Результат матча сохранен.")
        await message.answer('Нажмите далее, если закончили вводить результаты', reply_markup=inline_keyboard_next)
    except ValueError:
        await message.answer(f"Скорее всего вы ошиблись при написании, пропробуйте еще")
    except PredictionValidationError as e:
        await message.answer(e.message)

@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.match_results),
    IsTournamentOwner(),
)
async def process_callback_next_button(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(TournamentMenu.tournament_menu)
    data = await state.get_data()
    await callback_query.message.delete()
    await callback_query.message.answer('Результаты на матчи тура успешно заполнены', reply_markup=await keyboard_menu(user=data["user"], tournament=data["tournament"]))