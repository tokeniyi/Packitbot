import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.admin.service import (
    approve_driver,
    get_driver_application_detail,
    get_pending_drivers,
    get_stats,
    reject_driver,
)
from bot.admin.schemas import SystemStatsDTO
from bot.core.constants.enums import AdminActionType, DriverStatus, UserRole
from bot.core.exceptions import NotFoundError, ValidationError
from bot.core.models.admin_action_log import AdminActionLog
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.models.user import User


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
    dp.created_at = MagicMock()

    user = MagicMock(spec=User)
    user.id = user_id
    user.telegram_id = telegram_id
    user.full_name = "Jane Doe"
    user.phone_number = "08023456789"
    user.username = "janedoe"
    user.role = UserRole.DRIVER

    return dp, user


class TestGetPendingDrivers:
    async def test_returns_drivers_and_total_pages(self):
        session = AsyncMock()
        dp, user = _make_driver_and_user()

        count_row = MagicMock()
        count_row.scalar.return_value = 1

        driver_row = MagicMock()
        driver_row.all.return_value = [(dp, user)]

        call_count = 0

        def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return count_row
            return driver_row

        session.execute.side_effect = execute_side_effect

        drivers, total_pages = await get_pending_drivers(page=1, session=session)

        assert len(drivers) == 1
        assert drivers[0].driver_id == 1
        assert drivers[0].full_name == "Jane Doe"
        assert total_pages == 1

    async def test_returns_empty_when_no_pending(self):
        session = AsyncMock()
        count_row = MagicMock()
        count_row.scalar.return_value = 0
        session.execute.return_value = count_row

        drivers, total_pages = await get_pending_drivers(page=1, session=session)

        assert drivers == []
        assert total_pages == 1


class TestGetDriverApplicationDetail:
    async def test_returns_detail_dto(self):
        session = AsyncMock()
        dp, user = _make_driver_and_user()
        result_mock = MagicMock()
        result_mock.first.return_value = (dp, user)
        session.execute.return_value = result_mock

        detail = await get_driver_application_detail(driver_id=1, session=session)

        assert detail.driver_id == 1
        assert detail.full_name == "Jane Doe"
        assert detail.vehicle_type == "sedan"

    async def test_raises_when_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(NotFoundError):
            await get_driver_application_detail(driver_id=999, session=session)


class TestApproveDriver:
    async def test_approves_driver_and_logs_action(self):
        session = AsyncMock()
        session.add = MagicMock(return_value=None)
        dp, user = _make_driver_and_user(status=DriverStatus.PENDING_APPROVAL)

        admin_user = MagicMock(spec=User)
        admin_user.id = 99
        admin_user.role = UserRole.ADMIN
        admin_user.telegram_id = 42

        admin_row = MagicMock()
        admin_row.scalar_one_or_none.return_value = admin_user

        driver_row = MagicMock()
        driver_row.first.return_value = (dp, user)

        session.execute.side_effect = [admin_row, driver_row]
        session.flush.return_value = None

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)

        result = await approve_driver(dto, session=session)

        assert dp.status == DriverStatus.APPROVED
        assert user.role == UserRole.DRIVER
        session.add.assert_called_once()
        added_log = session.add.call_args[0][0]
        assert isinstance(added_log, AdminActionLog)
        assert added_log.action_type == AdminActionType.APPROVE_DRIVER

    async def test_raises_for_non_admin(self):
        session = AsyncMock()
        non_admin = MagicMock(spec=User)
        non_admin.role = UserRole.STUDENT
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = non_admin
        session.execute.return_value = result_mock

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)

        with pytest.raises(ValidationError, match="Admin permission required"):
            await approve_driver(dto, session=session)

    async def test_raises_when_already_approved(self):
        session = AsyncMock()
        dp, user = _make_driver_and_user(status=DriverStatus.APPROVED)
        admin_user = MagicMock(spec=User)
        admin_user.role = UserRole.ADMIN
        admin_user.telegram_id = 42

        admin_row = MagicMock()
        admin_row.scalar_one_or_none.return_value = admin_user
        driver_row = MagicMock()
        driver_row.first.return_value = (dp, user)

        session.execute.side_effect = [admin_row, driver_row]

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)

        with pytest.raises(ValidationError, match="already approved"):
            await approve_driver(dto, session=session)


class TestRejectDriver:
    async def test_rejects_driver_and_logs_action(self):
        session = AsyncMock()
        session.add = MagicMock(return_value=None)
        dp, user = _make_driver_and_user(status=DriverStatus.PENDING_APPROVAL)

        admin_user = MagicMock(spec=User)
        admin_user.id = 99
        admin_user.role = UserRole.ADMIN
        admin_user.telegram_id = 42

        admin_row = MagicMock()
        admin_row.scalar_one_or_none.return_value = admin_user
        driver_row = MagicMock()
        driver_row.first.return_value = (dp, user)

        session.execute.side_effect = [admin_row, driver_row]
        session.flush.return_value = None

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(
            driver_id=1, admin_telegram_id=42, rejection_reason="Incomplete docs"
        )

        result = await reject_driver(dto, session=session)

        assert dp.status == DriverStatus.REJECTED
        session.add.assert_called_once()
        added_logs = [call[0][0] for call in session.add.call_args_list]
        assert any(isinstance(log, AdminActionLog) for log in added_logs)
        for log in added_logs:
            if isinstance(log, AdminActionLog):
                assert "Incomplete docs" in log.details

    async def test_raises_for_non_admin(self):
        session = AsyncMock()
        non_admin = MagicMock(spec=User)
        non_admin.role = UserRole.STUDENT
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = non_admin
        session.execute.return_value = result_mock

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)

        with pytest.raises(ValidationError, match="Admin permission required"):
            await reject_driver(dto, session=session)

    async def test_raises_when_driver_not_found(self):
        session = AsyncMock()
        admin_user = MagicMock(spec=User)
        admin_user.role = UserRole.ADMIN
        admin_user.telegram_id = 42

        admin_row = MagicMock()
        admin_row.scalar_one_or_none.return_value = admin_user
        driver_row = MagicMock()
        driver_row.first.return_value = None

        session.execute.side_effect = [admin_row, driver_row]

        from bot.admin.schemas import ReviewDriverDTO
        dto = ReviewDriverDTO(driver_id=999, admin_telegram_id=42)

        with pytest.raises(NotFoundError):
            await reject_driver(dto, session=session)


class TestGetStats:
    async def test_returns_stats_dto(self):
        session = AsyncMock()
        scalar_values = [
            100,  # total_requests
            10,  # pending_requests
            5,  # assigned_requests
            8,  # accepted_requests
            3,  # en_route_requests
            2,  # picked_up_requests
            4,  # in_transit_requests
            60,  # delivered_requests
            5,  # cancelled_requests
            2,  # failed_requests
            1,  # rejected_by_driver_requests
            200,  # total_users
            150,  # total_students
            45,  # total_drivers
            5,  # total_admins
            40,  # approved_drivers
            3,  # pending_drivers
            1,  # rejected_drivers
            1,  # suspended_drivers
            80,  # total_feedbacks
            4.5,  # avg_rating
        ]
        result_mocks = [MagicMock(scalar=MagicMock(return_value=v)) for v in scalar_values]
        session.execute.side_effect = result_mocks

        stats = await get_stats(session=session)

        assert isinstance(stats, SystemStatsDTO)
        assert stats.total_requests == 100
        assert stats.pending_requests == 10
        assert stats.delivered_requests == 60
        assert stats.total_users == 200
        assert stats.total_students == 150
        assert stats.total_drivers == 45
        assert stats.total_admins == 5
        assert stats.approved_drivers == 40
        assert stats.pending_drivers == 3
        assert stats.rejected_drivers == 1
        assert stats.suspended_drivers == 1
        assert stats.total_feedbacks == 80
        assert stats.avg_rating == 4.5

    async def test_returns_zero_counts_when_empty(self):
        session = AsyncMock()
        zero = MagicMock(scalar=MagicMock(return_value=0))
        none_mock = MagicMock(scalar=MagicMock(return_value=None))
        session.execute.side_effect = [
            zero, zero, zero, zero, zero, zero, zero, zero, zero, zero, zero,
            zero, zero, zero, zero,
            zero, zero, zero, zero,
            zero,
            none_mock,
        ]

        stats = await get_stats(session=session)

        assert stats.total_requests == 0
        assert stats.total_users == 0
        assert stats.avg_rating is None
