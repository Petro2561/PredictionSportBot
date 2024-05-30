import logging

from aiogram import Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.keyboard import tournament_keyboard, yes_no_keyboard
from bot.states.states import FSMFillParametres
from bot.utils import create_tournament_db, create_user

START_PHRASE = "Этот бот для создания турниров прогнозов"

router = Router()


@router.message(CommandStart())
async def process_start_command(message: Message, state: FSMContext):
    await state.set_state(FSMFillParametres.fill_tournament)
    await message.answer(text=START_PHRASE, reply_markup=tournament_keyboard)


@router.callback_query(
    lambda callback: callback.data == "create_tournament",
    StateFilter(FSMFillParametres.fill_tournament),
)
async def create_tournament_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    data = {
        "username": callback_query.from_user.username,
        "name": f"{callback_query.from_user.first_name} {callback_query.from_user.last_name}",
        "telegram_id": callback_query.from_user.id,
    }
    user = await create_user(data)
    await state.update_data(user_id=int(user.id))
    await state.set_state(FSMFillParametres.fill_name)
    await callback_query.message.answer("Вы начали создание турнира.")
    await callback_query.message.answer("Введите название турнира:")


@router.message(StateFilter(FSMFillParametres.fill_name))
async def fill_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(FSMFillParametres.fill_results_points)
    await message.answer("Введите очки за точно угаданный счет:")


@router.message(StateFilter(FSMFillParametres.fill_results_points))
async def fill_results_points(message: Message, state: FSMContext):
    await state.update_data(results_points=int(message.text))
    await state.set_state(FSMFillParametres.fill_difference_points)
    await message.answer(
        "Введите очки за угаданную разницу голов, например, если прогноз был 2-0, а игрок написал 3-1, то он верно угадал разницу голов:"
    )


@router.message(StateFilter(FSMFillParametres.fill_difference_points))
async def fill_difference_points(message: Message, state: FSMContext):
    await state.update_data(difference_points=int(message.text))
    await state.set_state(FSMFillParametres.fill_winner)
    await message.answer("Нужно ли угадывать победителя?", reply_markup=yes_no_keyboard)


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_winner),
)
async def fill_winner(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(winner=callback_query.data == "yes")
    await callback_query.message.delete()
    await state.set_state(FSMFillParametres.fill_best_striker)
    await callback_query.message.answer(
        "Нужно ли угадывать лучшего бомбардира?", reply_markup=yes_no_keyboard
    )


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_best_striker),
)
async def fill_best_striker(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(best_striker=callback_query.data == "yes")
    await callback_query.message.delete()
    await state.set_state(FSMFillParametres.fill_best_assistant)
    await callback_query.message.answer(
        "Нужно ли угадывать лучшего ассистента?", reply_markup=yes_no_keyboard
    )


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_best_assistant),
)
async def fill_best_assistant(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(best_assistant=callback_query.data == "yes")
    await callback_query.message.delete()
    data = await state.get_data()
    print(data)
    await create_tournament_db(data)
    summary = (
        f"Название турнира: {data['name']}\n"
        f"Очки за результаты: {data['results_points']}\n"
        f"Очки за разницу: {data['difference_points']}\n"
        f"Угадывание победителя: {'Да' if data['guess_winner'] else 'Нет'}\n"
        f"Угадывание лучшего бомбардира: {'Да' if data['best_striker'] else 'Нет'}\n"
        f"Угадывание лучшего ассистента: {'Да' if data['best_assistant'] else 'Нет'}"
    )
    await callback_query.message.answer(
        f"Турнир успешно создан! Информация:\n{summary}"
    )
