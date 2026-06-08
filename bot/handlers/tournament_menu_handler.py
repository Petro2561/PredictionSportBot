import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from bot.errors.error import PredictionValidationError
from bot.filters.filters import PrivateChatFilter
from bot.keyboards.callback_factory import (DrawGroupsCallbackFactory,
                                            MenuCallbackFactory,
                                            TournamentCallbackFactory)
from bot.keyboards.tournament_menu_keyboard import (create_tournament_keyboard,
                                                    draw_groups_count_keyboard,
                                                    generate_link,
                                                    inline_keyboard_next,
                                                    keyboard_menu,
                                                    prediction_form_keyboard)
from bot.config import is_bot_admin, load_config
from bot.states.states import TournamentMenu
from bot.utils.tournament_predictions import (
    ensure_tournament_prediction_flags,
    get_missing_prediction_fields,
    start_next_prediction_prompt,
)
from bot.utils.common import get_tour, send_long_message
from bot.utils.google_sheets import (
    get_configured_spreadsheet_url,
    sync_google_spreadsheet,
    tour_has_started,
    tour_starts_at,
)
from bot.utils.random_distribution import (get_group_history,
                                           get_tournament_prediction,
                                           random_distribution,
                                           show_distribution)
from bot.utils.match_groups import (
    get_half_boundary,
    get_half_label,
    get_matches_for_player,
    get_total_groups,
    get_tour_matches_sorted,
    splits_matches_by_groups,
    validate_player_match_access,
)
from bot.utils.points_results import recalculate_tournament_points
from bot.utils.prediction_submit import save_player_predictions
from bot.utils.utils_match import (update_match_prediction_for_player,
                                   validate_prediction,
                                   validate_tour_date)
from bot.utils.utils_tournament import (eleminated_to_front,
                                        get_all_tournaments, get_tournament)
from bot.utils.utils_user_player import (ensure_user_in_default_tournament,
                                         get_or_create_player,
                                         get_or_create_user, refresh_user)
from db.models import Player, Tour, Tournament, User

router = Router()
logger = logging.getLogger(__name__)


async def enter_tournament_menu(
    user: User, state: FSMContext, telegram_id: int | None = None
) -> tuple[str, InlineKeyboardMarkup | None]:
    is_new_player = await ensure_user_in_default_tournament(user)
    refreshed_user = await refresh_user(user.id)
    if refreshed_user:
        user = refreshed_user

    await state.update_data(user_id=user.id)
    await state.set_state(TournamentMenu.tournament_menu)
    tournaments = get_all_tournaments(user)
    if not tournaments:
        await state.clear()
        return "У вас нет турниров", None
    if len(tournaments) > 1:
        return "Выберите турнир", create_tournament_keyboard(user)
    tournament = await get_tournament(tournaments[0].id)
    await state.update_data(tournament_id=tournament.id)
    greeting = f"Вы в турнире {tournament.name}"
    if is_new_player:
        greeting = f"Вы добавлены в турнир «{tournament.name}»"
    return (
        greeting,
        await keyboard_menu(
            tournament_id=tournament.id,
            user_id=user.id,
            telegram_id=telegram_id,
        ),
    )


@router.message(CommandStart(deep_link=False), PrivateChatFilter())
async def process_start_command(message: Message, state: FSMContext):
    user: User = await get_or_create_user(message)
    if not user:
        await message.answer("Не удалось загрузить профиль. Попробуйте позже.")
        return

    is_new_player = await ensure_user_in_default_tournament(user)
    refreshed_user = await refresh_user(user.id)
    if refreshed_user:
        user = refreshed_user

    config = load_config()
    await ensure_tournament_prediction_flags(config.default_tournament_id)
    tournament = await get_tournament(config.default_tournament_id)
    player = await get_or_create_player(
        {"user_id": user.id, "tournament_id": tournament.id}
    )
    await state.update_data(
        user_id=user.id, tournament_id=tournament.id, player_id=player.id
    )

    missing = get_missing_prediction_fields(player, tournament)
    if missing:
        if is_new_player:
            await message.answer(f"Вы добавлены в турнир «{tournament.name}»")
        await start_next_prediction_prompt(message, state, missing[0])
        return

    text, reply_markup = await enter_tournament_menu(
        user, state, telegram_id=message.from_user.id
    )
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(lambda callback: callback.data == "my_tournaments")
async def open_tournaments_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.delete()
    user: User = await get_or_create_user(callback_query)
    text, reply_markup = await enter_tournament_menu(
        user, state, telegram_id=callback_query.from_user.id
    )
    await callback_query.message.answer(text, reply_markup=reply_markup)


@router.callback_query(
    TournamentCallbackFactory.filter(), StateFilter(TournamentMenu.tournament_menu)
)
async def process_callback_tournament(
    callback_query: CallbackQuery,
    callback_data: TournamentCallbackFactory,
    state: FSMContext,
):
    await callback_query.answer()
    tournament: Tournament = await get_tournament(callback_data.id)
    data = await state.get_data()
    await callback_query.message.answer(
        f"Вы в турнире {tournament.name}",
        reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"]),
    )
    data = {"tournament_id": tournament.id, "user_id": data["user_id"]}
    await callback_query.message.delete()
    await state.update_data(tournament_id=tournament.id)


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "show_players"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_users(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    tournament: Tournament = await get_tournament(data["tournament_id"])
    players = tournament.players
    users_info = "\n".join(
        [
            f"{index + 1}. {player.user.name} (@{player.user.username}) {eleminated_to_front(player)} {await get_tournament_prediction(player)}"
            for index, player in enumerate(players)
        ]
    )
    if not users_info:
        await callback_query.message.answer("Нет участников в этом турнире.")
        await callback_query.message.answer(
            "Вы в главном меню",
            reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"])
        )
    else:
        await callback_query.message.answer(
            users_info,
            reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"]),
        )


async def _answer_sheet_sync_error(
    callback_query: CallbackQuery, tournament: Tournament, user_id: int, error: Exception
):
    if isinstance(error, FileNotFoundError):
        logger.exception("Google Sheets: файл сервисного аккаунта не найден")
        text = f"Не удалось обновить таблицу: {error}"
    elif isinstance(error, ValueError):
        text = str(error)
    else:
        logger.exception("Не удалось обновить Google Таблицу")
        text = "Не удалось обновить Google Таблицу. Проверьте настройки Google API."
    await callback_query.message.answer(
        text,
        reply_markup=await keyboard_menu(
            tournament_id=tournament.id,
            user_id=user_id,
            telegram_id=callback_query.from_user.id,
        ),
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "show_table"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_results(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    tour = await get_tour(tournament)
    menu = await keyboard_menu(
        tournament_id=tournament.id,
        user_id=data["user_id"],
        telegram_id=callback_query.from_user.id,
    )

    if not tour:
        await callback_query.message.answer("Матчи тура ещё не установлены", reply_markup=menu)
        return

    sheet_url = get_configured_spreadsheet_url()
    if not sheet_url:
        await callback_query.message.answer(
            "Google Таблица не настроена. Укажите GOOGLE_SPREADSHEET_ID в .env",
            reply_markup=menu,
        )
        return

    tournament = await get_tournament(tournament.id)
    if tour_has_started(tournament):
        message = f"Таблица с прогнозами игроков:\n{sheet_url}"
    else:
        starts_at = tour_starts_at(tournament)
        when_text = (
            starts_at.strftime("%d.%m.%Y в %H:%M") if starts_at else "после начала тура"
        )
        message = (
            f"Таблица турнира:\n{sheet_url}\n\n"
            f"Сейчас заполнены все 24 матча 1-го тура "
            f"(группы прогнозируют разные половины). "
            f"Прогнозы игроков появятся после начала тура ({when_text}). "
            f"Админ может обновить таблицу вручную."
        )

    await callback_query.message.answer(
        message,
        reply_markup=menu,
        disable_web_page_preview=False,
    )


def _active_players_count(tournament: Tournament) -> int:
    return sum(1 for player in tournament.players if not player.is_eliminated)


async def _validate_draw_prerequisites(
    tournament: Tournament, user_id: int, telegram_id: int
) -> tuple[str | None, InlineKeyboardMarkup | None]:
    menu = await keyboard_menu(
        tournament_id=tournament.id,
        user_id=user_id,
        telegram_id=telegram_id,
    )
    if not splits_matches_by_groups(tournament):
        return "Текущий тур не делит матчи по группам — жеребьёвка не нужна.", menu
    if _active_players_count(tournament) < 2:
        return "Недостаточно участников для жеребьёвки (нужно минимум 2).", menu
    return None, menu


async def _execute_draw_groups(
    message: Message,
    tournament_id: int,
    user_id: int,
    telegram_id: int,
    number_of_groups: int,
) -> None:
    tournament = await get_tournament(tournament_id)
    menu = await keyboard_menu(
        tournament_id=tournament.id,
        user_id=user_id,
        telegram_id=telegram_id,
    )
    max_groups = _active_players_count(tournament)
    if number_of_groups < 2 or number_of_groups > max_groups:
        await message.answer(
            f"Число групп должно быть от 2 до {max_groups}.",
            reply_markup=menu,
        )
        return

    await message.answer(f"Провожу жеребьёвку на {number_of_groups} групп...")
    result = await random_distribution(tournament, number_of_groups)
    if not result:
        await message.answer(
            "Не удалось провести жеребьёвку. Попробуйте ещё раз.",
            reply_markup=menu,
        )
        return

    await send_long_message(message.chat.id, result, message.bot)
    await message.answer("Жеребьёвка завершена.", reply_markup=menu)


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "admin_draw_groups"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def admin_draw_groups(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_bot_admin(callback_query.from_user.id):
        await callback_query.message.answer("Недостаточно прав.")
        return

    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    error, menu = await _validate_draw_prerequisites(
        tournament, data["user_id"], callback_query.from_user.id
    )
    if error:
        await callback_query.message.answer(error, reply_markup=menu)
        return

    max_groups = _active_players_count(tournament)
    await callback_query.message.answer(
        f"Выберите число групп (от 2 до {max_groups}):",
        reply_markup=draw_groups_count_keyboard(max_groups),
    )


@router.callback_query(
    DrawGroupsCallbackFactory.filter(),
    StateFilter(TournamentMenu.tournament_menu),
)
async def admin_draw_groups_pick_count(
    callback_query: CallbackQuery, state: FSMContext, callback_data: DrawGroupsCallbackFactory
):
    await callback_query.answer()
    if not is_bot_admin(callback_query.from_user.id):
        await callback_query.message.answer("Недостаточно прав.")
        return

    data = await state.get_data()
    await _execute_draw_groups(
        callback_query.message,
        data["tournament_id"],
        data["user_id"],
        callback_query.from_user.id,
        callback_data.groups,
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "admin_draw_groups_custom"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def admin_draw_groups_custom(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_bot_admin(callback_query.from_user.id):
        await callback_query.message.answer("Недостаточно прав.")
        return

    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    max_groups = _active_players_count(tournament)
    await state.set_state(TournamentMenu.admin_draw_groups_count)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=MenuCallbackFactory(
                        action="admin_draw_groups_cancel"
                    ).pack(),
                )
            ]
        ]
    )
    await callback_query.message.answer(
        f"Введите число групп (от 2 до {max_groups}):",
        reply_markup=cancel_kb,
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "admin_draw_groups_cancel"),
    StateFilter(TournamentMenu.tournament_menu, TournamentMenu.admin_draw_groups_count),
)
async def admin_draw_groups_cancel(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    await state.set_state(TournamentMenu.tournament_menu)
    menu = await keyboard_menu(
        tournament_id=data["tournament_id"],
        user_id=data["user_id"],
        telegram_id=callback_query.from_user.id,
    )
    await callback_query.message.answer("Жеребьёвка отменена.", reply_markup=menu)


@router.message(StateFilter(TournamentMenu.admin_draw_groups_count))
async def admin_draw_groups_enter_count(message: Message, state: FSMContext):
    if not is_bot_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    data = await state.get_data()
    await state.set_state(TournamentMenu.tournament_menu)
    try:
        number_of_groups = int(message.text.strip())
    except (TypeError, ValueError):
        menu = await keyboard_menu(
            tournament_id=data["tournament_id"],
            user_id=data["user_id"],
            telegram_id=message.from_user.id,
        )
        await message.answer("Введите целое число.", reply_markup=menu)
        return

    await _execute_draw_groups(
        message,
        data["tournament_id"],
        data["user_id"],
        message.from_user.id,
        number_of_groups,
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "admin_update_sheet"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def admin_update_sheet(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    if not is_bot_admin(callback_query.from_user.id):
        await callback_query.message.answer("Недостаточно прав.")
        return

    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    tour = await get_tour(tournament)
    menu = await keyboard_menu(
        tournament_id=tournament.id,
        user_id=data["user_id"],
        telegram_id=callback_query.from_user.id,
    )

    if not tour:
        await callback_query.message.answer("Матчи тура ещё не установлены", reply_markup=menu)
        return

    await callback_query.message.answer("Обновляю Google Таблицу...")
    try:
        sheet_url = await sync_google_spreadsheet(tournament)
    except (FileNotFoundError, ValueError, Exception) as error:
        await _answer_sheet_sync_error(
            callback_query, tournament, data["user_id"], error
        )
        return

    tournament = await get_tournament(tournament.id)
    if tour_has_started(tournament):
        details = "Таблица обновлена: матчи и прогнозы игроков."
    else:
        details = (
            "Таблица обновлена: матчи 1-го тура (2 части для разных групп). "
            "Прогнозы появятся после начала тура."
        )

    await callback_query.message.answer(
        f"{details}\n{sheet_url}",
        reply_markup=menu,
        disable_web_page_preview=False,
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "show_predictions"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def get_predictions(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    tour: Tour = await get_tour(tournament)
    if tour:
        if tour.next_deadline - datetime.now() < timedelta(hours=1):
            groups = await get_group_history(tournament)
            if groups:
                await recalculate_tournament_points(tournament)
                tournament = await get_tournament(data["tournament_id"])
                predictions = await show_distribution(
                    groups.group_distribution,
                    tournament.players,
                    with_match_prediction=True,
                )
                await send_long_message(callback_query.message.chat.id, predictions, callback_query.bot)
                await callback_query.message.answer(
                    "Вы в главном меню",
                    reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"])
                )
            else:
                await callback_query.message.answer(
                    "Вначале проведите жеребьевку",
                    reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"])
                )
        else:
            await callback_query.message.answer(
                "Прогнозы игроков будут доступны за час до тура",
                reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"])
            )
    else:
        await callback_query.message.answer("Матчи тура ещё не установлены")


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "open_prediction_form"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def open_prediction_form(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    player: Player = await get_or_create_player(
        {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
    )
    telegram_id = callback_query.from_user.id
    form_url, form_error = await generate_link(
        tournament=tournament, player=player, telegram_id=telegram_id
    )
    if form_error:
        await callback_query.message.answer(
            form_error,
            reply_markup=await keyboard_menu(
                tournament_id=tournament.id,
                user_id=data["user_id"],
                telegram_id=telegram_id,
            ),
        )
        return

    logger.info(
        "WebApp URL для user_id=%s telegram_id=%s: %s",
        data["user_id"],
        telegram_id,
        form_url,
    )
    await callback_query.message.answer(
        f"Выберите способ открытия формы:\n\n"
        f"• Web App — внутри Telegram (может не работать с ngrok free)\n"
        f"• В браузере — надёжный вариант, откроется полная ссылка\n\n"
        f"{form_url}",
        reply_markup=await prediction_form_keyboard(tournament, player, form_url),
        disable_web_page_preview=True,
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "make_prediction_late"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def give_prediction_late(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer(
        "Тур уже начался или начинается раньше чем через час. Если вы не успели 😔, бот проставил вам 0-0 все матчи"
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "no_group"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def no_group_prediction(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer(
        "Сначала проведите жеребьевку — от группы зависит, какие 12 матчей тура вы прогнозируете."
    )


@router.message(
    lambda message: message.web_app_data, StateFilter(TournamentMenu.tournament_menu)
)
async def receive_prediction(web_app_message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        message_predictions = await save_player_predictions(
            data["tournament_id"],
            data["user_id"],
            json.loads(web_app_message.web_app_data.data),
        )
    except ValueError as error:
        await web_app_message.answer(str(error))
        return

    await web_app_message.answer(
        message_predictions,
        reply_markup=await keyboard_menu(tournament_id=data["tournament_id"], user_id=data["user_id"])
    )


@router.callback_query(
    MenuCallbackFactory.filter(F.action == "prediction_text"),
    StateFilter(TournamentMenu.tournament_menu),
)
async def give_prediction_text(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    tournament = await get_tournament(data["tournament_id"])
    player: Player = await get_or_create_player(
        {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
    )
    if tournament.current_tour_id:
        date_validation = await validate_tour_date(tournament)
        if date_validation:
            if splits_matches_by_groups(tournament) and not player.group:
                await callback_query.message.answer(
                    "Сначала проведите жеребьевку — от группы зависит, какие 12 матчей тура вы прогнозируете."
                )
                return
            total_groups = await get_total_groups(tournament)
            matches = get_matches_for_player(player, tournament, total_groups)
            tour_matches = get_tour_matches_sorted(tournament)
            boundary = get_half_boundary(len(tour_matches))
            half_label = get_half_label(player, total_groups, boundary, tournament)
            message_result = f"Ваши матчи ({half_label} из {len(tour_matches)}):"
            await callback_query.message.answer(message_result)
            for match in matches:
                message_result = f"{match.id}.{match.first_team}-{match.second_team}"
                await callback_query.message.answer(message_result)
            await state.set_state(TournamentMenu.match_predictions)
            await callback_query.message.answer(
                "Пишите каждый матч отдельным сообщением. \nНапример, 1.Германия-Шотландия 1-0\nОбязательно с номером и точкой."
            )
            await callback_query.message.answer("Каждый матч отправляем отдельно.")
        else:
            await callback_query.message.answer(
                "Тур уже начался или начинается раньше чем через час. вы не успели 😔, бот проставил вам 0-0 все матчи"
            )
    else:
        await callback_query.message.answer("Матчи тура ещё не установлены")


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
        first_team_score, second_team_score = map(int, score_str.split("-"))
        await validate_prediction(match_id, first_team, second_team)
        data = await state.get_data()
        player: Player = await get_or_create_player(
            {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
        )
        tournament = await get_tournament(data["tournament_id"])
        await validate_player_match_access(player, match_id, tournament)
        await update_match_prediction_for_player(
            match_id=match_id,
            player_id=player.id,
            first_team_score=first_team_score,
            second_team_score=second_team_score,
        )
        await message.answer("Ваш прогноз сохранен.")
        await message.answer(
            "Нажмите далее, если закончили давать прогнозы",
            reply_markup=inline_keyboard_next,
        )
    except ValueError:
        await message.answer(
            f"Скорее всего вы ошиблись при написании, пропробуйте еще. У вас получится. \nСо следующего тура будет удобнее!"
        )
    except PredictionValidationError as e:
        await message.answer(e.message)


@router.callback_query(
    lambda callback: callback.data == "next",
    StateFilter(TournamentMenu.match_predictions),
)
async def process_callback_next_button(
    callback_query: CallbackQuery, state: FSMContext
):
    await callback_query.answer()
    await state.set_state(TournamentMenu.tournament_menu)
    data = await state.get_data()
    await callback_query.message.delete()
    player: Player = await get_or_create_player(
        {"tournament_id": data["tournament_id"], "user_id": data["user_id"]}
    )
    tournament = await get_tournament(data["tournament_id"])
    current_tour_id = tournament.current_tour_id
    total_groups = await get_total_groups(tournament)
    allowed_match_ids = {
        match.id
        for match in get_matches_for_player(player, tournament, total_groups)
    }
    message_predictions = "Ваши прогнозы:\n"
    for prediction in player.match_predictions:
        if (
            prediction.match.tour.id == current_tour_id
            and prediction.match_id in allowed_match_ids
        ):
            message_predictions += (
                f"{prediction.match.first_team}-{prediction.match.second_team}"
                f" {prediction.first_team_score}-{prediction.second_team_score}\n"
            )

    await callback_query.message.answer(
        "Прогнозы на матчи тура успешно заполнены",
        reply_markup=await keyboard_menu(tournament_id=tournament.id, user_id=data["user_id"])
    )
    await callback_query.message.answer(message_predictions)
    await callback_query.message.answer(
        f"Если хотите поменять прогнозы, просто начните заново и поменяйте нужный матч"
    )
