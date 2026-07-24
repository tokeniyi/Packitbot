from aiogram.fsm.state import State, StatesGroup


class StudentRegistrationFSM(StatesGroup):
    entering_full_name = State()
    entering_matric_number = State()
    entering_hall = State()
    entering_phone_number = State()
    confirming_registration = State()