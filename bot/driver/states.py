"""FSM state machine definitions for driver registration.

This module declares the :class:`DriverRegistrationFSM` StatesGroup, which
drives the step-by-step data-collection wizard used in
``bot/driver/handler.py``. Each state corresponds to one prompt that the
user must answer (or cancel out of) before progressing.

States
------
- ``entering_full_name``          -> Prompt: full name (validated via ``validate_full_name``).
- ``entering_phone_number``       -> Prompt: phone number (validated via ``validate_phone``).
- ``selecting_vehicle_type``      -> Prompt: vehicle type from an inline keyboard.
- ``entering_plate_number``       -> Prompt: vehicle plate number (validated via ``validate_plate_number``).
- ``entering_license_number``     -> Prompt: driver's license number (validated via ``validate_license_number``).
- ``confirming_registration``     -> Final review screen; no user input, only callbacks.

Depends on
----------
``aiogram.fsm.state`` (``State``, ``StatesGroup``).

Used by
-------
``bot/driver/handler.py`` — the router handlers are registered against these states.
"""

from aiogram.fsm.state import State, StatesGroup


class DriverRegistrationFSM(StatesGroup):
    """StatesGroup representing the driver registration wizard flow.

    The registration flow progresses linearly: the user is prompted for
    each field in order (full name, phone, vehicle type, plate, license),
    after which they arrive at ``confirming_registration`` for a final
    review/edit/submit screen. At any input step, ``is_editing`` may be set
    in FSM data to redirect the user back to the review screen instead of
    advancing to the next step.
    """

    entering_full_name = State()
    entering_phone_number = State()
    selecting_vehicle_type = State()
    entering_plate_number = State()
    entering_license_number = State()
    confirming_registration = State()
