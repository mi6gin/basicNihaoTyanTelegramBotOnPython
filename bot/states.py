from aiogram.fsm.state import State, StatesGroup


class SupportState(StatesGroup):
    waiting_for_category = State()
    waiting_for_text = State()
    waiting_for_followup = State()


class AdminState(StatesGroup):
    waiting_for_answer = State()
