import pytest

from bot.core.constants.enums import CancelledBy, RequestStatus
from bot.request.events import (
    FeedbackSubmittedEvent,
    RequestAssignedEvent,
    RequestCancelledEvent,
    RequestCreatedEvent,
    RequestStatusChangedEvent,
)


class TestRequestCreatedEvent:
    def test_valid_construction(self):
        event = RequestCreatedEvent(request_id=1, student_id=42)
        assert event.request_id == 1
        assert event.student_id == 42

    def test_event_is_frozen(self):
        event = RequestCreatedEvent(request_id=1, student_id=42)
        with pytest.raises(AttributeError):
            event.request_id = 2


class TestRequestAssignedEvent:
    def test_valid_construction(self):
        event = RequestAssignedEvent(request_id=1, driver_id=7, admin_id=3)
        assert event.request_id == 1
        assert event.driver_id == 7
        assert event.admin_id == 3


class TestRequestStatusChangedEvent:
    def test_valid_construction_with_old_status(self):
        event = RequestStatusChangedEvent(
            request_id=1,
            old_status=RequestStatus.PENDING,
            new_status=RequestStatus.ASSIGNED,
            actor_id=3,
        )
        assert event.old_status == RequestStatus.PENDING
        assert event.new_status == RequestStatus.ASSIGNED

    def test_valid_construction_with_none_old_status(self):
        event = RequestStatusChangedEvent(
            request_id=1,
            old_status=None,
            new_status=RequestStatus.PENDING,
            actor_id=None,
        )
        assert event.old_status is None
        assert event.actor_id is None


class TestRequestCancelledEvent:
    def test_valid_construction_with_reason(self):
        event = RequestCancelledEvent(
            request_id=1,
            cancelled_by=CancelledBy.STUDENT,
            actor_id=42,
            reason="No longer needed",
        )
        assert event.cancelled_by == CancelledBy.STUDENT
        assert event.reason == "No longer needed"

    def test_optional_reason_defaults_to_none(self):
        event = RequestCancelledEvent(
            request_id=1,
            cancelled_by=CancelledBy.ADMIN,
            actor_id=3,
        )
        assert event.reason is None


class TestFeedbackSubmittedEvent:
    def test_valid_construction(self):
        event = FeedbackSubmittedEvent(
            feedback_id=10,
            request_id=1,
            student_id=42,
            rating=5,
        )
        assert event.feedback_id == 10
        assert event.request_id == 1
        assert event.student_id == 42
        assert event.rating == 5
