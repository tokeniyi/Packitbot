import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.driver.handler import (
    start_driver_registration,
    process_full_name,
    process_phone_number,
    process_vehicle_type,
    process_plate_number,
    process_license_number,
    process_submit_registration,
    check_approval_status,
    toggle_availability_handler,
)
from bot.driver.service import register_driver
from bot.driver.states import DriverRegistrationFSM
from bot.driver.schemas import RegisterDriverDTO


class _AsyncSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_message(text: str = "", user_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


def _make_callback(data: str = "", user_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = user_id
    cb.from_user.username = "testuser"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


class TestDriverRegistrationFlowIntegration:
    async def test_full_registration_flow(self):
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        message = _make_message(text="John Doe", user_id=1)
        await process_full_name(message, state)
        state.update_data.assert_awaited_with(full_name="John Doe")

    async def test_registration_submit_creates_profile(self):
        callback = _make_callback(data="driver_submit_reg", user_id=1)
        state = AsyncMock()
        state.get_data = AsyncMock(
            return_value={
                "full_name": "John Doe",
                "phone_number": "+2348023456789",
                "vehicle_type": "sedan",
                "plate_number": "ABC-123DE",
                "license_number": "DL-001",
            }
        )
        state.clear = AsyncMock()

        with patch(
            "bot.driver.handler.register_driver", new_callable=AsyncMock
        ) as mock_reg:
            mock_reg.return_value = MagicMock()
            await process_submit_registration(callback, state)
            mock_reg.assert_awaited_once()
            state.clear.assert_awaited_once()

    async def test_check_approval_status_for_approved_driver(self):
        message = _make_message(text="🔄 Check Approval Status", user_id=1)

        profile = MagicMock()
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.AVAILABLE

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            await check_approval_status(message)

        message.answer.assert_awaited_once()

    async def test_toggle_availability_success(self):
        message = _make_message(text="🟢 Go Available", user_id=1)

        profile = MagicMock()
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.OFFLINE

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            with patch(
                "bot.driver.handler.set_driver_availability",
                new_callable=AsyncMock,
                return_value=profile,
            ) as mock_set:
                profile.availability = DriverAvailability.AVAILABLE
                await toggle_availability_handler(message)
                mock_set.assert_awaited_once()

    async def test_registration_service_with_duplicate_plate_raises(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            ctx = _AsyncSessionCtx(session)
            mock_session_factory.return_value = ctx

            user_row = MagicMock()
            user_row.scalar_one_or_none.return_value = None
            dp_row = MagicMock()
            dp_row.scalar_one_or_none.return_value = None

            def execute_side_effect(stmt):
                if "User" in str(stmt):
                    return user_row
                return dp_row

            session.execute.side_effect = execute_side_effect
            session.add.return_value = None

            flush_call_count = 0

            async def _raise_on_second_flush(*args, **kwargs):
                nonlocal flush_call_count
                flush_call_count += 1
                if flush_call_count == 2:
                    from sqlalchemy.exc import IntegrityError as IE
                    raise IE("duplicate key", None, None)

            session.flush = AsyncMock(side_effect=_raise_on_second_flush)

            dto = RegisterDriverDTO(
                telegram_id=123,
                full_name="John Doe",
                phone_number="08023456789",
                vehicle_type="sedan",
                plate_number="ABC-123DE",
                license_number="DL-987654",
            )

            with pytest.raises(Exception):
                await register_driver(dto, session=session)
