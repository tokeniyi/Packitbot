import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock, patch

from bot.admin.service import (
    add_authorized_driver,
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
from bot.core.models.authorized_driver import AuthorizedDriver
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
        dto = ReviewDriverDTO(driver_id=1, admin_user_id=42)

        result = await approve_driver(session=session, dto=dto)

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
        dto = ReviewDriverDTO(driver_id=1, admin_user_id=42)

        with pytest.raises(ValidationError, match="Admin permission required"):
            await approve_driver(session=session, dto=dto)

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
        dto = ReviewDriverDTO(driver_id=1, admin_user_id=42)

        with pytest.raises(ValidationError, match="already approved"):
            await approve_driver(session=session, dto=dto)


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
            driver_id=1, admin_user_id=42, rejection_reason="Incomplete docs"
        )

        result = await reject_driver(session=session, dto=dto)

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
        dto = ReviewDriverDTO(driver_id=1, admin_user_id=42)

        with pytest.raises(ValidationError, match="Admin permission required"):
            await reject_driver(session=session, dto=dto)

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
        dto = ReviewDriverDTO(driver_id=999, admin_user_id=42)

        with pytest.raises(NotFoundError):
            await reject_driver(session=session, dto=dto)


class TestGetStats:
    async def test_returns_stats_dto(self):
        session = AsyncMock()
        # 11 request-count columns, 4 user-count columns, 5 driver-count columns,
        # 2 feedback-count columns, then duration query uses .all()
        result_mocks = [
            MagicMock(one=MagicMock(return_value=(100, 10, 5, 8, 3, 2, 4, 60, 5, 2, 1))),
            MagicMock(one=MagicMock(return_value=(200, 150, 45, 5))),
            MagicMock(one=MagicMock(return_value=(40, 35, 3, 1, 1))),
            MagicMock(one=MagicMock(return_value=(80, 4.5))),
            MagicMock(all=MagicMock(return_value=[])),
        ]
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
        result_mocks = [
            MagicMock(one=MagicMock(return_value=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))),
            MagicMock(one=MagicMock(return_value=(0, 0, 0, 0))),
            MagicMock(one=MagicMock(return_value=(0, 0, 0, 0, 0))),
            MagicMock(one=MagicMock(return_value=(0, None))),
            MagicMock(all=MagicMock(return_value=[])),
        ]
        session.execute.side_effect = result_mocks

        stats = await get_stats(session=session)

        assert stats.total_requests == 0
        assert stats.total_users == 0
        assert stats.avg_rating is None


def _scalar_result(value):
    """Build a mock ``session.execute()`` result returning ``value``."""
    return MagicMock(scalar_one_or_none=MagicMock(return_value=value))


def _session():
    """Async session mock whose sync ``add`` is a MagicMock.

    ``AsyncSession.add`` is synchronous, so leaving it on ``AsyncMock`` makes
    it return an un-awaited coroutine and emits spurious RuntimeWarnings.
    """
    session = AsyncMock()
    session.add = MagicMock()
    return session


class TestAddAuthorizedDriver:
    """Regression tests for backlog item #1.

    ``add_authorized_driver`` is called from ``cmd_add_driver`` with
    ``admin_user_id=user.id`` (the internal ``users.id`` PK), but it used to
    filter on ``User.telegram_id``.  Those columns never matched, so every call
    raised ``ValidationError("Admin permission required.")`` and nobody could
    ever be authorized as a driver — a dead end in the whole onboarding funnel.

    The tests below assert the *compiled SQL column*, not just behaviour, so a
    future refactor cannot silently reintroduce the mismatch.
    """

    def _admin(self, user_id=42, telegram_id=999_000_111):
        admin = MagicMock(spec=User)
        admin.id = user_id
        admin.telegram_id = telegram_id
        admin.role = UserRole.ADMIN
        return admin

    async def test_looks_up_admin_by_users_id_not_telegram_id(self):
        """The admin lookup must filter on ``users.id``."""
        session = _session()
        session.execute.side_effect = [
            _scalar_result(self._admin()),   # admin lookup
            _scalar_result(None),            # already-authorized check
        ]

        await add_authorized_driver(
            session=session, telegram_id=123456789, admin_user_id=42
        )

        admin_stmt = session.execute.call_args_list[0].args[0]
        where_clause = admin_stmt.whereclause
        compared_columns = {c.name for c in where_clause.get_children() if hasattr(c, "name")}

        # ``users.id`` is the correct lookup key.
        assert "id" in compared_columns
        # ``users.telegram_id`` must NOT be used — it is what caused the bug.
        assert "telegram_id" not in compared_columns

    async def test_succeeds_for_admin_authorized_by_users_id(self):
        """Happy path: an admin found by ``users.id`` is authorized."""
        session = _session()
        session.execute.side_effect = [
            _scalar_result(self._admin()),
            _scalar_result(None),
        ]

        added = await add_authorized_driver(
            session=session, telegram_id=123456789, admin_user_id=42
        )

        assert added is True
        session.add.assert_called()

    async def test_records_added_by_admin_id_from_users_id(self):
        """The audit rows must reference the admin's ``users.id``."""
        session = _session()
        session.execute.side_effect = [
            _scalar_result(self._admin()),
            _scalar_result(None),
        ]

        await add_authorized_driver(
            session=session, telegram_id=123456789, admin_user_id=42
        )

        added = [
            call.args[0] for call in session.add.call_args_list
            if isinstance(call.args[0], AuthorizedDriver)
        ]
        assert added, "expected an AuthorizedDriver row to be added"
        assert added[0].added_by_admin_id == 42
        assert added[0].telegram_id == 123456789

    async def test_raises_when_caller_is_not_an_admin(self):
        """A non-admin caller is still rejected."""
        session = _session()
        non_admin = self._admin()
        non_admin.role = UserRole.STUDENT
        session.execute.side_effect = [_scalar_result(non_admin)]

        with pytest.raises(ValidationError, match="Admin permission required"):
            await add_authorized_driver(
                session=session, telegram_id=123456789, admin_user_id=42
            )

    async def test_raises_when_admin_lookup_finds_no_user(self):
        """An unknown admin id is rejected rather than silently allowed."""
        session = _session()
        session.execute.side_effect = [_scalar_result(None)]

        with pytest.raises(ValidationError, match="Admin permission required"):
            await add_authorized_driver(
                session=session, telegram_id=123456789, admin_user_id=404
            )

    async def test_returns_false_when_already_authorized(self):
        """Re-adding an existing Telegram ID is a no-op returning ``False``."""
        session = _session()
        session.execute.side_effect = [
            _scalar_result(self._admin()),
            _scalar_result(MagicMock(spec=AuthorizedDriver)),
        ]

        added = await add_authorized_driver(
            session=session, telegram_id=123456789, admin_user_id=42
        )

        assert added is False
        session.add.assert_not_called()


class TestAddAuthorizedDriverAgainstRealDatabase:
    """End-to-end proof for backlog item #1 against a real SQL database.

    The mocked tests above pin the *column* but cannot reproduce the actual
    lookup, because a mock returns the admin regardless of the filter.  This
    tier inserts a real admin row whose ``users.id`` differs from its
    ``telegram_id`` and asserts the query genuinely finds them — which it could
    not do before the fix.
    """

    async def test_admin_is_found_by_users_id_against_real_db(self, db_session):
        admin = User(
            telegram_id=555_000_222,
            full_name="Chief Admin",
            role=UserRole.ADMIN,
        )
        db_session.add(admin)
        await db_session.flush()
        # Guard: the two identifiers must differ for this test to be meaningful.
        assert admin.telegram_id != admin.id

        added = await add_authorized_driver(
            session=db_session,
            telegram_id=123456789,
            admin_user_id=admin.id,
        )

        assert added is True
        await db_session.flush()

        row = (
            await db_session.execute(
                select(AuthorizedDriver).where(
                    AuthorizedDriver.telegram_id == 123456789
                )
            )
        ).scalar_one()
        assert row.added_by_admin_id == admin.id

        log = (
            await db_session.execute(
                select(AdminActionLog).where(
                    AdminActionLog.admin_id == admin.id,
                    AdminActionLog.action_type == AdminActionType.AUTHORIZE_DRIVER,
                )
            )
        ).scalar_one()
        assert log.target_user_id is None
