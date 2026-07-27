import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import DriverAvailability, DriverStatus, UserRole
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.driver.schemas import RegisterDriverDTO


class TestRegisterDriverDTO:
    def test_valid_construction(self):
        dto = RegisterDriverDTO(
            telegram_id=123456789,
            full_name="Jane Doe",
            phone_number="08012345678",
            vehicle_type="sedan",
            plate_number="ABC-123DE",
            license_number="DL-987654",
            username="janedoe",
        )
        assert dto.telegram_id == 123456789
        assert dto.full_name == "Jane Doe"
        assert dto.phone_number == "08012345678"
        assert dto.vehicle_type == "sedan"
        assert dto.plate_number == "ABC-123DE"
        assert dto.license_number == "DL-987654"
        assert dto.username == "janedoe"

    def test_optional_username_defaults_to_none(self):
        dto = RegisterDriverDTO(
            telegram_id=123456789,
            full_name="Jane Doe",
            phone_number="08012345678",
            vehicle_type="sedan",
            plate_number="ABC-123DE",
            license_number="DL-987654",
        )
        assert dto.username is None

    def test_all_fields_required_except_username(self):
        with pytest.raises(TypeError):
            RegisterDriverDTO(
                telegram_id=123456789,
                full_name="Jane Doe",
            )
