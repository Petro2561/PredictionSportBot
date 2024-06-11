from bot.filters.filters import PrivateChatFilter
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.types import Message

from bot.utils.utils_tournament import get_tournament
from bot.utils.utils_user_player import create_player, get_or_create_user

ADDING_TO_TOURNAMENT = "Вы успешно добавлены в турнир"


# router = Router()

# @router.message(CommandStart(deep_link=True), PrivateChatFilter())
# async def handler(message: Message, command: CommandObject):
#     user = await get_or_create_user(message)
#     data_for_player = {"user_id": user.id, "tournament_id": int(command.args)}
#     await create_player(data_for_player)
#     await message.answer(ADDING_TO_TOURNAMENT)
#     tournament = await get_tournament(int(command.args))
#     if tournament.winner:
        
