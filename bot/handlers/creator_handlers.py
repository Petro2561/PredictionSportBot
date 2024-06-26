import logging

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.filters.filters import PrivateChatFilter
from bot.keyboards.creator_keyboard import (get_add_bot_keyboard,
                                            join_tournament_keyboard,
                                            tournament_keyboard,
                                            yes_no_keyboard)
from bot.states.states import FSMFillParametres
from bot.utils.utils_tournament import create_tournament_db
from bot.utils.utils_user_player import (get_or_create_player,
                                         get_or_create_user)

START_PHRASE = "Этот бот для создания турниров прогнозов"
START_TOURNAMENT_PHRASE = "Вы начали создание турнира."
FILL_TOURNAMENT_NAME = "Введите название турнира"
FILL_POINTS = "Введите очки за точно угаданный счет:"
FILL_DIFFERENCE_POINTS = "Введите очки за угаданную разницу голов, например, если прогноз был 2-0, а игрок написал 3-1, то он верно угадал разницу голов:"
ASK_WINNER = "Нужно ли угадывать команду победителя турнира?"
ASK_BEST_STRIKER = "Нужно ли угадывать лучшего бомбардира?"
ASK_BEST_ASSISTANT = "Нужно ли угадывать лучшего ассистента?"
TOURNAMENT_CREATED = "Турнир успешно создан! Информация:\n"
JOIN_GROUP = "Вступить в турнир"
ADDING_TO_TOURNAMENT = "Вы успешно добавлены в турнир"
FILL_RESULTS_POINTS = "Введите очки за правильно угаданный результат"

router = Router()


@router.message(CommandStart(), PrivateChatFilter())
async def process_start_command(message: Message, state: FSMContext):
    await message.answer(text=START_PHRASE, reply_markup=tournament_keyboard)


@router.callback_query(lambda callback: callback.data == "create_tournament")
async def create_tournament_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    user = await get_or_create_user(callback_query)
    await state.update_data(user_id=int(user.id))
    await state.set_state(FSMFillParametres.fill_name)
    await callback_query.message.answer(START_TOURNAMENT_PHRASE)
    await callback_query.message.answer(FILL_TOURNAMENT_NAME)


@router.message(StateFilter(FSMFillParametres.fill_name))
async def fill_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(FSMFillParametres.fill_exact_score)
    await message.answer(FILL_POINTS)


@router.message(StateFilter(FSMFillParametres.fill_exact_score))
async def fill_exact_points(message: Message, state: FSMContext):
    await state.update_data(exact_score_points=message.text)
    await state.set_state(FSMFillParametres.fill_difference_points)
    await message.answer(FILL_DIFFERENCE_POINTS)


@router.message(StateFilter(FSMFillParametres.fill_difference_points))
async def fill_results_points(message: Message, state: FSMContext):
    await state.update_data(difference_points=int(message.text))
    await state.set_state(FSMFillParametres.fill_results_points)
    await message.answer(FILL_RESULTS_POINTS)


@router.message(StateFilter(FSMFillParametres.fill_results_points))
async def fill_difference_points(message: Message, state: FSMContext):
    await state.update_data(results_points=int(message.text))
    await state.set_state(FSMFillParametres.fill_winner)
    await message.answer(ASK_WINNER, reply_markup=yes_no_keyboard)


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_winner),
)
async def fill_winner(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(winner=callback_query.data == "yes")
    await callback_query.message.delete()
    await state.set_state(FSMFillParametres.fill_best_striker)
    await callback_query.message.answer(ASK_BEST_STRIKER, reply_markup=yes_no_keyboard)


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_best_striker),
)
async def fill_best_striker(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(best_striker=callback_query.data == "yes")
    await callback_query.message.delete()
    await state.set_state(FSMFillParametres.fill_best_assistant)
    await callback_query.message.answer(
        ASK_BEST_ASSISTANT, reply_markup=yes_no_keyboard
    )


@router.callback_query(
    lambda callback: callback.data in ["yes", "no"],
    StateFilter(FSMFillParametres.fill_best_assistant),
)
async def fill_best_assistant(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(best_assistant=callback_query.data == "yes")
    await callback_query.message.delete()
    data = await state.get_data()
    data_for_tournament = {
        "name": data["name"],
        "exact_score_points": data["exact_score_points"],
        "results_points": data["results_points"],
        "difference_points": data["difference_points"],
        "winner": data["winner"],
        "best_striker": data["best_striker"],
        "best_assistant": data["best_assistant"],
        "user_id": data["user_id"],
    }
    tournament = await create_tournament_db(data_for_tournament)
    summary = (
        f"Название турнира: {data['name']}\n"
        f"Очки за точно угаданный счет: {data['exact_score_points']}\n"
        f"Очки за результаты: {data['results_points']}\n"
        f"Очки за разницу: {data['difference_points']}\n"
        f"Угадывание победителя: {'Да' if data['winner'] else 'Нет'}\n"
        f"Угадывание лучшего бомбардира: {'Да' if data['best_striker'] else 'Нет'}\n"
        f"Угадывание лучшего ассистента: {'Да' if data['best_assistant'] else 'Нет'}"
    )
    logging.info(f"Создан турнир {summary}")
    bot_username = (await callback_query.bot.get_me()).username
    await callback_query.message.answer(
        f"{TOURNAMENT_CREATED}{summary}",
        reply_markup=get_add_bot_keyboard(bot_username, tournament_id=tournament.id),
    )


@router.message(CommandStart(deep_link=True))
async def handler(message: Message, command: CommandObject):
    bot_username = (await message.bot.get_me()).username
    join_message = await message.answer(
        JOIN_GROUP, reply_markup=join_tournament_keyboard(bot_username, command.args)
    )
    await message.bot.pin_chat_message(
        chat_id=message.chat.id, message_id=join_message.message_id
    )
