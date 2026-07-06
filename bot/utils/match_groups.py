from typing import List, Optional

from bot.errors.error import PredictionValidationError
from db.models import Match, Player, Tournament

MATCHES_PER_HALF = 12

# Матчи, которые должны идти первыми в туре (для всех игроков)
TOUR_MATCHES_FIRST: list[tuple[str, str]] = [
    ("Канада", "Марокко"),
]


def _match_sort_key(match: Match) -> tuple[int, int]:
    teams = {match.first_team, match.second_team}
    for index, (home, away) in enumerate(TOUR_MATCHES_FIRST):
        if teams == {home, away}:
            return index, match.id
    return len(TOUR_MATCHES_FIRST), match.id


def sort_tour_matches(matches: list[Match]) -> None:
    matches.sort(key=_match_sort_key)


def splits_matches_by_groups(tournament: Tournament) -> bool:
    tour = tournament.current_tour
    if tour is None:
        return True
    return bool(getattr(tour, "split_matches_by_groups", True))


def get_group_number(player: Player) -> Optional[int]:
    if not player.group:
        return None
    return group_number_from_name(player.group)


def group_number_from_name(group_name: str) -> Optional[int]:
    try:
        return int(group_name.rsplit(" ", 1)[-1])
    except ValueError:
        return None


def player_group_numbers_from_distribution(
    group_distribution: dict[str, list[int]],
) -> dict[int, int]:
    """player_id → номер группы (1, 2, …) для конкретной жеребьёвки."""
    result: dict[int, int] = {}
    for group_name, player_ids in group_distribution.items():
        group_num = group_number_from_name(group_name)
        if group_num is None:
            continue
        for player_id in player_ids:
            result[player_id] = group_num
    return result


def player_predicts_first_half_for_group(
    group_number: int, total_groups: int
) -> bool:
    return group_number <= total_groups / 2


def tour_matches_for_player_in_tour(
    tour_matches: list[Match],
    group_number: int | None,
    total_groups: int,
    *,
    split: bool,
) -> list[Match]:
    if not split:
        return tour_matches
    if group_number is None:
        return []
    if player_predicts_first_half_for_group(group_number, total_groups):
        return tour_matches[:MATCHES_PER_HALF]
    return tour_matches[MATCHES_PER_HALF : MATCHES_PER_HALF * 2]


def get_half_boundary(match_count: int) -> int:
    return MATCHES_PER_HALF


def player_predicts_first_half(player: Player, total_groups: int) -> bool:
    group_num = get_group_number(player)
    if group_num is None:
        return False
    return group_num <= total_groups / 2


def get_tour_matches_sorted(tournament: Tournament) -> List[Match]:
    matches = [
        match
        for match in tournament.matches
        if match.tour_id == tournament.current_tour_id
    ]
    sort_tour_matches(matches)
    return matches


async def get_total_groups(tournament: Tournament) -> int:
    from bot.utils.random_distribution import get_group_history

    group_history = await get_group_history(tournament)
    if group_history:
        return len(group_history.group_distribution)
    groups = {player.group for player in tournament.players if player.group}
    return len(groups) if groups else 2


def get_matches_for_player(
    player: Player, tournament: Tournament, total_groups: int
) -> List[Match]:
    matches = get_tour_matches_sorted(tournament)
    if not matches:
        return []

    if not splits_matches_by_groups(tournament):
        return matches

    if not player.group:
        return []

    if player_predicts_first_half(player, total_groups):
        return matches[:MATCHES_PER_HALF]
    return matches[MATCHES_PER_HALF : MATCHES_PER_HALF * 2]


def match_is_in_first_half(match: Match, tournament: Tournament) -> bool:
    matches = get_tour_matches_sorted(tournament)
    for index, tour_match in enumerate(matches):
        if tour_match.id == match.id:
            return index < MATCHES_PER_HALF
    return False


def player_can_predict_match(
    player: Player, match: Match, tournament: Tournament, total_groups: int
) -> bool:
    if not splits_matches_by_groups(tournament):
        return match.tour_id == tournament.current_tour_id

    if not player.group:
        return False
    is_first_half = match_is_in_first_half(match, tournament)
    predicts_first = player_predicts_first_half(player, total_groups)
    return is_first_half == predicts_first


async def validate_player_match_access(
    player: Player, match_id: int, tournament: Tournament
) -> Match:
    from bot.utils.utils_match import get_match_by_id

    match = await get_match_by_id(match_id)
    if match.tour_id != tournament.current_tour_id:
        raise PredictionValidationError("Этот матч не относится к текущему туру")

    total_groups = await get_total_groups(tournament)
    if not player_can_predict_match(player, match, tournament, total_groups):
        half = "первые" if player_predicts_first_half(player, total_groups) else "вторые"
        raise PredictionValidationError(
            f"Ваша группа прогнозирует {half} {get_half_boundary(len(get_tour_matches_sorted(tournament)))} матчей тура"
        )
    return match


def get_half_label(
    player: Player, total_groups: int, boundary: int, tournament: Tournament | None = None
) -> str:
    if tournament is not None and not splits_matches_by_groups(tournament):
        return "все"
    if player_predicts_first_half(player, total_groups):
        return f"первые {boundary}"
    return f"вторые {boundary}"
