import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.core.exceptions import ValidationError
from bot.core.models.student_profile import StudentProfile
from bot.core.constants.enums import UserRole
from bot.student.handler import (
    cancel_registration,
    edit_full_name,
    edit_phone,
    receive_full_name,
    receive_phone,
    select_hall,
    submit_registration,
)
from bot.student.service import get_profile, is_registered, register_student
from bot.student.states import StudentRegistrationFSM

VALID_PHONE = "08023456789"
VALID_FULL_NAME = "John Doe"
VALID_HALL = "Esther Hall"


def _make_message(text: str = "hello", user_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


def _make_callback(data: str = "", user_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = user_id
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


async def test_register_student_creates_user_and_profile_atomically():
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        session.execute.return_value = row

        profile = await register_student(
            telegram_id=999,
            username="johndoe",
            full_name=VALID_FULL_NAME,
            hall=VALID_HALL,
            phone=VALID_PHONE,
        )

        assert isinstance(profile, StudentProfile)
        assert profile.hall_of_residence == VALID_HALL
        assert session.add.call_count == 2
        session.commit.assert_awaited_once()


async def test_register_student_duplicate_raises_validation_error():
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        session.flush.side_effect = ValidationError("IntegrityError")

        with pytest.raises(ValidationError):
            await register_student(
                telegram_id=999,
                username="janedoe",
                full_name="Jane Doe",
                hall=VALID_HALL,
                phone=VALID_PHONE,
            )

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


async def test_is_registered_returns_false_before_registration():
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        session.execute.return_value = row

        result = await is_registered(telegram_id=999)
        assert result is False


async def test_is_registered_returns_true_after_registration():
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        user = MagicMock()
        user.role = UserRole.STUDENT

        row = MagicMock()
        row.scalar_one_or_none.return_value = user
        session.execute.return_value = row

        result = await is_registered(telegram_id=999)
        assert result is True


async def test_receive_full_name_advances_to_hall_state():
    message = _make_message(text=VALID_FULL_NAME)
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})

    await receive_full_name(message, state)

    state.update_data.assert_awaited_with(full_name=VALID_FULL_NAME)
    state.set_state.assert_awaited_with(StudentRegistrationFSM.entering_hall)


async def test_receive_full_name_invalid_reprompts_same_state():
    message = _make_message(text="12345")
    state = MagicMock(spec=FSMContext)

    await receive_full_name(message, state)

    state.set_state.assert_not_awaited()


async def test_select_hall_callback_advances_to_phone_state():
    callback = _make_callback(data=f"hall_select:{VALID_HALL}")
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})

    await select_hall(callback, state)

    state.update_data.assert_awaited_with(hall_of_residence=VALID_HALL)
    state.set_state.assert_awaited_with(StudentRegistrationFSM.entering_phone_number)


async def test_receive_phone_advances_to_confirming_state():
    message = _make_message(text=VALID_PHONE)
    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={
            "full_name": VALID_FULL_NAME,
            "hall_of_residence": VALID_HALL,
            "phone_number": VALID_PHONE,
        }
    )

    await receive_phone(message, state)

    state.set_state.assert_awaited_with(StudentRegistrationFSM.confirming_registration)


async def test_receive_phone_invalid_reprompts_same_state():
    message = _make_message(text="123")
    state = MagicMock(spec=FSMContext)

    await receive_phone(message, state)

    state.set_state.assert_not_awaited()


async def test_cancel_registration_clears_state():
    message = _make_message(text="/cancel")
    state = MagicMock(spec=FSMContext)

    await cancel_registration(message, state)

    state.clear.assert_awaited_once()


async def test_submit_registration_creates_profile():
    callback = _make_callback(data="review_submit")
    state = MagicMock(spec=FSMContext)
    state.get_data = AsyncMock(
        return_value={
            "full_name": VALID_FULL_NAME,
            "hall_of_residence": VALID_HALL,
            "phone_number": VALID_PHONE,
        }
    )
    state.clear = AsyncMock()

    with patch("bot.student.handler.register_student", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = MagicMock(spec=StudentProfile)
        await submit_registration(callback, state)

        mock_reg.assert_awaited_once_with(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=VALID_FULL_NAME,
            hall=VALID_HALL,
            phone=VALID_PHONE,
        )
        state.clear.assert_awaited_once()


async def test_submit_registration_shows_error_on_duplicate():
    callback = _make_callback(data="review_submit")
    state = MagicMock(spec=FSMContext)
    state.get_data = AsyncMock(
        return_value={
            "full_name": VALID_FULL_NAME,
            "hall_of_residence": VALID_HALL,
            "phone_number": VALID_PHONE,
        }
    )

    with patch("bot.student.handler.register_student", new_callable=AsyncMock) as mock_reg:
        mock_reg.side_effect = ValidationError(
            "This full name is already registered."
        )
        await submit_registration(callback, state)

        callback.message.edit_text.assert_awaited_once()


async def test_edit_full_name_goes_back_to_name_state():
    callback = _make_callback(data="review_edit_full_name")
    callback.message.answer = AsyncMock()
    state = AsyncMock()

    await edit_full_name(callback, state)

    state.set_state.assert_awaited_with(StudentRegistrationFSM.entering_full_name)


async def test_edit_phone_goes_back_to_phone_state():
    callback = _make_callback(data="review_edit_phone_number")
    callback.message.answer = AsyncMock()
    state = AsyncMock()

    await edit_phone(callback, state)

    state.set_state.assert_awaited_with(StudentRegistrationFSM.entering_phone_number)
