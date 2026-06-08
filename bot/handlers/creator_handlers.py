from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from bot.keyboards.creator_keyboard import join_tournament_keyboard

JOIN_GROUP = "Вступить в турнир"

router = Router()


@router.message(CommandStart(deep_link=True))
async def add_bot_to_group_handler(message: Message, command: CommandObject):
    bot_username = (await message.bot.get_me()).username
    join_message = await message.answer(
        JOIN_GROUP, reply_markup=join_tournament_keyboard(bot_username, command.args)
    )
    await message.bot.pin_chat_message(
        chat_id=message.chat.id, message_id=join_message.message_id
    )
