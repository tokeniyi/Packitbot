import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.core.constants.enums import CancelledBy, DriverAvailability, DriverStatus, RequestStatus
from bot.core.exceptions import (
    DriverUnavailableError,
    InvalidStatusTransitionError,
    NotFoundError,
    PackitbotError,
    PermissionDeniedError,
    ValidationError,
)
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.models.status_log import RequestStatusLog
from bot.request.events import (
    FeedbackSubmittedEvent,
    RequestAssignedEvent,
    RequestCancelledEvent,
    RequestCreatedEvent,
    RequestStatusChangedEvent,
)
from bot.request.repository import (
    FeedbackRepository,
    RequestRepository,
    StatusLogRepository,
)
from bot.request.schemas import (
    AssignDriverDTO,
    CancelRequestDTO,
    CreateFeedbackDTO,
    CreateRequestDTO,
    TransitionDTO,
    UpdateRequestDTO,
)
from bot.request.service import RequestService
from bot.request.state_machine import can_transition


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


class TestRequestServiceCreateRequest:
    async def test_create_request_returns_event(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        session.add.return_value = None

        request = _make_request(id=1, status=RequestStatus.PENDING)
        session.get.return_value = None
        repo.create = AsyncMock(return_value=request)
        status_log_repo.create = AsyncMock(return_value=MagicMock(spec=RequestStatusLog))

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

        result_request, event = await service.create_request(dto)

        assert result_request.id == 1
        assert isinstance(event, RequestCreatedEvent)
        assert event.request_id == 1
        assert event.student_id == 1

    async def test_create_request_handles_integrity_error(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        repo.create = AsyncMock(side_effect=ValidationError("FK violation"))

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

        with pytest.raises(ValidationError):
            await service.create_request(dto)


class TestRequestServiceUpdateRequest:
    async def test_update_request_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=42, status=RequestStatus.PENDING, student_id=1)
        session.get.return_value = req
        repo.update = AsyncMock(return_value=req)

        service = RequestService(session)
        service.request_repo = repo

        dto = UpdateRequestDTO(request_id=42, actor_id=1, changed_fields={"pickup_detail": "New gate"})
        result = await service.update_request(dto)

        assert result.id == 42
        repo.update.assert_called_once_with(42, pickup_detail="New gate")

    async def test_update_request_not_found(self):
        session = _make_session()
        repo = RequestRepository(session)
        session.get.return_value = None

        service = RequestService(session)
        service.request_repo = repo

        dto = UpdateRequestDTO(request_id=42, actor_id=1, changed_fields={"pickup_detail": "New gate"})
        with pytest.raises(NotFoundError):
            await service.update_request(dto)

    async def test_update_request_permission_denied_wrong_actor(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=42, status=RequestStatus.PENDING, student_id=1)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = UpdateRequestDTO(request_id=42, actor_id=999, changed_fields={"pickup_detail": "New gate"})
        with pytest.raises(PermissionDeniedError):
            await service.update_request(dto)

    async def test_update_request_permission_denied_not_pending(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=42, status=RequestStatus.ASSIGNED, student_id=1)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = UpdateRequestDTO(request_id=42, actor_id=1, changed_fields={"pickup_detail": "New gate"})
        with pytest.raises(PermissionDeniedError):
            await service.update_request(dto)


class TestRequestServiceAssignDriver:
    async def test_assign_driver_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        req = _make_request(id=1, status=RequestStatus.PENDING, student_id=1)
        session.get.return_value = req
        repo.update = AsyncMock(return_value=req)
        status_log_repo.create = AsyncMock(return_value=MagicMock(spec=RequestStatusLog))

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = AssignDriverDTO(request_id=1, driver_id=7, admin_id=3)
        driver = _make_driver_profile(user_id=7)
        result_req, event = await service.assign_driver(dto, driver)

        assert result_req.id == 1
        assert isinstance(event, RequestAssignedEvent)
        assert event.driver_id == 7
        assert event.admin_id == 3

    async def test_assign_driver_not_found(self):
        session = _make_session()
        repo = RequestRepository(session)
        session.get.return_value = None

        service = RequestService(session)
        service.request_repo = repo

        dto = AssignDriverDTO(request_id=1, driver_id=7, admin_id=3)
        driver = _make_driver_profile()
        with pytest.raises(NotFoundError):
            await service.assign_driver(dto, driver)

    async def test_assign_driver_driver_unavailable(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=1)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = AssignDriverDTO(request_id=1, driver_id=7, admin_id=3)
        driver = _make_driver_profile(status=DriverStatus.PENDING_APPROVAL)
        with pytest.raises(DriverUnavailableError):
            await service.assign_driver(dto, driver)

    async def test_assign_driver_invalid_transition(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = AssignDriverDTO(request_id=1, driver_id=7, admin_id=3)
        driver = _make_driver_profile()
        with pytest.raises(InvalidStatusTransitionError):
            await service.assign_driver(dto, driver)


class TestRequestServiceTransitionStatus:
    async def test_transition_status_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        req = _make_request(id=1, status=RequestStatus.ASSIGNED)
        session.get.return_value = req
        repo.update = AsyncMock(return_value=req)
        status_log_repo.create = AsyncMock(return_value=MagicMock(spec=RequestStatusLog))

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = TransitionDTO(
            request_id=1,
            new_status=RequestStatus.ACCEPTED,
            actor_id=3,
            note="Accepted by driver",
        )
        result_req, event = await service.transition_status(dto)

        assert result_req.id == 1
        assert isinstance(event, RequestStatusChangedEvent)
        assert event.new_status == RequestStatus.ACCEPTED
        repo.update.assert_called_once_with(
            1, status=RequestStatus.ACCEPTED
        )

    async def test_transition_status_not_found(self):
        session = _make_session()
        repo = RequestRepository(session)
        session.get.return_value = None

        service = RequestService(session)
        service.request_repo = repo

        dto = TransitionDTO(request_id=1, new_status=RequestStatus.CANCELLED, actor_id=3)
        with pytest.raises(NotFoundError):
            await service.transition_status(dto)

    async def test_transition_status_invalid_transition(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=1, status=RequestStatus.PENDING)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = TransitionDTO(request_id=1, new_status=RequestStatus.DELIVERED, actor_id=3)
        with pytest.raises(InvalidStatusTransitionError):
            await service.transition_status(dto)


class TestRequestServiceCancelRequest:
    async def test_cancel_request_by_student_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        req = _make_request(id=1, status=RequestStatus.PENDING, student_id=42)
        session.get.return_value = req

        async def _apply_updates(entity_id, **kwargs):
            for key, value in kwargs.items():
                setattr(req, key, value)
            return req

        repo.update = _apply_updates
        status_log_repo.create = AsyncMock(return_value=MagicMock(spec=RequestStatusLog))

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = CancelRequestDTO(
            request_id=1,
            actor_id=42,
            cancelled_by=CancelledBy.STUDENT,
            cancellation_reason="Need to change date",
        )
        result_req, event = await service.cancel_request(dto)

        assert result_req.status == RequestStatus.CANCELLED
        assert isinstance(event, RequestCancelledEvent)
        assert event.cancelled_by == CancelledBy.STUDENT

    async def test_cancel_request_by_student_permission_denied(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=1, status=RequestStatus.EN_ROUTE_TO_PICKUP, student_id=42)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = CancelRequestDTO(
            request_id=1,
            actor_id=42,
            cancelled_by=CancelledBy.STUDENT,
        )
        with pytest.raises(PermissionDeniedError):
            await service.cancel_request(dto)

    async def test_cancel_request_by_admin_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        status_log_repo = StatusLogRepository(session)
        req = _make_request(id=1, status=RequestStatus.ASSIGNED, student_id=42)
        session.get.return_value = req

        async def _apply_updates(entity_id, **kwargs):
            for key, value in kwargs.items():
                setattr(req, key, value)
            return req

        repo.update = _apply_updates
        status_log_repo.create = AsyncMock(return_value=MagicMock(spec=RequestStatusLog))

        service = RequestService(session)
        service.request_repo = repo
        service.status_log_repo = status_log_repo

        dto = CancelRequestDTO(
            request_id=1,
            actor_id=3,
            cancelled_by=CancelledBy.ADMIN,
            cancellation_reason="Driver unavailable",
        )
        result_req, event = await service.cancel_request(dto)

        assert result_req.status == RequestStatus.CANCELLED
        assert event.cancelled_by == CancelledBy.ADMIN

    async def test_cancel_request_not_found(self):
        session = _make_session()
        repo = RequestRepository(session)
        session.get.return_value = None

        service = RequestService(session)
        service.request_repo = repo

        dto = CancelRequestDTO(request_id=1, actor_id=3, cancelled_by=CancelledBy.ADMIN)
        with pytest.raises(NotFoundError):
            await service.cancel_request(dto)

    async def test_cancel_request_invalid_transition(self):
        session = _make_session()
        repo = RequestRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED, student_id=42)
        session.get.return_value = req

        service = RequestService(session)
        service.request_repo = repo

        dto = CancelRequestDTO(request_id=1, actor_id=3, cancelled_by=CancelledBy.ADMIN)
        with pytest.raises(InvalidStatusTransitionError):
            await service.cancel_request(dto)


class TestRequestServiceSubmitFeedback:
    async def test_submit_feedback_success(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED, student_id=42)
        session.get.return_value = req
        feedback_repo.get_for_request = AsyncMock(return_value=None)

        feedback = MagicMock(spec=Feedback)
        feedback.id = 10
        feedback.request_id = 1
        feedback.student_id = 42
        feedback.rating = 5
        feedback.comment = "Great"
        feedback_repo.create = AsyncMock(return_value=feedback)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=5, comment="Great")
        result_feedback, event = await service.submit_feedback(dto)

        assert result_feedback.id == 10
        assert isinstance(event, FeedbackSubmittedEvent)
        assert event.rating == 5

    async def test_submit_feedback_not_found(self):
        session = _make_session()
        repo = RequestRepository(session)
        session.get.return_value = None

        service = RequestService(session)
        service.request_repo = repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=5)
        with pytest.raises(NotFoundError):
            await service.submit_feedback(dto)

    async def test_submit_feedback_already_rated(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED)
        session.get.return_value = req
        existing_feedback = MagicMock(spec=Feedback)
        feedback_repo.get_for_request = AsyncMock(return_value=existing_feedback)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=5)
        with pytest.raises(PermissionDeniedError):
            await service.submit_feedback(dto)

    async def test_submit_feedback_not_delivered(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)
        req = _make_request(id=1, status=RequestStatus.PENDING, student_id=42)
        session.get.return_value = req
        feedback_repo.get_for_request = AsyncMock(return_value=None)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=5)
        with pytest.raises(PermissionDeniedError):
            await service.submit_feedback(dto)

    async def test_submit_feedback_invalid_rating(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED, student_id=42)
        session.get.return_value = req
        feedback_repo.get_for_request = AsyncMock(return_value=None)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=6)
        with pytest.raises(ValidationError):
            await service.submit_feedback(dto)

    async def test_submit_feedback_rating_zero(self):
        session = _make_session()
        repo = RequestRepository(session)
        feedback_repo = FeedbackRepository(session)
        req = _make_request(id=1, status=RequestStatus.DELIVERED, student_id=42)
        session.get.return_value = req
        feedback_repo.get_for_request = AsyncMock(return_value=None)

        service = RequestService(session)
        service.request_repo = repo
        service.feedback_repo = feedback_repo

        dto = CreateFeedbackDTO(request_id=1, student_id=42, rating=0)
        with pytest.raises(ValidationError):
            await service.submit_feedback(dto)
