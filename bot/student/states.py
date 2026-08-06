"""Finite state machine (FSM) state definitions for student interactions.

This module defines the aiogram StatesGroup classes that govern
the student registration flow, delivery request creation flow,
request editing flow, feedback collection, and profile editing.

State Groups:
    - StudentRegistrationFSM: Steps for new student onboarding.
    - RequestCreateFSM: Multi-step delivery request creation.
    - RequestUpdateFSM: Editing fields of an existing request.
    - FeedbackFSM: Rating and commenting on completed deliveries.
    - StudentProfileFSM: Editing profile fields (phone, hall).
"""

# bot/student/states.py
from aiogram.fsm.state import State, StatesGroup

class StudentRegistrationFSM(StatesGroup):
    """States for the student registration flow.

    Flow: entering_full_name -> entering_hall -> entering_phone_number -> confirming_registration
    """
    entering_full_name = State()
    entering_hall = State()
    entering_phone_number = State()
    confirming_registration = State()


class RequestCreateFSM(StatesGroup):
    """States for the delivery request creation flow.

    Flow: entering_pickup_detail -> entering_dropoff_address -> entering_dropoff_landmark
          -> entering_hall -> entering_recipient_name -> entering_recipient_phone
          -> selecting_luggage_size -> entering_luggage_count -> selecting_preferred_date
          -> selecting_time_window -> entering_special_instructions -> confirming_request
    """
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


class RequestUpdateFSM(StatesGroup):
    """States for editing an existing delivery request.

    Flow: selecting_field -> editing_value -> confirming_update
    """
    selecting_field = State()
    editing_value = State()
    confirming_update = State()


class FeedbackFSM(StatesGroup):
    """States for collecting driver feedback after delivery completion.

    Flow: selecting_rating -> entering_comment
    """
    selecting_rating = State()
    entering_comment = State()

class StudentProfileFSM(StatesGroup):
    """States for editing student profile fields.

    Flow: editing_phone / editing_hall
    """
    editing_phone = State()
    editing_hall = State()