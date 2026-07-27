import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext

from bot.admin.handler import (
    cmd_verify_drivers,
    handle_approve_driver,
    handle_reject_driver,
    handle_view_driver_detail,
    handle_back_to_pending_list,
)
from bot.admin.service import approve_driver, reject_driver, get_pending_drivers
from bot.core.constants.enums import AdminActionType, DriverStatus, UserRole
from bot.core.services.notification_service import notify_driver_approval_status
from bot.core.models.admin_action_log import AdminActionLog
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User


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
    user.id = 99
    return user


class TestAdminApprovalFlowIntegration:
    async def test_full_approval_flow(self):
        session = AsyncMock()

        dp, user = _make_driver_and_user(status=DriverStatus.PENDING_APPROVAL)
        admin_user = _make_admin_user(telegram_id=42)

        admin_result = MagicMock()
        admin_result.scalar_one_or_none.return_value = admin_user
        driver_result = MagicMock()
        driver_result.first.return_value = (dp, user)
        session.execute.side_effect = [admin_result, driver_result]
        session.flush.return_value = None

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)

        result = await approve_driver(dto, session=session)

        assert dp.status == DriverStatus.APPROVED
        assert user.role == UserRole.DRIVER

        added_logs = [call[0][0] for call in session.add.call_args_list]
        assert any(isinstance(log, AdminActionLog) for log in added_logs)

    async def test_full_rejection_flow(self):
        session = AsyncMock()

        dp, user = _make_driver_and_user(status=DriverStatus.PENDING_APPROVAL)
        admin_user = _make_admin_user(telegram_id=42)

        admin_result = MagicMock()
        admin_result.scalar_one_or_none.return_value = admin_user
        driver_result = MagicMock()
        driver_result.first.return_value = (dp, user)
        session.execute.side_effect = [admin_result, driver_result]
        session.flush.return_value = None

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(
            driver_id=1, admin_telegram_id=42, rejection_reason="Incomplete docs"
        )

        result = await reject_driver(dto, session=session)

        assert dp.status == DriverStatus.REJECTED

        added_logs = [call[0][0] for call in session.add.call_args_list]
        assert any(isinstance(log, AdminActionLog) for log in added_logs)
        for log in added_logs:
            if isinstance(log, AdminActionLog):
                assert "Incomplete docs" in log.details

    async def test_notification_sent_on_approve(self):
        callback = _make_callback()
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
                mock_notify.assert_awaited_once_with(
                    bot=callback.bot, telegram_id=123456789, approved=True
                )

    async def test_notification_sent_on_reject(self):
        callback = _make_callback()
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
                mock_notify.assert_awaited_once_with(
                    bot=callback.bot, telegram_id=123456789, approved=False
                )

    async def test_admin_portal_lists_pending_drivers(self):
        message = _make_message(text="/verify")
        state = AsyncMock()
        user = _make_admin_user()

        drivers = [MagicMock(driver_id=1, full_name="Alice")]

        with patch(
            "bot.admin.handler.get_pending_drivers",
            new_callable=AsyncMock,
            return_value=(drivers, 1),
        ):
            await cmd_verify_drivers(message, state, user=user)

        message.answer.assert_awaited_once()


def _make_driver_and_user(
    driver_id: int = 1,
    user_id: int = 7,
    status: DriverStatus = DriverStatus.PENDING_APPROVAL,
    telegram_id: int = 123456789,
):
    dp = MagicMock(spec=DriverProfile)
    dp.id = driver_id
    dp.user_id = user_id
    dp.vehicle_type = "sedan"
    dp.plate_number = "ABC-123"
    dp.license_number = "DL-001"
    dp.status = status

    user = MagicMock(spec=User)
    user.id = user_id
    user.telegram_id = telegram_id
    user.full_name = "Jane Doe"
    user.phone_number = "08012345678"
    user.username = "janedoe"
    user.role = UserRole.DRIVER

    return dp, user
