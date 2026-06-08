from aiogram.filters.callback_data import CallbackData


class TournamentCallbackFactory(CallbackData, prefix="tournament"):
    id: int


class MenuCallbackFactory(CallbackData, prefix="menu"):
    action: str


class DrawGroupsCallbackFactory(CallbackData, prefix="draw"):
    groups: int
