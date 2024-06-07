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
    first_step = State()
    tournament_menu = State()
