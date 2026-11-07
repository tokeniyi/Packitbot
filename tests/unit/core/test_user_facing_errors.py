"""Regression tests for P1 #15: raw exception text must not reach users.

Four handler sites used to interpolate ``str(exc)`` into the Telegram reply,
which could expose table, column, or constraint names. After the fix:

- unexpected exceptions show ``ErrorMessages.SOMETHING_WENT_WRONG``;
- domain errors (``PackitbotError``) keep their intended, user-facing text.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.core.constants.messages import ErrorMessages
from bot.core.exceptions import ValidationError
from bot.driver.handler import process_submit_registration, toggle_availability_handler
from bot.student.handlers.registration import submit_registration
from bot.student.handlers.requests import submit_request_creation

LEAKY = 'duplicate key value violates unique constraint "users_telegram_id_key"'


def _callback() -> MagicMock:
    cb = MagicMock()
    cb.from_user.id = 1
    cb.from_user.username = "tester"
    cb.from_user.full_name = "Tester"
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


def _state(data: dict) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value=data)
    state.clear = AsyncMock()
    return state


def _sent_text(mock: AsyncMock) -> str:
    mock.assert_awaited_once()
    return mock.await_args.args[0]


async def test_student_registration_hides_raw_exception_text():
    cb = _callback()
    with patch(
        "bot.student.handlers.registration.register_student",
        new_callable=AsyncMock,
        side_effect=RuntimeError(LEAKY),
    ):
        await submit_registration(cb, _state({"full_name": "Tester", "hall": "A"}), session=AsyncMock())

    text = _sent_text(cb.message.edit_text)
    assert text == ErrorMessages.SOMETHING_WENT_WRONG
    assert "constraint" not in text and "users_telegram_id_key" not in text


async def test_student_registration_keeps_domain_error_text():
    cb = _callback()
    with patch(
        "bot.student.handlers.registration.register_student",
        new_callable=AsyncMock,
        side_effect=ValidationError("You are already registered."),
    ):
        await submit_registration(cb, _state({"full_name": "Tester", "hall": "A"}), session=AsyncMock())

    assert _sent_text(cb.message.edit_text) == "You are already registered."


async def test_driver_registration_hides_raw_exception_text():
    cb = _callback()
    state = _state(
        {
            "full_name": "Driver",
            "phone_number": "08012345678",
            "vehicle_type": "bike",
            "plate_number": "ABC123",
            "license_number": "LIC1",
        }
    )
    with patch(
        "bot.driver.handler.register_driver",
        new_callable=AsyncMock,
        side_effect=RuntimeError(LEAKY),
    ):
        await process_submit_registration(cb, state, session=AsyncMock())

    text = _sent_text(cb.message.answer)
    assert text == ErrorMessages.SOMETHING_WENT_WRONG
    assert "users_telegram_id_key" not in text


async def test_driver_availability_toggle_hides_raw_exception_text():
    message = MagicMock()
    message.from_user.id = 2
    message.answer = AsyncMock()
    profile = MagicMock(status=DriverStatus.APPROVED, availability=DriverAvailability.OFFLINE)
    with patch(
        "bot.driver.handler.get_driver_profile_by_telegram_id",
        new_callable=AsyncMock,
        return_value=profile,
    ), patch(
        "bot.driver.handler.set_driver_availability",
        new_callable=AsyncMock,
        side_effect=RuntimeError(LEAKY),
    ):
        await toggle_availability_handler(message, session=AsyncMock())

    text = _sent_text(message.answer)
    assert text == ErrorMessages.SOMETHING_WENT_WRONG
    assert "users_telegram_id_key" not in text


async def test_request_creation_hides_raw_exception_text():
    cb = _callback()
    data = {
        "pickup_detail": "x",
        "dropoff_address": "y",
        "hall_of_residence": "A",
        "recipient_name": "R",
        "recipient_phone": "08012345678",
        "luggage_size": "small",
        "luggage_count": "1",
        "preferred_date": "2026-12-01",
        "preferred_time_window": "morning",
    }
    service = MagicMock()
    service.create_request = AsyncMock(side_effect=RuntimeError(LEAKY))
    with patch("bot.student.handlers.requests.resolve_user_id", new_callable=AsyncMock, return_value=1), patch(
        "bot.student.handlers.requests.CreateRequestDTO", MagicMock()
    ), patch("bot.student.handlers.requests.RequestService", return_value=service):
        await submit_request_creation(cb, _state(data), session=AsyncMock())

    text = _sent_text(cb.message.answer)
    assert text == ErrorMessages.SOMETHING_WENT_WRONG
    assert "users_telegram_id_key" not in text
