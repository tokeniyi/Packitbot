# bot/driver/states.py
from aiogram.fsm.state import State, StatesGroup


class DriverRegistrationFSM(StatesGroup):
    entering_full_name = State()
    entering_phone_number = State()
    selecting_vehicle_type = State()
    entering_plate_number = State()
    entering_license_number = State()
    confirming_registration = State()
