import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.core.constants.enums import DriverAvailability, DriverStatus
from bot.driver.repository import DriverRepository


def _make_driver_profile(
    id: int = 1,
    user_id: int = 1,
    vehicle_type: str = "sedan",
    plate_number: str = "ABC-123",
    license_number: str = "DL-001",
    status: DriverStatus = DriverStatus.PENDING_APPROVAL,
    availability: DriverAvailability = DriverAvailability.OFFLINE,
):
    dp = MagicMock()
    dp.id = id
    dp.user_id = user_id
    dp.vehicle_type = vehicle_type
    dp.plate_number = plate_number
    dp.license_number = license_number
    dp.status = status
    dp.availability = availability
    return dp


class TestDriverRepositoryGetByUserId:
    async def test_returns_driver_when_found(self):
        session = AsyncMock()
        driver = _make_driver_profile(user_id=7)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = driver
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_user_id(user_id=7)

        assert result is driver
        assert result.user_id == 7

    async def test_returns_none_when_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_user_id(user_id=999)

        assert result is None


class TestDriverRepositoryGetByPlateNumber:
    async def test_returns_driver_by_plate(self):
        session = AsyncMock()
        driver = _make_driver_profile(plate_number="ABC-123")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = driver
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_plate_number(plate_number="ABC-123")

        assert result is driver
        assert result.plate_number == "ABC-123"

    async def test_returns_none_when_plate_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_plate_number(plate_number="ZZZ-999")

        assert result is None


class TestDriverRepositoryGetByLicenseNumber:
    async def test_returns_driver_by_license(self):
        session = AsyncMock()
        driver = _make_driver_profile(license_number="DL-001")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = driver
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_license_number(license_number="DL-001")

        assert result is driver
        assert result.license_number == "DL-001"

    async def test_returns_none_when_license_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DriverRepository(session)
        result = await repo.get_by_license_number(license_number="DL-XXX")

        assert result is None
