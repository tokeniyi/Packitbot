# bot/admin/states.py
from aiogram.fsm.state import State, StatesGroup


class BroadcastFSM(StatesGroup):
    waiting_for_audience = State()
    waiting_for_content = State()
    waiting_for_confirmation = State()
