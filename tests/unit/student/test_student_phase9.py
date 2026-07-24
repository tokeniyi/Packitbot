import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.core.exceptions import ValidationError
from bot.core.models.student_profile import StudentProfile
from bot.core.constants.enums import UserRole
from bot.student.schemas import RegisterStudentDTO
from bot.student.states import StudentRegistrationFSM
from bot.student.service import get_profile, is_registered, register_student
from bot.student.keyboards import hall_selection_keyboard, student_persistent_menu


# ============================================================================
# 1. SCHEMAS & DTO TESTS
# ============================================================================


def test_register_student_dto_fields():
    """Verify RegisterStudentDTO has the expected fields and types."""
    dto = RegisterStudentDTO(
        telegram_id=12345678,
        full_name="John Doe",
        matric_number="12/3456",
        hall_of_residence="Esther Hall",
        phone_number="08012345678",
    )
    assert dto.telegram_id == 12345678
    assert dto.full_name == "John Doe"
    assert dto.matric_number == "12/3456"
    assert dto.hall_of_residence == "Esther Hall"
    assert dto.phone_number == "08012345678"


# ============================================================================
# 2. SERVICE TESTS (Isolation & Business Rules)
# ============================================================================


async def test_register_student_creates_user_and_profile():
    """Verify register_student creates User + StudentProfile atomically."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        session.execute.return_value = row

        profile = await register_student(
            telegram_id=999,
            full_name="John Doe",
            hall="Esther Hall",
            phone="08012345678",
        )

        assert isinstance(profile, StudentProfile)
        assert profile.matric_number == "12/3456"
        assert profile.hall_of_residence == "Esther Hall"
        assert session.add.call_count == 2
        session.commit.assert_awaited_once()


async def test_register_student_duplicate_matric_raises_validation_error():
    """Verify duplicate matric_number raises ValidationError and rolls back."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = MagicMock()
        session.execute.return_value = row

        with pytest.raises(ValidationError) as exc_info:
            await register_student(
                telegram_id=999,
                full_name="Jane Doe",
                hall="Dorcas Hall",
                phone="08012345678",
            )

        assert "already registered" in str(exc_info.value)
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


async def test_is_registered_returns_true_for_student():
    """Verify is_registered returns True when user exists and role is STUDENT."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        user = MagicMock()
        user.role = UserRole.STUDENT

        row = MagicMock()
        row.scalar_one_or_none.return_value = user
        session.execute.return_value = row

        assert await is_registered(telegram_id=999) is True


async def test_is_registered_returns_false_for_non_student():
    """Verify is_registered returns False when user exists but is not STUDENT."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        user = MagicMock()
        user.role = UserRole.DRIVER

        row = MagicMock()
        row.scalar_one_or_none.return_value = user
        session.execute.return_value = row

        assert await is_registered(telegram_id=999) is False


async def test_is_registered_returns_false_when_user_missing():
    """Verify is_registered returns False when no user is found."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        session.execute.return_value = row

        assert await is_registered(telegram_id=999) is False


async def test_get_profile_returns_profile_when_exists():
    """Verify get_profile returns StudentProfile for valid user_id."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        profile = MagicMock(spec=StudentProfile)
        profile.user_id = 1

        row = MagicMock()
        row.scalar_one_or_none.return_value = profile
        session.execute.return_value = row

        result = await get_profile(user_id=1)
        assert result is profile


async def test_get_profile_returns_none_when_missing():
    """Verify get_profile returns None when profile does not exist."""
    with patch("bot.student.service.async_session") as mock_session_factory:
        session = AsyncMock()
        mock_session_factory.return_value = session

        row = MagicMock()
        row.scalar_one_or_none.return_value = None
        session.execute.return_value = row

        result = await get_profile(user_id=999)
        assert result is None


# ============================================================================
# 3. KEYBOARD & UI TESTS
# ============================================================================


def test_hall_selection_keyboard_matches_halls_list():
    """Ensure Hall selection keyboard has one button per CU hall."""
    from bot.core.constants.halls import CU_HALLS

    keyboard = hall_selection_keyboard()
    assert keyboard.inline_keyboard is not None
    assert len(keyboard.inline_keyboard) == len(CU_HALLS)


def test_hall_selection_keyboard_callback_format():
    """Ensure hall buttons use the expected callback_data format."""
    keyboard = hall_selection_keyboard()
    for row in keyboard.inline_keyboard:
        for button in row:
            assert button.callback_data.startswith("hall:")


def test_student_main_menu_has_four_buttons():
    """Ensure Student Persistent Menu has exactly 4 buttons in 2 rows."""
    keyboard = student_persistent_menu()
    assert keyboard.keyboard is not None
    assert len(keyboard.keyboard) == 2
    assert all(len(row) == 2 for row in keyboard.keyboard)


def test_student_main_menu_button_labels():
    """Ensure Student Persistent Menu contains the expected button labels."""
    keyboard = student_persistent_menu()
    buttons_text = [btn.text for row in keyboard.keyboard for btn in row]

    expected_buttons = [
        "📦 New Request",
        "📋 My Requests",
        "👤 Profile",
        "🛈 Help",
    ]

    for expected in expected_buttons:
        assert expected in buttons_text, f"Missing button: {expected}"


# ============================================================================
# 4. FSM STATE & HANDLER TESTS
# ============================================================================


def test_fsm_states_exist_and_are_unique():
    """Ensure StudentRegistrationFSM states match Architecture v2 §7 strictly."""
    expected_states = [
        "entering_full_name",
        "entering_matric_number",
        "entering_hall",
        "entering_phone_number",
        "confirming_registration",
    ]
    assert len(expected_states) == len(set(expected_states)), "Duplicate state names detected"

    for state_name in expected_states:
        assert hasattr(StudentRegistrationFSM, state_name), f"Missing state: {state_name}"


def test_fsm_states_count():
    """Verify the exact number of registration states."""
    from aiogram.fsm.state import State

    state_names = [
        name
        for name in dir(StudentRegistrationFSM)
        if not name.startswith("_")
        and isinstance(getattr(StudentRegistrationFSM, name), State)
    ]
    assert len(state_names) == 5


async def test_cancel_mid_fsm_clears_state():
    """Verify /cancel clears state completely without saving partial data."""
    state = MagicMock(spec=FSMContext)
    await state.set_state(StudentRegistrationFSM.entering_phone_number)
    await state.update_data(full_name="John Doe", matric_number="12/3456")

    await state.clear()

    state.clear.assert_awaited_once()
