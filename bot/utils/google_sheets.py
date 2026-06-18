import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.auth.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

from bot.config import load_config
from bot.utils.google_oauth import get_oauth_credentials, oauth_is_configured
from bot.utils.common import get_tour
from bot.utils.match_groups import (
    MATCHES_PER_HALF,
    player_predicts_first_half,
)
from bot.utils.utils_match import tour_has_started, tour_starts_at
from bot.utils.utils_tournament import get_tournament
from db.crud.group_history import crud_group_history
from db.crud.tournament import crud_tournament
from db.db import get_async_session
from db.models import (
    Match,
    MatchPrediction,
    Player,
    Tour,
    Tournament,
    TournamentPrediction,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

FIRST_GROUP_COL = 2
GROUP_BLOCK_WIDTH = 7
SCHEDULE_HEADER_ROW = 2
SCHEDULE_FIRST_MATCH_ROW = 3
SECTION_HEADER_ROW = 21
GROUP_HEADER_ROW = 22
STANDINGS_START_ROW = 23
STANDINGS_TO_PREDICTIONS_GAP = 2
PLAYER_BLOCK_GAP = 2

GROUP_HEADER_SUFFIXES = ("А", "B", "C", "D", "E", "F", "G", "H")
HALF_LABELS = (
    f"часть 1 (матчи 1–{MATCHES_PER_HALF})",
    f"часть 2 (матчи {MATCHES_PER_HALF + 1}–{MATCHES_PER_HALF * 2})",
)
SECTION_TOUR_LABEL = "1 ТУР"

COL_A_WIDTH = 13.63
BLOCK_COL_WIDTHS = (26.38, 3.63, 13.0, 13.0, 4.5, 3.63, 14.38)

YELLOW = {"red": 1.0, "green": 0.851, "blue": 0.4}
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}

# Google Таблицы с русской локалью: разделитель аргументов «;», не «,»
FORMULA_SEP = ";"


TOUR_BLOCK_GAP = 4

SUMMARY_LABEL_ROW = 1
SUMMARY_HEADER_ROW = 2
SUMMARY_FIRST_PLAYER_ROW = 3
SUMMARY_LABEL = "ОБЩИЙ ЗАЧЁТ"


@dataclass
class Stage1Layout:
    width: int
    max_standings_rows: int
    matches_per_player: int
    num_groups: int
    predictions_start_row: int
    player_block_gap: int = PLAYER_BLOCK_GAP
    base_row: int = 0


@dataclass
class SummaryLayout:
    width: int
    num_groups: int
    max_players: int
    num_tours: int


def _summary_height(max_players: int) -> int:
    """Высота сводной таблицы сверху (строк), включая разрыв до 1-го тура."""
    if max_players <= 0:
        return 0
    last_player_row = SUMMARY_FIRST_PLAYER_ROW + max_players - 1
    return last_player_row + TOUR_BLOCK_GAP


def _player_block_height(matches_per_player: int, gap: int = PLAYER_BLOCK_GAP) -> int:
    return matches_per_player + gap


def _tour_block_height(max_players: int, matches_per_player: int) -> int:
    """Высота одного блока тура (строк), включая разрыв до следующего тура."""
    predictions_start = STANDINGS_START_ROW + max_players + STANDINGS_TO_PREDICTIONS_GAP
    predictions_rows = max_players * _player_block_height(matches_per_player)
    return predictions_start + predictions_rows + TOUR_BLOCK_GAP


async def should_include_predictions(tournament: Tournament) -> bool:
    config = load_config()
    if config.google.skip_deadline_check:
        return True
    tournament = await get_tournament(tournament.id)
    return tour_has_started(tournament)


def _group_start_col(group_index: int) -> int:
    return FIRST_GROUP_COL + group_index * GROUP_BLOCK_WIDTH


def _last_col(num_groups: int) -> int:
    return FIRST_GROUP_COL + GROUP_BLOCK_WIDTH * num_groups - 2


def _player_name_col(group_index: int) -> int:
    return 1 if group_index == 0 else _group_start_col(group_index) - 1


def _pad_row(row: list, width: int) -> list:
    if len(row) < width:
        return row + [""] * (width - len(row))
    return row[:width]


def _set_cell(row: list, col: int, value) -> None:
    if col < 1:
        return
    while len(row) < col:
        row.append("")
    row[col - 1] = value


def _match_label(match: Match) -> str:
    return f"{match.first_team} – {match.second_team}"


def _group_header_label(group_index: int) -> str:
    suffix = GROUP_HEADER_SUFFIXES[group_index]
    return f"Группа {suffix}"


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _excel_width_to_pixels(width: float) -> int:
    return max(21, int(width * 7 + 10))


def _schedule_half_col(half_index: int) -> int:
    """Левая колонка — 1-я половина групп (A/B), правая — 2-я (C/D)."""
    return _group_start_col(half_index)


def _schedule_score_cols(half_index: int) -> tuple[int, int]:
    start = _schedule_half_col(half_index)
    return start + 1, start + 2


def _schedule_coords_for_match(
    absolute_index: int, base: int = 0
) -> tuple[int, int, tuple[int, int]]:
    half_index = 0 if absolute_index < MATCHES_PER_HALF else 1
    slot = absolute_index % MATCHES_PER_HALF
    schedule_row = base + SCHEDULE_FIRST_MATCH_ROW + slot
    return schedule_row, half_index, _schedule_score_cols(half_index)


def _prediction_row_for(player_index: int, match_index: int, layout: Stage1Layout) -> int:
    block_height = _player_block_height(layout.matches_per_player, layout.player_block_gap)
    return layout.predictions_start_row + player_index * block_height + match_index


def _points_formula(
    pred_row: int,
    schedule_row: int,
    pred_score_cols: tuple[int, int],
    schedule_score_cols: tuple[int, int],
    diff_col: int,
    *,
    exact_points: int = 3,
    diff_points: int = 2,
    outcome_points: int = 1,
) -> str:
    pc1, pc2 = (_column_letter(c) for c in pred_score_cols)
    sc1, sc2 = (_column_letter(c) for c in schedule_score_cols)
    pe = _column_letter(diff_col)
    s = FORMULA_SEP
    return (
        f"=IF(ISBLANK(${sc1}${schedule_row}){s}\"\"{s}"
        f"IF(AND({pc1}{pred_row}=${sc1}${schedule_row}{s}{pc2}{pred_row}=${sc2}${schedule_row}){s}{exact_points}{s}"
        f"IF({pc1}{pred_row}-{pc2}{pred_row}=${sc1}${schedule_row}-${sc2}${schedule_row}{s}{diff_points}{s}"
        f"IF({pe}{pred_row}>0{s}{outcome_points}{s}0))))"
    )


def _diff_formula(
    pred_row: int,
    schedule_row: int,
    pred_score_cols: tuple[int, int],
    schedule_score_cols: tuple[int, int],
    diff_col: int,
) -> str:
    pc1, pc2 = (_column_letter(c) for c in pred_score_cols)
    sc1, sc2 = (_column_letter(c) for c in schedule_score_cols)
    pe = _column_letter(diff_col)
    return (
        f"=({pc1}{pred_row}-{pc2}{pred_row})*"
        f"({sc1}{schedule_row}-{sc2}{schedule_row})"
    )


def _player_tour_matches(
    player: Player,
    tour_matches: list[Match],
    total_groups: int,
    split: bool,
) -> list[Match]:
    """Матчи конкретного тура, которые прогнозирует игрок (с учётом группы)."""
    if not split:
        return tour_matches
    if not player.group:
        return []
    if player_predicts_first_half(player, total_groups):
        return tour_matches[:MATCHES_PER_HALF]
    return tour_matches[MATCHES_PER_HALF : MATCHES_PER_HALF * 2]


def _build_summary_section(
    group_players: list[list[Player]],
    width: int,
    max_players: int,
    tour_bases: list[int],
) -> dict[int, list]:
    """Сводная таблица сверху: по каждой группе очки за каждый тур и «Итого»."""
    rows: dict[int, list] = {}
    num_tours = len(tour_bases)

    label_row = _pad_row([], width)
    _set_cell(label_row, 1, SUMMARY_LABEL)
    rows[SUMMARY_LABEL_ROW] = label_row

    header = _pad_row([], width)
    for group_index in range(len(group_players)):
        start = _group_start_col(group_index)
        _set_cell(header, start, _group_header_label(group_index))
        for tour_index in range(num_tours):
            _set_cell(header, start + 1 + tour_index, f"{tour_index + 1} тур")
        _set_cell(header, start + 1 + num_tours, "Итого")
    rows[SUMMARY_HEADER_ROW] = header

    for player_index in range(max_players):
        row_num = SUMMARY_FIRST_PLAYER_ROW + player_index
        row = _pad_row([], width)
        for group_index, players in enumerate(group_players):
            if player_index >= len(players):
                continue
            player = players[player_index]
            start = _group_start_col(group_index)
            # в блоке тура итог игрока лежит в колонке start+1
            tour_sum_col = _column_letter(start + 1)
            _set_cell(row, start, player.user.name or "")
            for tour_index, base in enumerate(tour_bases):
                ref_row = base + STANDINGS_START_ROW + player_index
                _set_cell(
                    row, start + 1 + tour_index, f"={tour_sum_col}{ref_row}"
                )
            if num_tours:
                first_col = _column_letter(start + 1)
                last_col = _column_letter(start + num_tours)
                _set_cell(
                    row,
                    start + 1 + num_tours,
                    f"=SUM({first_col}{row_num}:{last_col}{row_num})",
                )
        rows[row_num] = row

    return rows


def _build_schedule_section(
    matches: list[Match], width: int, base: int = 0
) -> dict[int, list]:
    rows: dict[int, list] = {base + 1: _pad_row([], width)}

    header = _pad_row([], width)
    if matches[:MATCHES_PER_HALF]:
        _set_cell(header, _schedule_half_col(0), HALF_LABELS[0])
    if len(matches) > MATCHES_PER_HALF:
        _set_cell(header, _schedule_half_col(1), HALF_LABELS[1])
    rows[base + SCHEDULE_HEADER_ROW] = header

    for slot in range(MATCHES_PER_HALF):
        row_num = base + SCHEDULE_FIRST_MATCH_ROW + slot
        row = _pad_row([], width)
        for half_index in range(2):
            match_index = half_index * MATCHES_PER_HALF + slot
            if match_index >= len(matches):
                continue
            match = matches[match_index]
            half_col = _schedule_half_col(half_index)
            score1_col, score2_col = _schedule_score_cols(half_index)
            _set_cell(row, half_col, _match_label(match))
            if match.first_team_score is not None:
                _set_cell(row, score1_col, match.first_team_score)
                _set_cell(row, score2_col, match.second_team_score)
        rows[row_num] = row

    return rows


def _build_standings_and_predictions(
    group_players: list[list[Player]],
    tournament: Tournament,
    total_groups: int,
    predictions_by_player: dict[int, dict[int, dict]],
    extras_by_player: dict[int, tuple[str, str]],
    width: int,
    include_predictions: bool,
    matches: list[Match],
    *,
    base: int = 0,
    tour_number: int = 1,
    split_matches: bool = True,
    matches_per_player: int = MATCHES_PER_HALF,
    max_players: int = 0,
) -> tuple[dict[int, list], Stage1Layout]:
    rows: dict[int, list] = {}
    num_groups = len(group_players) or 1

    layout = Stage1Layout(
        width=width,
        max_standings_rows=max_players,
        matches_per_player=matches_per_player,
        num_groups=num_groups,
        predictions_start_row=base
        + STANDINGS_START_ROW
        + max_players
        + STANDINGS_TO_PREDICTIONS_GAP,
        base_row=base,
    )
    exact_points = tournament.exact_score_points if tournament.exact_score_points is not None else 3
    diff_points = tournament.difference_points if tournament.difference_points is not None else 2
    outcome_points = tournament.results_points if tournament.results_points is not None else 1

    section_row = _pad_row([], width)
    _set_cell(section_row, 1, f"{tour_number} ТУР")
    rows[base + SECTION_HEADER_ROW] = section_row

    group_header = _pad_row([], width)
    for group_index in range(num_groups):
        start = _group_start_col(group_index)
        _set_cell(group_header, start, _group_header_label(group_index))
        if tournament.best_striker:
            _set_cell(group_header, start + 2, "Бомбардир")
        if tournament.best_assistant:
            _set_cell(group_header, start + 3, "Ассистент")
    rows[base + GROUP_HEADER_ROW] = group_header

    player_matches_cache: dict[int, list[Match]] = {}

    def matches_for(player: Player) -> list[Match]:
        if player.id not in player_matches_cache:
            player_matches_cache[player.id] = _player_tour_matches(
                player, matches, total_groups, split_matches
            )
        return player_matches_cache[player.id]

    for player_index in range(max_players):
        standings_row_num = base + STANDINGS_START_ROW + player_index
        standings_row = _pad_row([], width)
        pred_first = _prediction_row_for(player_index, 0, layout)
        pred_last = _prediction_row_for(player_index, matches_per_player - 1, layout)

        for group_index, players in enumerate(group_players):
            if player_index >= len(players):
                continue
            player = players[player_index]
            start = _group_start_col(group_index)
            points_col_letter = _column_letter(start + 4)
            _set_cell(standings_row, start, player.user.name or "")
            _set_cell(
                standings_row,
                start + 1,
                f"=SUM({points_col_letter}{pred_first}:{points_col_letter}{pred_last})",
            )
            if include_predictions:
                striker, assistant = extras_by_player.get(player.id, ("", ""))
                if tournament.best_striker:
                    _set_cell(standings_row, start + 2, striker)
                if tournament.best_assistant:
                    _set_cell(standings_row, start + 3, assistant)
        rows[standings_row_num] = standings_row

    if not group_players:
        return rows, layout

    for player_index in range(max_players):
        for match_index in range(matches_per_player):
            pred_row_num = _prediction_row_for(player_index, match_index, layout)
            row = _pad_row([], width)
            wrote_any = False

            for group_index, players in enumerate(group_players):
                if player_index >= len(players):
                    continue
                player = players[player_index]
                player_matches = matches_for(player)
                if match_index >= len(player_matches):
                    continue

                match = player_matches[match_index]
                start = _group_start_col(group_index)
                pred_score_cols = (start + 1, start + 2)
                diff_col = start + 3
                points_col = start + 4

                if match_index == 0:
                    _set_cell(row, _player_name_col(group_index), player.user.name or "")

                _set_cell(row, start, _match_label(match))

                try:
                    absolute_index = matches.index(match)
                except ValueError:
                    absolute_index = match_index
                schedule_row, schedule_half, schedule_score_cols = (
                    _schedule_coords_for_match(absolute_index, base)
                )

                if include_predictions:
                    prediction = predictions_by_player.get(player.id, {}).get(match.id)
                    if prediction:
                        _set_cell(row, pred_score_cols[0], prediction["s1"])
                        _set_cell(row, pred_score_cols[1], prediction["s2"])

                _set_cell(
                    row,
                    diff_col,
                    _diff_formula(
                        pred_row_num,
                        schedule_row,
                        pred_score_cols,
                        schedule_score_cols,
                        diff_col,
                    ),
                )
                _set_cell(
                    row,
                    points_col,
                    _points_formula(
                        pred_row_num,
                        schedule_row,
                        pred_score_cols,
                        schedule_score_cols,
                        diff_col,
                        exact_points=exact_points,
                        diff_points=diff_points,
                        outcome_points=outcome_points,
                    ),
                )
                wrote_any = True

            if wrote_any:
                rows[pred_row_num] = row

        block_start = _prediction_row_for(player_index, 0, layout)
        for gap_index in range(layout.player_block_gap):
            rows[block_start + matches_per_player + gap_index] = _pad_row([], width)

    return rows, layout


def _rows_dict_to_list(rows: dict[int, list], width: int) -> list[list]:
    if not rows:
        return []
    max_row = max(rows)
    return [rows.get(index, _pad_row([], width)) for index in range(1, max_row + 1)]


async def _load_tournament_tours(session, tournament_id: int) -> list[Tour]:
    result = await session.execute(
        select(Tour)
        .where(Tour.tournament_id == tournament_id)
        .order_by(Tour.number)
    )
    return list(result.scalars())


async def build_stage1_sheet_rows(
    tournament: Tournament, *, include_predictions: bool
) -> tuple[list[list], list[Stage1Layout], SummaryLayout | None]:
    async for session in get_async_session():
        tournament = await crud_tournament.get_tournament(tournament.id, session)
        current_tour = tournament.current_tour
        if not current_tour:
            return [["Матчи тура ещё не установлены"]], [], None

        tours = await _load_tournament_tours(session, tournament.id)

        matches_by_tour: dict[int, list[Match]] = {}
        for match in tournament.matches:
            matches_by_tour.setdefault(match.tour_id, []).append(match)
        for tour_matches in matches_by_tour.values():
            tour_matches.sort(key=lambda m: m.id)

        # только туры, в которых есть матчи; по возрастанию номера
        tours = [t for t in tours if matches_by_tour.get(t.id)]
        if not tours:
            return [["Матчи тура ещё не установлены"]], [], None

        group_history = await crud_group_history.get_last_group_history(
            tournament.id, session
        )
        extras_by_player = await _load_tournament_extras_by_player(
            session, tournament.id
        )

        player_map = {
            player.id: player
            for player in tournament.players
            if not player.is_eliminated
        }

        if group_history:
            group_players = _sorted_group_players(
                group_history.group_distribution, player_map
            )
            total_groups = len(group_history.group_distribution)
        else:
            players = sorted(
                player_map.values(),
                key=lambda player: (-player.points, player.user.name or ""),
            )
            group_players = [players] if players else []
            total_groups = 1

        num_groups = max(len(group_players), 2)
        width = _last_col(num_groups)
        max_players = max((len(players) for players in group_players), default=0)
        matches_per_player = MATCHES_PER_HALF
        block_height = _tour_block_height(max_players, matches_per_player)

        summary_height = _summary_height(max_players)
        tour_bases = [
            summary_height + index * block_height for index in range(len(tours))
        ]

        current_number = current_tour.number or 1
        rows_map: dict[int, list] = {}
        layouts: list[Stage1Layout] = []

        summary: SummaryLayout | None = None
        if summary_height and group_players:
            rows_map.update(
                _build_summary_section(
                    group_players, width, max_players, tour_bases
                )
            )
            summary = SummaryLayout(
                width=width,
                num_groups=num_groups,
                max_players=max_players,
                num_tours=len(tours),
            )

        for index, tour in enumerate(tours):
            base = tour_bases[index]
            tour_matches = matches_by_tour.get(tour.id, [])
            predictions_by_player = await _load_match_predictions_by_player(
                session, tournament.id, tour.id
            )
            # прошедшие туры показываем всегда, текущий — по флагу
            if tour.id == current_tour.id:
                include_for_tour = include_predictions
            else:
                include_for_tour = (tour.number or 0) <= current_number

            rows_map.update(_build_schedule_section(tour_matches, width, base))
            for row_num in range(
                base + SCHEDULE_FIRST_MATCH_ROW + MATCHES_PER_HALF,
                base + SECTION_HEADER_ROW,
            ):
                rows_map.setdefault(row_num, _pad_row([], width))

            standings_rows, layout = _build_standings_and_predictions(
                group_players,
                tournament,
                total_groups,
                predictions_by_player,
                extras_by_player,
                width,
                include_for_tour,
                tour_matches,
                base=base,
                tour_number=tour.number or (index + 1),
                split_matches=bool(
                    getattr(tour, "split_matches_by_groups", True)
                ),
                matches_per_player=matches_per_player,
                max_players=max_players,
            )
            rows_map.update(standings_rows)
            layouts.append(layout)

        return _rows_dict_to_list(rows_map, width), layouts, summary


async def _load_tournament_extras_by_player(
    session, tournament_id: int
) -> dict[int, tuple[str, str]]:
    result = await session.execute(
        select(TournamentPrediction).where(
            TournamentPrediction.tournament_id == tournament_id
        )
    )
    return {
        prediction.player_id: (
            prediction.best_striker or "",
            prediction.best_assistant or "",
        )
        for prediction in result.scalars()
    }


async def _load_match_predictions_by_player(
    session, tournament_id: int, tour_id: int
) -> dict[int, dict[int, dict]]:
    result = await session.execute(
        select(MatchPrediction)
        .join(Match, MatchPrediction.match_id == Match.id)
        .where(Match.tournament_id == tournament_id, Match.tour_id == tour_id)
    )
    by_player: dict[int, dict[int, dict]] = {}
    for prediction in result.scalars():
        by_player.setdefault(prediction.player_id, {})[prediction.match_id] = {
            "s1": prediction.first_team_score,
            "s2": prediction.second_team_score,
            "points": prediction.points,
        }
    return by_player


def _sorted_group_players(
    group_distribution: dict[str, list[int]], player_map: dict[int, Player]
) -> list[list[Player]]:
    group_players: list[list[Player]] = []
    for group_name in sorted(group_distribution, key=lambda name: name):
        players = [
            player_map[player_id]
            for player_id in group_distribution[group_name]
            if player_id in player_map
        ]
        players.sort(key=lambda player: (-player.points, player.user.name or ""))
        group_players.append(players)
    return group_players


def _get_service_account_credentials(config) -> ServiceAccountCredentials:
    path = Path(config.google.service_account_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        raise FileNotFoundError(f"Файл сервисного аккаунта не найден: {path}")
    return ServiceAccountCredentials.from_service_account_file(
        str(path), scopes=SCOPES
    )


def _uses_service_account() -> bool:
    config = load_config()
    if not config.google.service_account_file:
        return False
    path = Path(config.google.service_account_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    return path.exists()


def _uses_oauth() -> bool:
    return oauth_is_configured()


def _get_credentials() -> Credentials:
    config = load_config()
    if _uses_service_account():
        return _get_service_account_credentials(config)
    if oauth_is_configured():
        return get_oauth_credentials(SCOPES)
    raise ValueError(
        "Google не настроен.\n"
        "Укажите GOOGLE_SERVICE_ACCOUNT_FILE (JSON сервисного аккаунта) "
        "или выполните python scripts/google_oauth_setup.py"
    )


def _parse_spreadsheet_id(value: str) -> str:
    value = value.strip()
    if "/d/" in value:
        return value.split("/d/")[1].split("/")[0]
    return value


def _spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def get_configured_spreadsheet_url() -> str | None:
    config = load_config()
    if not config.google.spreadsheet_id:
        return None
    return _spreadsheet_url(_parse_spreadsheet_id(config.google.spreadsheet_id))


def _get_sheet_id(sheets_service, spreadsheet_id: str, sheet_title: str) -> int:
    spreadsheet = (
        sheets_service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )
    for sheet in spreadsheet.get("sheets", []):
        props = sheet["properties"]
        if props["title"] == sheet_title:
            return props["sheetId"]
    raise ValueError(f"Лист «{sheet_title}» не найден")


def _resolve_sheet_title(sheets_service, spreadsheet_id: str, preferred_name: str) -> str:
    spreadsheet = (
        sheets_service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )
    sheets = spreadsheet.get("sheets", [])
    if not sheets:
        raise ValueError("В таблице нет листов")

    for sheet in sheets:
        title = sheet["properties"]["title"]
        if title == preferred_name:
            return title

    first_sheet_id = sheets[0]["properties"]["sheetId"]
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": first_sheet_id,
                            "title": preferred_name,
                        },
                        "fields": "title",
                    }
                }
            ]
        },
    ).execute()
    return preferred_name


def _column_width_requests(sheet_id: int, layout: Stage1Layout) -> list[dict]:
    requests: list[dict] = [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": _excel_width_to_pixels(COL_A_WIDTH)},
                "fields": "pixelSize",
            }
        }
    ]
    for group_index in range(layout.num_groups):
        block_start = _group_start_col(group_index) - 1
        for offset, width in enumerate(BLOCK_COL_WIDTHS):
            requests.append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": block_start + offset,
                            "endIndex": block_start + offset + 1,
                        },
                        "properties": {"pixelSize": _excel_width_to_pixels(width)},
                        "fields": "pixelSize",
                    }
                }
            )
    return requests


def _tour_format_requests(sheet_id: int, layout: Stage1Layout) -> list[dict]:
    requests: list[dict] = []
    last_col_index = layout.width
    base = layout.base_row
    section_row = base + SECTION_HEADER_ROW
    group_row = base + GROUP_HEADER_ROW
    schedule_row = base + SCHEDULE_HEADER_ROW

    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": section_row - 1,
                    "endRowIndex": section_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": last_col_index,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": YELLOW,
                        "textFormat": {"bold": True, "fontSize": 12},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }
    )

    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": group_row - 1,
                    "endRowIndex": group_row,
                    "startColumnIndex": _group_start_col(0) - 1,
                    "endColumnIndex": last_col_index,
                },
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 12}}},
                "fields": "userEnteredFormat.textFormat",
            }
        }
    )

    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": schedule_row - 1,
                    "endRowIndex": schedule_row,
                    "startColumnIndex": _group_start_col(0) - 1,
                    "endColumnIndex": last_col_index,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"bold": True},
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
            }
        }
    )

    if layout.max_standings_rows:
        block_height = _player_block_height(
            layout.matches_per_player, layout.player_block_gap
        )
        pred_last_row = layout.predictions_start_row + layout.max_standings_rows * block_height
        for group_index in range(layout.num_groups):
            points_col_index = _group_start_col(group_index) + 3
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": layout.predictions_start_row - 1,
                            "endRowIndex": pred_last_row,
                            "startColumnIndex": points_col_index,
                            "endColumnIndex": points_col_index + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": WHITE,
                                "textFormat": {"fontSize": 11},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            )

    return requests


def _summary_format_requests(sheet_id: int, summary: SummaryLayout) -> list[dict]:
    requests: list[dict] = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": SUMMARY_LABEL_ROW - 1,
                    "endRowIndex": SUMMARY_LABEL_ROW,
                    "startColumnIndex": 0,
                    "endColumnIndex": summary.width,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": YELLOW,
                        "textFormat": {"bold": True, "fontSize": 12},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": SUMMARY_HEADER_ROW - 1,
                    "endRowIndex": SUMMARY_HEADER_ROW,
                    "startColumnIndex": _group_start_col(0) - 1,
                    "endColumnIndex": summary.width,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"bold": True, "fontSize": 12},
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
            }
        },
    ]

    if summary.max_players and summary.num_tours:
        last_player_row = SUMMARY_FIRST_PLAYER_ROW + summary.max_players - 1
        for group_index in range(summary.num_groups):
            total_col_index = _group_start_col(group_index) + summary.num_tours
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": SUMMARY_FIRST_PLAYER_ROW - 1,
                            "endRowIndex": last_player_row,
                            "startColumnIndex": total_col_index,
                            "endColumnIndex": total_col_index + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat.textFormat",
                    }
                }
            )

    return requests


def _formatting_requests(
    sheet_id: int,
    layouts: list[Stage1Layout],
    summary: SummaryLayout | None = None,
) -> list[dict]:
    if not layouts:
        return []
    requests = _column_width_requests(sheet_id, layouts[0])
    if summary:
        requests.extend(_summary_format_requests(sheet_id, summary))
    for layout in layouts:
        requests.extend(_tour_format_requests(sheet_id, layout))
    return requests


def _write_sheet_rows(
    sheets_service,
    spreadsheet_id: str,
    sheet_title: str,
    rows: list[list],
    layouts: list[Stage1Layout] | None,
    summary: SummaryLayout | None = None,
) -> None:
    sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_title)

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A:ZZ",
    ).execute()

    if not rows:
        return

    max_cols = max(len(row) for row in rows)
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    end_col = _column_letter(max_cols)
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1:{end_col}{len(padded_rows)}",
        valueInputOption="USER_ENTERED",
        body={"values": padded_rows},
    ).execute()

    if layouts:
        requests = _formatting_requests(sheet_id, layouts, summary)
        if requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()


def _create_spreadsheet_sync(
    title: str,
    rows: list[list],
    layouts: list[Stage1Layout] | None,
    summary: SummaryLayout | None = None,
) -> str:
    config = load_config()
    credentials = _get_credentials()
    sheets_service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    if _uses_service_account() and not config.google.drive_folder_id:
        sa_email = "email из JSON сервисного аккаунта (поле client_email)"
        sa_path = Path(config.google.service_account_file)
        if not sa_path.is_absolute():
            sa_path = Path(__file__).resolve().parent.parent.parent / sa_path
        if sa_path.exists():
            sa_email = json.loads(sa_path.read_text(encoding="utf-8")).get(
                "client_email", sa_email
            )
        raise ValueError(
            "Для сервисного аккаунта укажите GOOGLE_DRIVE_FOLDER_ID.\n"
            "1) Создайте папку в Google Drive\n"
            f"2) Дайте доступ редактору: {sa_email}\n"
            "3) ID папки — из URL: drive.google.com/.../folders/ВОТ_ЭТОТ_ID"
        )

    file_metadata: dict = {
        "name": title,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    if config.google.drive_folder_id:
        file_metadata["parents"] = [config.google.drive_folder_id]

    created_file = (
        drive_service.files()
        .create(body=file_metadata, fields="id, webViewLink")
        .execute()
    )
    spreadsheet_id = created_file["id"]
    spreadsheet_url = created_file.get("webViewLink")

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": 0, "title": "Стадия 1"},
                        "fields": "title",
                    }
                }
            ]
        },
    ).execute()

    _write_sheet_rows(
        sheets_service, spreadsheet_id, "Стадия 1", rows, layouts, summary
    )

    if config.google.share_email:
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={
                "type": "user",
                "role": "writer",
                "emailAddress": config.google.share_email,
            },
            sendNotificationEmail=False,
        ).execute()

    return spreadsheet_url or _spreadsheet_url(spreadsheet_id)


def _update_spreadsheet_sync(
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list],
    layouts: list[Stage1Layout] | None,
    summary: SummaryLayout | None = None,
) -> str:
    credentials = _get_credentials()
    sheets_service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    spreadsheet_id = _parse_spreadsheet_id(spreadsheet_id)
    sheet_title = _resolve_sheet_title(sheets_service, spreadsheet_id, sheet_name)
    _write_sheet_rows(
        sheets_service, spreadsheet_id, sheet_title, rows, layouts, summary
    )
    return _spreadsheet_url(spreadsheet_id)


async def sync_google_spreadsheet(
    tournament: Tournament, *, include_predictions: bool | None = None
) -> str:
    if include_predictions is None:
        include_predictions = await should_include_predictions(tournament)
    rows, layouts, summary = await build_stage1_sheet_rows(
        tournament, include_predictions=include_predictions
    )
    config = load_config()
    if config.google.spreadsheet_id:
        return await asyncio.to_thread(
            _update_spreadsheet_sync,
            config.google.spreadsheet_id,
            config.google.spreadsheet_sheet_name,
            rows,
            layouts,
            summary,
        )

    tour = await get_tour(tournament)
    title = f"{tournament.name} — тур {tour.number if tour else '?'}"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    return await asyncio.to_thread(
        _create_spreadsheet_sync, f"{title} ({timestamp})", rows, layouts, summary
    )


async def create_predictions_spreadsheet(tournament: Tournament) -> str:
    return await sync_google_spreadsheet(tournament)
