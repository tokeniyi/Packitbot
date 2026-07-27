import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.admin.handler import (
    cmd_admin_portal,
    cmd_verify_drivers,
    handle_approve_driver,
    handle_back_to_pending_list,
    handle_reject_driver,
    handle_view_driver_detail,
)
from bot.core.constants.enums import UserRole
from bot.core.models.user import User


def _make_message(text: str = "", user_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


def _make_callback(data: str = "", user_id: int = 1, driver_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = user_id
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = MagicMock()
    return cb


def _make_admin_user(telegram_id: int = 42) -> User:
    user = MagicMock(spec=User)
    user.telegram_id = telegram_id
    user.role = UserRole.ADMIN
    return user


class TestCmdAdminPortal:
    async def test_admin_sees_portal(self):
        message = _make_message(text="/admin")
        state = AsyncMock()
        user = _make_admin_user()

        await cmd_admin_portal(message, state, user=user)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once()

    async def test_non_admin_denied(self):
        message = _make_message(text="/admin")
        state = AsyncMock()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await cmd_admin_portal(message, state, user=student)

        message.answer.assert_awaited_once()


class TestCmdVerifyDrivers:
    async def test_lists_pending_drivers(self):
        message = _make_message(text="/verify")
        state = AsyncMock()
        user = _make_admin_user()

        drivers = [
            MagicMock(driver_id=1, full_name="Alice"),
            MagicMock(driver_id=2, full_name="Bob"),
        ]

        with patch(
            "bot.admin.handler.get_pending_drivers",
            new_callable=AsyncMock,
            return_value=(drivers, 1),
        ):
            await cmd_verify_drivers(message, state, user=user)

        message.answer.assert_awaited_once()

    async def test_no_pending_drivers_message(self):
        message = _make_message(text="/verify")
        state = AsyncMock()
        user = _make_admin_user()

        with patch(
            "bot.admin.handler.get_pending_drivers",
            new_callable=AsyncMock,
            return_value=([], 1),
        ):
            await cmd_verify_drivers(message, state, user=user)

        message.answer.assert_awaited_once()

    async def test_non_admin_denied(self):
        message = _make_message(text="/verify")
        state = AsyncMock()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await cmd_verify_drivers(message, state, user=student)

        message.answer.assert_awaited_once()


class TestHandleViewDriverDetail:
    async def test_displays_driver_detail(self):
        callback = _make_callback(data="admin_driver_approval:view:1")
        user = _make_admin_user()

        detail = MagicMock()
        detail.full_name = "Jane Doe"
        detail.phone_number = "08012345678"
        detail.vehicle_type = "sedan"
        detail.plate_number = "ABC-123"
        detail.license_number = "DL-001"
        detail.status.value = "pending_approval"
        detail.username = "janedoe"
        detail.driver_id = 1

        with patch(
            "bot.admin.handler.get_driver_application_detail",
            new_callable=AsyncMock,
            return_value=detail,
        ):
            await handle_view_driver_detail(callback, MagicMock(), user=user)

        callback.message.edit_text.assert_awaited_once()

    async def test_non_admin_denied(self):
        callback = _make_callback()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await handle_view_driver_detail(callback, MagicMock(), user=student)

        callback.answer.assert_awaited_once()


class TestHandleApproveDriver:
    async def test_approves_and_notifies(self):
        callback = _make_callback(data="admin_driver_approval:approve:1")
        user = _make_admin_user()

        approved = MagicMock()
        approved.telegram_id = 123456789
        approved.full_name = "Jane Doe"
        approved.phone_number = "08012345678"

        with patch(
            "bot.admin.handler.approve_driver", new_callable=AsyncMock, return_value=approved
        ):
            with patch(
                "bot.admin.handler.notify_driver_approval_status",
                new_callable=AsyncMock,
            ) as mock_notify:
                await handle_approve_driver(callback, MagicMock(), user=user)

                mock_notify.assert_awaited_once()
                callback.message.edit_text.assert_awaited_once()

    async def test_non_admin_denied(self):
        callback = _make_callback()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await handle_approve_driver(callback, MagicMock(), user=student)

        callback.answer.assert_awaited_once()


class TestHandleRejectDriver:
    async def test_rejects_and_notifies(self):
        callback = _make_callback(data="admin_driver_approval:reject:1")
        user = _make_admin_user()

        rejected = MagicMock()
        rejected.telegram_id = 123456789
        rejected.full_name = "Jane Doe"

        with patch(
            "bot.admin.handler.reject_driver", new_callable=AsyncMock, return_value=rejected
        ):
            with patch(
                "bot.admin.handler.notify_driver_approval_status",
                new_callable=AsyncMock,
            ) as mock_notify:
                await handle_reject_driver(callback, MagicMock(), user=user)

                mock_notify.assert_awaited_once()
                callback.message.edit_text.assert_awaited_once()

    async def test_non_admin_denied(self):
        callback = _make_callback()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await handle_reject_driver(callback, MagicMock(), user=student)

        callback.answer.assert_awaited_once()


class TestHandleBackToPendingList:
    async def test_navigates_back(self):
        callback = _make_callback()
        user = _make_admin_user()

        drivers = [MagicMock(driver_id=1, full_name="Alice")]

        with patch(
            "bot.admin.handler.get_pending_drivers",
            new_callable=AsyncMock,
            return_value=(drivers, 1),
        ):
            await handle_back_to_pending_list(callback, user=user)

        callback.message.edit_text.assert_awaited_once()

    async def test_non_admin_denied(self):
        callback = _make_callback()
        student = MagicMock()
        student.role = UserRole.STUDENT

        await handle_back_to_pending_list(callback, user=student)

        callback.answer.assert_awaited_once()
