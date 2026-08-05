import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import (
    AccountStatus,
    DriverAvailability,
    DriverStatus,
    UserRole,
)
from bot.core.exceptions import (
    DuplicateResourceError,
    PackitbotError,
    ValidationError,
)
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.driver.schemas import RegisterDriverDTO
from bot.driver.service import (
    get_driver_profile_by_telegram_id,
    register_driver,
    set_driver_availability,
)


class _AsyncSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


VALID_DTO = RegisterDriverDTO(
    telegram_id=123456789,
    full_name="Jane Doe",
    phone_number="08023456789",
    vehicle_type="sedan",
    plate_number="ABC-123DE",
    license_number="DL-987654",
    username="janedoe",
)


class TestRegisterDriver:
    async def test_creates_new_user_and_driver_profile(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value = session

            user_row = MagicMock()
            user_row.scalar_one_or_none.return_value = None
            dp_row = MagicMock()
            dp_row.scalar_one_or_none.return_value = None

            def execute_side_effect(stmt):
                if "User" in str(stmt):
                    return user_row
                return dp_row

            session.execute.side_effect = execute_side_effect
            session.flush.return_value = None

            result = await register_driver(VALID_DTO, session=session)

            assert isinstance(result, DriverProfile)
            assert session.add.call_count == 2

    async def test_returns_existing_pending_profile(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value = session

            existing_user = MagicMock(spec=User)
            existing_user.id = 1
            existing_user.role = UserRole.DRIVER

            existing_dp = MagicMock(spec=DriverProfile)
            existing_dp.status = DriverStatus.PENDING_APPROVAL

            user_row = MagicMock()
            user_row.scalar_one_or_none.return_value = existing_user
            dp_row = MagicMock()
            dp_row.scalar_one_or_none.return_value = existing_dp

            def execute_side_effect(stmt):
                if "User" in str(stmt):
                    return user_row
                return dp_row

            session.execute.side_effect = execute_side_effect
            session.flush.return_value = None

            result = await register_driver(VALID_DTO, session=session)

            assert isinstance(result, DriverProfile)
            assert existing_dp.status == DriverStatus.PENDING_APPROVAL

    async def test_raises_when_already_approved(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value = session

            existing_user = MagicMock(spec=User)
            existing_user.id = 1
            existing_user.role = UserRole.DRIVER

            existing_dp = MagicMock(spec=DriverProfile)
            existing_dp.status = DriverStatus.APPROVED

            user_row = MagicMock()
            user_row.scalar_one_or_none.return_value = existing_user
            dp_row = MagicMock()
            dp_row.scalar_one_or_none.return_value = existing_dp

            def execute_side_effect(stmt):
                if "User" in str(stmt):
                    return user_row
                return dp_row

            session.execute.side_effect = execute_side_effect

            with pytest.raises(PackitbotError, match="already approved"):
                await register_driver(VALID_DTO, session=session)

    async def test_raises_on_duplicate_plate_or_license(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value = session

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

            with pytest.raises(DuplicateResourceError):
                await register_driver(dto, session=session)

    async def test_without_session_creates_own_transaction(self):
        with patch("bot.driver.service.async_session") as mock_session_factory:
            session = AsyncMock()
            ctx = _AsyncSessionCtx(session)
            mock_session_factory.return_value = ctx

            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = None
            session.execute.side_effect = lambda stmt: result_mock
            session.flush.return_value = None
            session.add.return_value = None
            session.commit = AsyncMock(return_value=None)

            result = await register_driver(VALID_DTO)

            assert isinstance(result, DriverProfile)
            session.commit.assert_awaited_once()


class TestGetDriverProfileByTelegramId:
    async def test_returns_profile_when_found(self):
        session = AsyncMock()
        driver = MagicMock(spec=DriverProfile)
        driver.id = 1
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = driver
        session.execute.return_value = result_mock

        result = await get_driver_profile_by_telegram_id(telegram_id=123, session=session)

        assert result is driver

    async def test_returns_none_when_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await get_driver_profile_by_telegram_id(telegram_id=999, session=session)

        assert result is None


class TestSetDriverAvailability:
    async def test_sets_available_when_approved(self):
        session = AsyncMock()
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.OFFLINE

        with patch(
            "bot.driver.service.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            result = await set_driver_availability(
                telegram_id=123, target_availability=DriverAvailability.AVAILABLE, session=session
            )

        assert result.availability == DriverAvailability.AVAILABLE
        session.flush.assert_awaited_once()

    async def test_raises_when_not_approved(self):
        session = AsyncMock()
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.PENDING_APPROVAL
        profile.availability = DriverAvailability.OFFLINE

        with patch(
            "bot.driver.service.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            with pytest.raises(ValidationError, match="Only approved drivers"):
                await set_driver_availability(
                    telegram_id=123, target_availability=DriverAvailability.AVAILABLE, session=session
                )

    async def test_raises_when_busy(self):
        session = AsyncMock()
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.BUSY

        with patch(
            "bot.driver.service.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            with pytest.raises(ValidationError, match="Cannot manually change availability"):
                await set_driver_availability(
                    telegram_id=123, target_availability=DriverAvailability.AVAILABLE, session=session
                )

    async def test_raises_when_setting_busy_manually(self):
        session = AsyncMock()
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.AVAILABLE

        with patch(
            "bot.driver.service.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            with pytest.raises(ValidationError, match="BUSY state is system-managed"):
                await set_driver_availability(
                    telegram_id=123, target_availability=DriverAvailability.BUSY, session=session
                )

    async def test_sets_offline_when_available(self):
        session = AsyncMock()
        profile = MagicMock(spec=DriverProfile)
        profile.status = DriverStatus.APPROVED
        profile.availability = DriverAvailability.AVAILABLE

        with patch(
            "bot.driver.service.get_driver_profile_by_telegram_id",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            result = await set_driver_availability(
                telegram_id=123, target_availability=DriverAvailability.OFFLINE, session=session
            )

        assert result.availability == DriverAvailability.OFFLINE
