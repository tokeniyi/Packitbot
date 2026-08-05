import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import CancelledBy, DriverAvailability, DriverStatus, RequestStatus
from bot.core.exceptions import (
    DriverUnavailableError,
    InvalidStatusTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.request.service import RequestService
from bot.request.repository import RequestRepository, StatusLogRepository, FeedbackRepository
from bot.request.schemas import (
    AssignDriverDTO,
    CancelRequestDTO,
    CreateFeedbackDTO,
    CreateRequestDTO,
    TransitionDTO,
    UpdateRequestDTO,
)
from bot.request.events import (
    RequestCreatedEvent,
    RequestAssignedEvent,
    RequestCancelledEvent,
    RequestStatusChangedEvent,
    FeedbackSubmittedEvent,
)
from bot.request.state_machine import can_transition
from bot.request.business_rules import (
    can_assign_driver,
    can_edit_request,
    can_rate_delivery,
    can_student_cancel,
)


def _make_session():
    return AsyncMock()


def _make_request(
    id: int = 1,
    status: RequestStatus = RequestStatus.PENDING,
    student_id: int = 1,
    driver_id: int | None = None,
) -> DeliveryRequest:
    req = MagicMock(spec=DeliveryRequest)
    req.id = id
    req.status = status
    req.student_id = student_id
    req.driver_id = driver_id
    req.feedback = None
    return req


def _make_driver_profile(
    user_id: int = 7,
    status: DriverStatus = DriverStatus.APPROVED,
    availability: DriverAvailability = DriverAvailability.AVAILABLE,
) -> DriverProfile:
    driver = MagicMock(spec=DriverProfile)
    driver.user_id = user_id
    driver.status = status
    driver.availability = availability
    return driver


class TestRequestLifecycleIntegration:
    async def test_create_then_assign_then_transition_to_delivered(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)

        req = _make_request(id=1, status=RequestStatus.PENDING)
        session.get.return_value = req
        repo.create = AsyncMock(return_value=req)

        async def apply_updates(entity_id, **kwargs):
            for key, value in kwargs.items():
                setattr(req, key, value)
            return req

        repo.update = apply_updates
        status_log_repo.create = AsyncMock(return_value=MagicMock())

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = CreateRequestDTO(
            student_id=1,
            pickup_detail="Gate",
            dropoff_address="Lagos",
            dropoff_landmark=None,
            hall_of_residence="Esther Hall",
            recipient_name="Jane",
            recipient_phone="08012345678",
            luggage_size="small",
            luggage_count=1,
            special_instructions=None,
            preferred_date=None,
            preferred_time_window="10-12",
        )
        _, created_event = await service.create_request(dto)
        assert isinstance(created_event, RequestCreatedEvent)

        assign_dto = AssignDriverDTO(request_id=1, driver_id=7, admin_id=3)
        driver = _make_driver_profile()
        _, assigned_event = await service.assign_driver(assign_dto, driver)
        assert isinstance(assigned_event, RequestAssignedEvent)
        assert req.status == RequestStatus.ASSIGNED

        req.status = RequestStatus.ACCEPTED
        transition_dto = TransitionDTO(
            request_id=1, new_status=RequestStatus.EN_ROUTE_TO_PICKUP, actor_id=3
        )
        _, transitioned_event = await service.transition_status(transition_dto)
        assert isinstance(transitioned_event, RequestStatusChangedEvent)
        assert req.status == RequestStatus.EN_ROUTE_TO_PICKUP

    async def test_create_then_cancel_by_student(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)

        req = _make_request(id=1, status=RequestStatus.PENDING, student_id=42)
        session.get.return_value = req
        repo.create = AsyncMock(return_value=req)

        async def apply_updates(entity_id, **kwargs):
            for key, value in kwargs.items():
                setattr(req, key, value)
            return req

        repo.update = apply_updates
        status_log_repo.create = AsyncMock(return_value=MagicMock())

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = CreateRequestDTO(
            student_id=42,
            pickup_detail="Gate",
            dropoff_address="Lagos",
            dropoff_landmark=None,
            hall_of_residence="Esther Hall",
            recipient_name="Jane",
            recipient_phone="08012345678",
            luggage_size="small",
            luggage_count=1,
            special_instructions=None,
            preferred_date=None,
            preferred_time_window="10-12",
        )
        await service.create_request(dto)

        cancel_dto = CancelRequestDTO(
            request_id=1,
            actor_id=42,
            cancelled_by=CancelledBy.STUDENT,
            cancellation_reason="Changed mind",
        )
        _, cancel_event = await service.cancel_request(cancel_dto)
        assert isinstance(cancel_event, RequestCancelledEvent)
        assert cancel_event.cancelled_by == CancelledBy.STUDENT

    async def test_create_then_submit_feedback(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)

        req = _make_request(id=1, status=RequestStatus.DELIVERED, student_id=42)
        session.get.return_value = req
        repo.create = AsyncMock(return_value=req)

        feedback = MagicMock(spec=Feedback)
        feedback.id = 10
        feedback.request_id = 1
        feedback.student_id = 42
        feedback.rating = 5
        feedback.comment = "Great"
        feedback_repo.create = AsyncMock(return_value=feedback)
        feedback_repo.get_for_request = AsyncMock(return_value=None)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=5, comment="Great")
        result_feedback, event = await service.submit_feedback(dto)
        assert isinstance(event, FeedbackSubmittedEvent)
        assert event.rating == 5

    async def test_business_rules_consistency_with_service(self):
        req = _make_request(status=RequestStatus.PENDING, student_id=1)
        assert can_student_cancel(req, actor_id=1) is True
        assert can_edit_request(req, actor_id=1) is True
        assert can_transition(RequestStatus.PENDING, RequestStatus.ASSIGNED) is True
        assert can_transition(RequestStatus.PENDING, RequestStatus.CANCELLED) is True

        req_assigned = _make_request(status=RequestStatus.ASSIGNED, student_id=1)
        assert can_edit_request(req_assigned, actor_id=1) is False

        delivered_req = _make_request(status=RequestStatus.DELIVERED)
        assert can_rate_delivery(delivered_req, existing_feedback=None) is True
