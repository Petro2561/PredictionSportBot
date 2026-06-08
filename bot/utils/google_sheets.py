import asyncio
import json
import logging
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
    get_matches_for_player,
    get_tour_matches_sorted,
)
from bot.utils.utils_tournament import get_tournament
from db.crud.group_history import crud_group_history
from db.crud.tournament import crud_tournament
from db.db import get_async_session
from db.models import Match, MatchPrediction, Player, Tournament, TournamentPrediction
from sqlalchemy import select

logger = logging.getLogger(__name__)

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

GROUP_BLOCK_WIDTH = 7
FIRST_TOUR_LABEL = "1-й тур"
HALF_LABELS = ("часть 1 (матчи 1–12)", "часть 2 (матчи 13–24)")
GROUP_LABELS = (
    "Группа A — матчи 1–12",
    "Группа B — матчи 13–24",
    "Группа C",
    "Группа D",
)


def tour_has_started(tournament: Tournament) -> bool:
    if not tournament.current_tour_id or not tournament.current_tour:
        return False
    return datetime.now() >= tournament.current_tour.next_deadline


def tour_starts_at(tournament: Tournament):
    if not tournament.current_tour_id or not tournament.current_tour:
        return None
    return tournament.current_tour.next_deadline


async def should_include_predictions(tournament: Tournament) -> bool:
    config = load_config()
    if config.google.skip_deadline_check:
        return True
    tournament = await get_tournament(tournament.id)
    return tour_has_started(tournament)


def _group_start_col(group_index: int) -> int:
    return 1 + group_index * GROUP_BLOCK_WIDTH


def _sheet_width(num_groups: int) -> int:
    return 1 + num_groups * GROUP_BLOCK_WIDTH


def _pad_row(row: list, width: int) -> list:
    if len(row) < width:
        return row + [""] * (width - len(row))
    return row[:width]


def _match_label(match: Match) -> str:
    return f"{match.first_team} – {match.second_team}"


def _build_schedule_rows(matches: list[Match], width: int) -> list[list]:
    first_half = matches[:MATCHES_PER_HALF]
    second_half = matches[MATCHES_PER_HALF : MATCHES_PER_HALF * 2]
    rows: list[list] = [_pad_row([], width)]

    tour_row = _pad_row([], width)
    tour_row[0] = FIRST_TOUR_LABEL
    rows.append(tour_row)

    header = _pad_row([], width)
    header[1] = HALF_LABELS[0]
    header[_group_start_col(1)] = HALF_LABELS[1]
    rows.append(header)

    for index in range(MATCHES_PER_HALF):
        row = _pad_row([], width)
        if index < len(first_half):
            match = first_half[index]
            row[1] = _match_label(match)
            if match.first_team_score is not None:
                row[2] = match.first_team_score
                row[3] = match.second_team_score
        if index < len(second_half):
            start = _group_start_col(1)
            match = second_half[index]
            row[start] = _match_label(match)
            if match.first_team_score is not None:
                row[start + 1] = match.first_team_score
                row[start + 2] = match.second_team_score
        rows.append(row)

    rows.append(_pad_row([], width))
    rows.append(_pad_row([], width))
    return rows


def _build_group_headers_row(num_groups: int, width: int) -> list:
    row = _pad_row([], width)
    for group_index in range(num_groups):
        row[_group_start_col(group_index)] = GROUP_LABELS[group_index]
    return row


def _build_standings_rows(
    group_players: list[list[Player]],
    width: int,
    extras_by_player: dict[int, tuple[str, str]],
) -> list[list]:
    max_players = max((len(players) for players in group_players), default=0)
    rows: list[list] = []
    for player_index in range(max_players):
        row = _pad_row([], width)
        for group_index, players in enumerate(group_players):
            if player_index >= len(players):
                continue
            player = players[player_index]
            striker, assistant = extras_by_player.get(player.id, ("", ""))
            start = _group_start_col(group_index)
            row[start] = player.user.name or ""
            row[start + 1] = player.points
            row[start + 2] = striker
            row[start + 3] = assistant
        rows.append(row)
    return rows


def _build_prediction_rows(
    group_players: list[list[Player]],
    tournament: Tournament,
    total_groups: int,
    predictions_by_player: dict[int, dict[int, dict]],
    width: int,
    include_predictions: bool,
) -> list[list]:
    rows: list[list] = []
    max_players = max((len(players) for players in group_players), default=0)

    for player_index in range(max_players):
        matches_by_group = [
            get_matches_for_player(players[player_index], tournament, total_groups)
            if player_index < len(players)
            else []
            for players in group_players
        ]
        if not any(matches_by_group):
            continue

        for match_index in range(max(len(matches) for matches in matches_by_group)):
            row = _pad_row([], width)
            for group_index, players in enumerate(group_players):
                if player_index >= len(players):
                    continue
                player_matches = matches_by_group[group_index]
                if match_index >= len(player_matches):
                    continue
                player = players[player_index]
                match = player_matches[match_index]
                start = _group_start_col(group_index)
                row[start] = player.user.name or ""
                row[start + 1] = _match_label(match)
                if include_predictions:
                    prediction = predictions_by_player.get(player.id, {}).get(match.id)
                    if prediction:
                        row[start + 2] = prediction["s1"]
                        row[start + 3] = prediction["s2"]
                        if match.first_team_score is not None:
                            row[start + 4] = prediction["points"]
            rows.append(row)
    return rows


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


async def build_stage1_sheet_rows(
    tournament: Tournament, *, include_predictions: bool
) -> list[list]:
    async for session in get_async_session():
        tournament = await crud_tournament.get_tournament(tournament.id, session)
        tour = tournament.current_tour
        if not tour or tour.number != 1:
            return [["Матчи первого тура ещё не установлены"]]

        group_history = await crud_group_history.get_last_group_history(
            tournament.id, session
        )
        predictions_by_player = await _load_match_predictions_by_player(
            session, tournament.id, tour.id
        )
        extras_by_player = await _load_tournament_extras_by_player(
            session, tournament.id
        )

        matches = get_tour_matches_sorted(tournament)
        player_map = {
            player.id: player
            for player in tournament.players
            if not player.is_eliminated
        }

        if group_history:
            group_players = _sorted_group_players(
                group_history.group_distribution, player_map
            )
        else:
            players = sorted(
                player_map.values(),
                key=lambda player: (-player.points, player.user.name or ""),
            )
            group_players = [players] if players else []

        num_groups = len(group_players) or 2
        width = _sheet_width(num_groups)
        rows = _build_schedule_rows(matches, width)

        tour_header = _pad_row([], width)
        tour_header[0] = FIRST_TOUR_LABEL
        rows.append(tour_header)
        rows.append(_build_group_headers_row(num_groups, width))
        rows.extend(_build_standings_rows(group_players, width, extras_by_player))

        if group_players:
            total_groups = (
                len(group_history.group_distribution) if group_history else 1
            )
            rows.extend(
                _build_prediction_rows(
                    group_players,
                    tournament,
                    total_groups,
                    predictions_by_player,
                    width,
                    include_predictions,
                )
            )

        return rows


def _create_spreadsheet_sync(title: str, rows: list[list[str]]) -> str:
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

    _write_sheet_rows(sheets_service, spreadsheet_id, "Стадия 1", rows)

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

    return spreadsheet_url or f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


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


def _write_sheet_rows(
    sheets_service, spreadsheet_id: str, sheet_title: str, rows: list[list[str]]
) -> None:
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
        valueInputOption="RAW",
        body={"values": padded_rows},
    ).execute()


def _update_spreadsheet_sync(
    spreadsheet_id: str, sheet_name: str, rows: list[list[str]]
) -> str:
    credentials = _get_credentials()
    sheets_service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    spreadsheet_id = _parse_spreadsheet_id(spreadsheet_id)
    sheet_title = _resolve_sheet_title(sheets_service, spreadsheet_id, sheet_name)
    _write_sheet_rows(sheets_service, spreadsheet_id, sheet_title, rows)
    return _spreadsheet_url(spreadsheet_id)


async def sync_google_spreadsheet(
    tournament: Tournament, *, include_predictions: bool | None = None
) -> str:
    if include_predictions is None:
        include_predictions = await should_include_predictions(tournament)
    rows = await build_stage1_sheet_rows(
        tournament, include_predictions=include_predictions
    )
    config = load_config()
    if config.google.spreadsheet_id:
        return await asyncio.to_thread(
            _update_spreadsheet_sync,
            config.google.spreadsheet_id,
            config.google.spreadsheet_sheet_name,
            rows,
        )

    tour = await get_tour(tournament)
    title = f"{tournament.name} — тур {tour.number if tour else '?'}"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    return await asyncio.to_thread(
        _create_spreadsheet_sync, f"{title} ({timestamp})", rows
    )


async def create_predictions_spreadsheet(tournament: Tournament) -> str:
    return await sync_google_spreadsheet(tournament)
