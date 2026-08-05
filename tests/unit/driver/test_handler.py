import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.core.models.driver_profile import DriverProfile
from bot.driver.handler import (
    cancel_driver_registration,
    check_approval_status,
    process_full_name,
    process_license_number,
    process_phone_number,
    process_plate_number,
    process_vehicle_type,
    process_submit_registration,
    start_driver_registration,
    toggle_availability_handler,
)
from bot.driver.service import get_driver_profile_by_telegram_id
from bot.driver.states import DriverRegistrationFSM


def _make_message(text: str = "hello", user_id: int = 1) -> MagicMock:
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


class TestStartDriverRegistration:
    async def test_advances_to_full_name_state_when_new(self):
        message = _make_message(text="/register_driver")
        state = AsyncMock()

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await start_driver_registration(message, state)

        state.set_state.assert_awaited_with(DriverRegistrationFSM.entering_full_name)

    async def test_shows_pending_menu_when_already_pending(self):
        message = _make_message(text="/register_driver")
        state = AsyncMock()
        pending_profile = MagicMock(spec=DriverProfile)
        pending_profile.status = DriverStatus.PENDING_APPROVAL

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=pending_profile,
        ):
            await start_driver_registration(message, state)

        message.answer.assert_awaited_once()

    async def test_shows_approved_menu_when_already_approved(self):
        message = _make_message(text="/register_driver")
        state = AsyncMock()
        approved_profile = MagicMock(spec=DriverProfile)
        approved_profile.status = DriverStatus.APPROVED
        approved_profile.availability = DriverAvailability.AVAILABLE

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=approved_profile,
        ):
            await start_driver_registration(message, state)

        message.answer.assert_awaited_once()


class TestProcessFullName:
    async def test_advances_to_phone_state(self):
        message = _make_message(text="John Doe")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        await process_full_name(message, state)

        state.update_data.assert_awaited_with(full_name="John Doe")
        state.set_state.assert_awaited_with(DriverRegistrationFSM.entering_phone_number)

    async def test_rejects_invalid_name(self):
        message = _make_message(text="12345")
        state = AsyncMock()

        await process_full_name(message, state)

        state.set_state.assert_not_awaited()


class TestProcessPhoneNumber:
    async def test_advances_to_vehicle_type_state(self):
        message = _make_message(text="08023456789")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        await process_phone_number(message, state)

        state.update_data.assert_awaited_with(phone_number="+2348023456789")
        state.set_state.assert_awaited_with(DriverRegistrationFSM.selecting_vehicle_type)

    async def test_rejects_invalid_phone(self):
        message = _make_message(text="abc")
        state = AsyncMock()

        await process_phone_number(message, state)

        state.set_state.assert_not_awaited()


class TestProcessVehicleType:
    async def test_advances_to_plate_state(self):
        callback = _make_callback(data="driver_vtype:sedan")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        await process_vehicle_type(callback, state)

        state.update_data.assert_awaited_with(vehicle_type="sedan")
        state.set_state.assert_awaited_with(DriverRegistrationFSM.entering_plate_number)

    async def test_rejects_invalid_vehicle_type(self):
        callback = _make_callback(data="driver_vtype:rocket")
        state = AsyncMock()

        await process_vehicle_type(callback, state)

        callback.answer.assert_awaited()


class TestProcessPlateNumber:
    async def test_advances_to_license_state(self):
        message = _make_message(text="ABC-123DE")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        await process_plate_number(message, state)

        state.update_data.assert_awaited_with(plate_number="ABC-123DE")
        state.set_state.assert_awaited_with(DriverRegistrationFSM.entering_license_number)

    async def test_rejects_invalid_plate(self):
        message = _make_message(text="!!!")
        state = AsyncMock()

        await process_plate_number(message, state)

        state.set_state.assert_not_awaited()


class TestProcessLicenseNumber:
    async def test_advances_to_confirming_state(self):
        message = _make_message(text="DL-987654")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})

        await process_license_number(message, state)

        state.set_state.assert_awaited_with(DriverRegistrationFSM.confirming_registration)


class TestProcessSubmitRegistration:
    async def test_calls_register_driver_and_clears_state(self):
        callback = _make_callback(data="driver_submit_reg")
        state = AsyncMock()
        state.get_data = AsyncMock(
            return_value={
                "full_name": "Jane Doe",
                "phone_number": "08012345678",
                "vehicle_type": "sedan",
                "plate_number": "ABC-123DE",
                "license_number": "DL-987654",
            }
        )
        state.clear = AsyncMock()

        with patch(
            "bot.driver.handler.register_driver", new_callable=AsyncMock
        ) as mock_reg:
            mock_reg.return_value = MagicMock(spec=DriverProfile)
            await process_submit_registration(callback, state)

            mock_reg.assert_awaited_once()
            state.clear.assert_awaited_once()


class TestCancelDriverRegistration:
    async def test_clears_state_and_returns_home(self):
        message = _make_message(text="/cancel_driver_reg")
        state = AsyncMock()

        await cancel_driver_registration(message, state)

        state.clear.assert_awaited_once()


class TestCheckApprovalStatus:
    async def test_shows_approved_message(self):
        message = _make_message(text="🔄 Check Approval Status")
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.AVAILABLE

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            await check_approval_status(message)

        message.answer.assert_awaited_once()

    async def test_shows_pending_message(self):
        message = _make_message(text="🔄 Check Approval Status")
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.PENDING_APPROVAL

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            await check_approval_status(message)

        message.answer.assert_awaited_once()


class TestToggleAvailabilityHandler:
    async def test_toggles_to_available(self):
        message = _make_message(text="🟢 Go Available")
        profile = MagicMock(spec=DriverProfile)
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
                message.answer.assert_awaited_once()

    async def test_blocks_when_not_approved(self):
        message = _make_message(text="🟢 Go Available")
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.PENDING_APPROVAL
        profile.availability = DriverAvailability.OFFLINE

        with patch(
            "bot.driver.handler.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            await toggle_availability_handler(message)

        message.answer.assert_awaited_once()
