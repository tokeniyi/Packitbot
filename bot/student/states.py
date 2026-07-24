# bot/student/states.py
from aiogram.fsm.state import State, StatesGroup

class StudentRegistrationFSM(StatesGroup):
    entering_full_name = State()
    entering_hall = State()
    entering_phone_number = State()
    confirming_registration = State()


class RequestCreateFSM(StatesGroup):
    entering_pickup_detail = State()
    entering_dropoff_address = State()
    entering_dropoff_landmark = State()
    entering_hall = State()
    entering_recipient_name = State()
    entering_recipient_phone = State()
    selecting_luggage_size = State()
    entering_luggage_count = State()
    selecting_preferred_date = State()
    selecting_time_window = State()
    entering_special_instructions = State()
    confirming_request = State()