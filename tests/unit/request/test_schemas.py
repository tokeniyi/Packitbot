import pytest
from datetime import date

from bot.core.constants.enums import (
    CancelledBy,
    LuggageSize,
    RequestStatus,
)
from bot.request.schemas import (
    CancelRequestDTO,
    CreateFeedbackDTO,
    CreateRequestDTO,
    TransitionDTO,
    UpdateRequestDTO,
    AssignDriverDTO,
)


class TestCreateRequestDTO:
    def test_valid_construction(self):
        dto = CreateRequestDTO(
            student_id=1,
            pickup_detail="Covenant University Gate",
            dropoff_address="123 Lagos Street",
            dropoff_landmark=None,
            hall_of_residence="Esther Hall",
            recipient_name="Jane Doe",
            recipient_phone="08012345678",
            luggage_size=LuggageSize.SMALL,
            luggage_count=1,
            special_instructions=None,
            preferred_date=date(2025, 8, 15),
            preferred_time_window="10:00-12:00",
        )
        assert dto.student_id == 1
        assert dto.luggage_size == LuggageSize.SMALL
        assert dto.hall_of_residence == "Esther Hall"


class TestUpdateRequestDTO:
    def test_valid_construction(self):
        dto = UpdateRequestDTO(
            request_id=42,
            actor_id=1,
            changed_fields={"pickup_detail": "New address"},
        )
        assert dto.request_id == 42
        assert dto.actor_id == 1
        assert dto.changed_fields == {"pickup_detail": "New address"}


class TestAssignDriverDTO:
    def test_valid_construction(self):
        dto = AssignDriverDTO(
            request_id=42,
            driver_id=7,
            admin_id=1,
        )
        assert dto.request_id == 42
        assert dto.driver_id == 7
        assert dto.admin_id == 1


class TestTransitionDTO:
    def test_valid_construction(self):
        dto = TransitionDTO(
            request_id=42,
            new_status=RequestStatus.DELIVERED,
            actor_id=3,
            note="Package left at door",
        )
        assert dto.request_id == 42
        assert dto.new_status == RequestStatus.DELIVERED
        assert dto.actor_id == 3
        assert dto.note == "Package left at door"

    def test_optional_note_defaults_to_none(self):
        dto = TransitionDTO(
            request_id=42,
            new_status=RequestStatus.CANCELLED,
            actor_id=3,
        )
        assert dto.note is None


class TestCreateRequestDTOWithHall:
    def test_valid_construction_with_hall(self):
        dto = CreateRequestDTO(
            student_id=1,
            pickup_detail="Covenant University Gate",
            dropoff_address="123 Lagos Street",
            dropoff_landmark=None,
            hall_of_residence="Esther Hall",
            recipient_name="Jane Doe",
            recipient_phone="08012345678",
            luggage_size=LuggageSize.SMALL,
            luggage_count=1,
            special_instructions=None,
            preferred_date=date(2025, 8, 15),
            preferred_time_window="10:00-12:00",
        )
        assert dto.hall_of_residence == "Esther Hall"

    def test_missing_hall_raises_type_error(self):
        with pytest.raises(TypeError):
            CreateRequestDTO(
                student_id=1,
                pickup_detail="Gate",
                dropoff_address="Lagos",
                dropoff_landmark=None,
                recipient_name="Jane",
                recipient_phone="08012345678",
                luggage_size=LuggageSize.SMALL,
                luggage_count=1,
                special_instructions=None,
                preferred_date=date(2025, 8, 15),
                preferred_time_window="10:00-12:00",
            )


class TestUpdateRequestDTOWithTypedFields:
    def test_changed_fields_accepts_any_string_key(self):
        dto = UpdateRequestDTO(
            request_id=42,
            actor_id=1,
            changed_fields={"pickup_detail": "New address", "special_instructions": "Ring bell"},
        )
        assert dto.changed_fields["pickup_detail"] == "New address"


class TestCancelRequestDTO:
    def test_valid_construction(self):
        dto = CancelRequestDTO(
            request_id=42,
            actor_id=1,
            cancelled_by=CancelledBy.STUDENT,
            cancellation_reason="No longer needed",
        )
        assert dto.request_id == 42
        assert dto.actor_id == 1
        assert dto.cancelled_by == CancelledBy.STUDENT
        assert dto.cancellation_reason == "No longer needed"

    def test_optional_reason_defaults_to_none(self):
        dto = CancelRequestDTO(
            request_id=42,
            actor_id=1,
            cancelled_by=CancelledBy.ADMIN,
        )
        assert dto.cancellation_reason is None


class TestCreateFeedbackDTO:
    def test_valid_construction(self):
        dto = CreateFeedbackDTO(
            request_id=42,
            student_id=1,
            rating=5,
            comment="Excellent service",
        )
        assert dto.request_id == 42
        assert dto.student_id == 1
        assert dto.rating == 5
        assert dto.comment == "Excellent service"

    def test_optional_comment_defaults_to_none(self):
        dto = CreateFeedbackDTO(
            request_id=42,
            student_id=1,
            rating=4,
        )
        assert dto.comment is None