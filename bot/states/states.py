from aiogram.fsm.state import State, StatesGroup


class FSMFillParametres(StatesGroup):
    fill_tournament = State()
    fill_name = State()
    fill_exact_score = State()
    fill_difference_points = State()
    fill_results_points = State()
    fill_winner = State()
    fill_best_striker = State()
    fill_best_assistant = State()
    fill_confirm = State()
    add_bot = State()


class TournamentMenu(StatesGroup):
    tournament_menu = State()
    groups = State()
    reset_points = State()
    eleminate_player = State()
    tour_date = State()
    webapp_matches = State()
    match_predictions = State()
    match_results = State()


class PredictionState(StatesGroup):
    waiting_for_winner = State()
    waiting_for_best_striker = State()
    waiting_for_best_assistant = State()
