from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


button_tournaments = InlineKeyboardButton(
    text="Мои турниры", callback_data="my_tournaments"
)
button_create = InlineKeyboardButton(
    text="Создать турнир", callback_data="create_tournament"
)

tournament = InlineKeyboardBuilder()
tournament.add(button_tournaments)
tournament.add(button_create)
tournament_keyboard = tournament.as_markup()

button_yes = InlineKeyboardButton(text="Да", callback_data="yes")
button_no = InlineKeyboardButton(text="Нет", callback_data="no")
yes_no_keyboard = InlineKeyboardBuilder()
yes_no_keyboard.add(button_yes)
yes_no_keyboard.add(button_no)
yes_no_keyboard = yes_no_keyboard.as_markup()

def get_add_bot_keyboard(bot_username: str, tournament_id) -> InlineKeyboardMarkup:
    admin_permissions = (
        "change_info+post_messages+edit_messages+delete_messages+"
        "restrict_members+invite_users+pin_messages+manage_topics+"
        "promote_members+manage_video_chats+anonymous+manage_chat+"
        "post_stories+edit_stories+delete_stories"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить бота в группу", url=f"https://t.me/{bot_username}?startgroup={tournament_id}&admin={admin_permissions}")]
        ]
    )

def join_tournament_keyboard(bot_username, tournament_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в турнир", url=f"https://t.me/{bot_username}?start={tournament_id}")]
        ]
    )
