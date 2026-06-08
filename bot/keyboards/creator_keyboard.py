from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def join_tournament_keyboard(bot_username, tournament_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Вступить в турнир",
                    url=f"https://t.me/{bot_username}?start={tournament_id}",
                )
            ]
        ]
    )
