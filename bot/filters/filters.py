from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

class PrivateChatFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == 'private'
    
class IsTournamentOwner(BaseFilter):
    async def __call__(self, obj: Union[CallbackQuery, Message], state: FSMContext):
        data = await state.get_data()
        user = data.get('user')
        tournament = data.get('tournament')
        
        if not user or not tournament:
            return False
        
        if tournament.user_id == user.id:
            return True
        else:
            return False