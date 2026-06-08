from aiogram.fsm.state import State, StatesGroup


class TournamentMenu(StatesGroup):
    tournament_menu = State()
    match_predictions = State()
    admin_draw_groups_count = State()


class PredictionState(StatesGroup):
    waiting_for_winner = State()
    waiting_for_best_striker = State()
    waiting_for_best_assistant = State()
