import logging
import random
from typing import Dict, List



from bot.utils.common import get_predictions
from db.crud import crud_group_history
from db.db import get_async_session
from db.models import GroupHistory, MatchPrediction, Player, Tournament


async def random_distribution(tournament: Tournament, number_of_groups: int):
    try:
        players = [player for player in tournament.players if not player.is_eliminated]
        random.shuffle(players)
        groups = [[] for _ in range(number_of_groups)]
        for i, player in enumerate(players):
            groups[i % number_of_groups].append(player)
        group_history = await create_group_history(groups, tournament)
        await set_player_groups(group_history=group_history, tournament=tournament)
        resuls = await show_distribution(group_history.group_distribution, players)
        return resuls
    except Exception:
        logging.error("Что-то пошло нет так при жеребьевке", exc_info=True)



async def show_distribution(group_distribution: Dict[str, List[int]], players: List[Player], with_match_prediction=False):
    result_message = "Распределение по группам:\n"
    player_dict = {player.id: player for player in players if player.is_eliminated == False}
    
    for group_name, player_ids in group_distribution.items():
        result_message += f"\n{group_name}:\n"
        for player_id in player_ids:
            player = player_dict.get(player_id)
            if player:
                if with_match_prediction:
                    prediction = await get_predictions(player)
                    result_message += f"{player.user.name} @{player.user.username} Очки всего:{player.points} {prediction}\n"
                else: 
                    result_message += f"{player.user.name} @{player.user.username} {player.points}\n"
            
    
    return result_message




async def create_group_history(groups: List[list], tournament: Tournament):
    group_distribution = {
        f"Group {idx + 1}": [player.id for player in group]
        for idx, group in enumerate(groups)
    }
    data = {"group_distribution": group_distribution, "tournament_id": tournament.id}
    async for session in get_async_session():
        group_history = await crud_group_history.create(data, session)
        return group_history


async def set_player_groups(group_history: GroupHistory, tournament: Tournament):
    group_distribution = group_history.group_distribution
    async for session in get_async_session():
        for group_name, player_ids in group_distribution.items():
            for player_id in player_ids:
                player = next(
                    (p for p in tournament.players if p.id == player_id), None
                )
                if player:
                    player.group = group_name
                    session.add(player)
        await session.commit()

async def get_group_history(tournament):
    """Возвращает последний распределение по группам"""
    async for session in get_async_session():
        group_history = await crud_group_history.get_last_group_history(tournament.id, session)
        return group_history