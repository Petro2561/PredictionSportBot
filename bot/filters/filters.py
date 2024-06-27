from typing import Union

from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.utils.utils_tournament import get_tournament


class PrivateChatFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"


class IsTournamentOwner(BaseFilter):
    async def __call__(self, obj: Union[CallbackQuery, Message], state: FSMContext):
        data = await state.get_data()
        tournament = await get_tournament(data["tournament_id"])

        if not data["user_id"] or not tournament:
            return False

        if tournament.user_id == data["user_id"]:
            return True
        else:
            return False
