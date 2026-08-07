"""
Admin module state definitions for the Packit bot.

This module defines the Finite State Machine (FSM) states used by admin
conversation flows, such as the broadcast workflow. Each ``State`` represents
a step in the conversation that the admin must complete before proceeding.

Typical usage:
    - ``BroadcastFSM`` is referenced in ``bot/admin/handler.py`` for the
      multi-step broadcast command flow.
"""

from aiogram.fsm.state import State, StatesGroup


class BroadcastFSM(StatesGroup):
    """FSM states for the admin broadcast workflow.

    The broadcast flow guides an admin through three steps:
        1. ``waiting_for_audience`` - Select the target audience
           (students, drivers, or all users).
        2. ``waiting_for_content`` - Enter the broadcast message text.
        3. ``waiting_for_confirmation`` - Review the preview and confirm
           or cancel the dispatch.

    Attributes:
        waiting_for_audience (State): Admin selects broadcast audience.
        waiting_for_content (State): Admin types broadcast message.
        waiting_for_confirmation (State): Admin confirms or cancels.
    """

    waiting_for_audience = State()
    waiting_for_content = State()
    waiting_for_confirmation = State()


class DriverEditFSM(StatesGroup):
    """FSM states for the admin driver field editing workflow.

    The driver edit flow guides an admin through updating a specific
    field on a driver record:
        1. ``waiting_for_field_value`` - Admin enters the new value for
           the selected field.

    Attributes:
        waiting_for_field_value (State): Admin inputs the new value.
    """

    waiting_for_field_value = State()
