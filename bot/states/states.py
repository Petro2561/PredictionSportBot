from aiogram.fsm.state import State, StatesGroup, default_state


class FSMFillParametres(StatesGroup):
    fill_tournament = State()
    fill_name = State()
    fill_difference_points = State()
    fill_results_points = State()
    fill_winner = State()
    fill_best_striker = State()
    fill_best_assistant = State()
    fill_confirm = State()
