from aiogram.filters.callback_data import CallbackData

class TournamentCallbackFactory(CallbackData, prefix='tournament'):
    id: int