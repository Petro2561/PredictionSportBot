from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import is_bot_admin, load_config
from bot.utils.prediction_submit import build_prediction_form_matches
from bot.webapp_sessions import create_prediction_session
from bot.keyboards.callback_factory import (
    DrawGroupsCallbackFactory,
    MenuCallbackFactory,
    TournamentCallbackFactory,
)
from bot.utils.match_groups import (
    get_matches_for_player,
    get_total_groups,
    splits_matches_by_groups,
)
from bot.utils.utils_match import validate_tour_date
from bot.utils.utils_tournament import get_all_tournaments, get_tournament
from bot.utils.random_distribution import add_player_to_group
from bot.utils.utils_user_player import get_or_create_player
from db.models import Player, User

def create_tournament_keyboard(user: User):
    tournaments = get_all_tournaments(user)
    if tournaments:
        keyboard = []
        for tournament in tournaments:
            button = InlineKeyboardButton(
                text=tournament.name,
                callback_data=TournamentCallbackFactory(id=tournament.id).pack(),
            )
            keyboard.append([button])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return None


async def generate_link(
    tournament, player: Player, telegram_id: int | None = None
) -> tuple[str, str | None]:
    config = load_config()
    tournament = await get_tournament(tournament.id)
    player = await get_or_create_player(
        {"user_id": player.user_id, "tournament_id": tournament.id}
    )
    base_url = config.webapp.url.rstrip("/")
    if not player:
        return f"{base_url}/prediction.html", "Не удалось загрузить профиль игрока."

    if splits_matches_by_groups(tournament):
        if not player.group:
            await add_player_to_group(player, tournament)
            player = await get_or_create_player(
                {"user_id": player.user_id, "tournament_id": tournament.id}
            )

    total_groups = await get_total_groups(tournament)
    matches = get_matches_for_player(player, tournament, total_groups)
    if not matches:
        if splits_matches_by_groups(tournament):
            return f"{base_url}/prediction.html", (
                "Сначала проведите жеребьевку — от группы зависит, какие 12 матчей тура вы прогнозируете."
            )
        return f"{base_url}/prediction.html", "Матчи текущего тура ещё не добавлены."

    if telegram_id is None and player.user:
        telegram_id = player.user.telegram_id
    session_id = create_prediction_session(
        await build_prediction_form_matches(player, tournament),
        telegram_id=telegram_id,
        tournament_id=tournament.id,
        user_id=player.user_id,
    )
    return f"{base_url}/p/{session_id}", None


async def prediction_form_keyboard(
    tournament, player: Player, form_url: str | None = None
):
    if form_url is None:
        form_url, _ = await generate_link(tournament=tournament, player=player)
    kb_builder = InlineKeyboardBuilder()
    kb_builder.row(
        InlineKeyboardButton(
            text="Заполнить прогноз на сайте",
            url=form_url,
        )
    )
    return kb_builder.as_markup()


def draw_groups_count_keyboard(max_groups: int) -> InlineKeyboardMarkup:
    kb_builder = InlineKeyboardBuilder()
    for count in (2, 3, 4, 6):
        if count <= max_groups:
            kb_builder.button(
                text=str(count),
                callback_data=DrawGroupsCallbackFactory(groups=count).pack(),
            )
    kb_builder.adjust(4)
    kb_builder.row(
        InlineKeyboardButton(
            text="Другое число",
            callback_data=MenuCallbackFactory(action="admin_draw_groups_custom").pack(),
        )
    )
    kb_builder.row(
        InlineKeyboardButton(
            text="Отмена",
            callback_data=MenuCallbackFactory(action="admin_draw_groups_cancel").pack(),
        )
    )
    return kb_builder.as_markup()


async def keyboard_menu(user_id, tournament_id, telegram_id: int | None = None):
    kb_builder = InlineKeyboardBuilder()
    button_players = InlineKeyboardButton(
        text="Посмотреть список участников",
        callback_data=MenuCallbackFactory(action="show_players").pack(),
    )
    button_table = InlineKeyboardButton(
        text="Посмотреть таблицу",
        callback_data=MenuCallbackFactory(action="show_table").pack(),
    )
    tournament = await get_tournament(tournament_id)
    player = next(
        (p for p in tournament.players if p.user_id == user_id),
        None,
    )
    if not player:
        player = await get_or_create_player(
            {"user_id": user_id, "tournament_id": tournament_id}
        )
    if tournament.current_tour_id:
        date_validation = await validate_tour_date(tournament)
        if not date_validation:
            button_make_prediction = InlineKeyboardButton(
                text="Сделать прогноз",
                callback_data=MenuCallbackFactory(action="make_prediction_late").pack(),
            )
        elif splits_matches_by_groups(tournament) and not player.group:
            button_make_prediction = InlineKeyboardButton(
                text="Сделать прогноз",
                callback_data=MenuCallbackFactory(action="no_group").pack(),
            )
        else:
            button_make_prediction = InlineKeyboardButton(
                text="Сделать прогноз",
                callback_data=MenuCallbackFactory(action="open_prediction_form").pack(),
            )
        button_show_predictions = InlineKeyboardButton(
            text="Посмотреть прогнозы игроков",
            callback_data=MenuCallbackFactory(action="show_predictions").pack(),
        )
        kb_builder.row(button_show_predictions)
        kb_builder.row(button_make_prediction)
    kb_builder.row(button_players)
    kb_builder.row(button_table)
    if telegram_id and is_bot_admin(telegram_id):
        kb_builder.row(
            InlineKeyboardButton(
                text="Провести жеребьёвку",
                callback_data=MenuCallbackFactory(action="admin_draw_groups").pack(),
            )
        )
        kb_builder.row(
            InlineKeyboardButton(
                text="Обновить Google таблицу",
                callback_data=MenuCallbackFactory(action="admin_update_sheet").pack(),
            )
        )
    return kb_builder.as_markup()
