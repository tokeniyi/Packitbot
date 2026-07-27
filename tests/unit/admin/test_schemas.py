import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.admin.schemas import DriverApplicationDetailDTO, ReviewDriverDTO
from bot.core.constants.enums import DriverStatus, UserRole


class TestReviewDriverDTO:
    def test_valid_construction(self):
        dto = ReviewDriverDTO(driver_id=1, admin_telegram_id=42)
        assert dto.driver_id == 1
        assert dto.admin_telegram_id == 42
        assert dto.rejection_reason is None

    def test_with_rejection_reason(self):
        dto = ReviewDriverDTO(
            driver_id=1, admin_telegram_id=42, rejection_reason="Incomplete docs"
        )
        assert dto.rejection_reason == "Incomplete docs"


class TestDriverApplicationDetailDTO:
    def test_valid_construction(self):
        dto = DriverApplicationDetailDTO(
            driver_id=1,
            user_id=7,
            telegram_id=123456789,
            full_name="Jane Doe",
            phone_number="08012345678",
            vehicle_type="sedan",
            plate_number="ABC-123DE",
            license_number="DL-987654",
            status=DriverStatus.PENDING_APPROVAL,
            username="janedoe",
        )
        assert dto.driver_id == 1
        assert dto.user_id == 7
        assert dto.full_name == "Jane Doe"
        assert dto.username == "janedoe"
        assert dto.status == DriverStatus.PENDING_APPROVAL

    def test_optional_username_defaults_to_none(self):
        dto = DriverApplicationDetailDTO(
            driver_id=1,
            user_id=7,
            telegram_id=123456789,
            full_name="Jane Doe",
            phone_number="08012345678",
            vehicle_type="sedan",
            plate_number="ABC-123DE",
            license_number="DL-987654",
            status=DriverStatus.PENDING_APPROVAL,
        )
        assert dto.username is None
