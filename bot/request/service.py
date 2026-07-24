from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.constants.enums import CancelledBy, RequestStatus
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
from bot.request.business_rules import (
    can_assign_driver,
    can_edit_request,
    can_rate_delivery,
    can_student_cancel,
)
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
from bot.request.state_machine import can_transition


class RequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.request_repo = RequestRepository(session)
        self.status_log_repo = StatusLogRepository(session)
        self.feedback_repo = FeedbackRepository(session)

    async def create_request(
        self, dto: CreateRequestDTO
    ) -> tuple[DeliveryRequest, RequestCreatedEvent]:
        try:
            request = await self.request_repo.create(
                student_id=dto.student_id,
                pickup_detail=dto.pickup_detail,
                dropoff_address=dto.dropoff_address,
                dropoff_landmark=dto.dropoff_landmark,
                hall_of_residence=dto.hall_of_residence,
                recipient_name=dto.recipient_name,
                recipient_phone=dto.recipient_phone,
                luggage_size=dto.luggage_size,
                luggage_count=dto.luggage_count,
                special_instructions=dto.special_instructions,
                preferred_date=dto.preferred_date,
                preferred_time_window=dto.preferred_time_window,
                status=RequestStatus.PENDING,
            )
            await self.status_log_repo.create(
                request_id=request.id,
                old_status=None,
                new_status=RequestStatus.PENDING,
                changed_by_user_id=dto.student_id,
                note="Request created by student",
            )
            event = RequestCreatedEvent(
                request_id=request.id,
                student_id=dto.student_id,
            )
            return request, event
        except IntegrityError as exc:
            raise ValidationError("Failed to create request due to invalid foreign key reference.") from exc

    async def update_request(self, dto: UpdateRequestDTO) -> DeliveryRequest:
        request = await self.request_repo.get_by_id(dto.request_id)
        if request is None:
            raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")

        if not can_edit_request(request, dto.actor_id):
            raise PermissionDeniedError("Request cannot be edited in its current status or by this user.")

        try:
            updated_request = await self.request_repo.update(
                dto.request_id, **dto.changed_fields
            )
            if updated_request is None:
                raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")
            return updated_request
        except IntegrityError as exc:
            raise ValidationError("Failed to update request details.") from exc

    async def assign_driver(
        self, dto: AssignDriverDTO, driver_profile: DriverProfile
    ) -> tuple[DeliveryRequest, RequestAssignedEvent]:
        request = await self.request_repo.get_by_id(dto.request_id)
        if request is None:
            raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")

        if not can_assign_driver(driver_profile):
            raise DriverUnavailableError("Driver is not approved or available for assignment.")

        if not can_transition(request.status, RequestStatus.ASSIGNED):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {request.status} to {RequestStatus.ASSIGNED}"
            )

        old_status = request.status
        try:
            updated_request = await self.request_repo.update(
                dto.request_id,
                driver_id=dto.driver_id,
                status=RequestStatus.ASSIGNED,
            )
            await self.status_log_repo.create(
                request_id=request.id,
                old_status=old_status,
                new_status=RequestStatus.ASSIGNED,
                changed_by_user_id=dto.admin_id,
                note=f"Assigned to driver {dto.driver_id}",
            )
            event = RequestAssignedEvent(
                request_id=request.id,
                driver_id=dto.driver_id,
                admin_id=dto.admin_id,
            )
            return updated_request, event
        except IntegrityError as exc:
            raise ValidationError("Failed to assign driver due to integrity constraint.") from exc

    async def transition_status(
        self, dto: TransitionDTO
    ) -> tuple[DeliveryRequest, RequestStatusChangedEvent]:
        request = await self.request_repo.get_by_id(dto.request_id)
        if request is None:
            raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")

        old_status = request.status
        if not can_transition(old_status, dto.new_status):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {old_status} to {dto.new_status}"
            )

        try:
            updated_request = await self.request_repo.update(
                dto.request_id,
                status=dto.new_status,
            )
            await self.status_log_repo.create(
                request_id=request.id,
                old_status=old_status,
                new_status=dto.new_status,
                changed_by_user_id=dto.actor_id,
                note=dto.note,
            )
            event = RequestStatusChangedEvent(
                request_id=request.id,
                old_status=old_status,
                new_status=dto.new_status,
                actor_id=dto.actor_id,
            )
            return updated_request, event
        except IntegrityError as exc:
            raise ValidationError("Failed to transition status.") from exc

    async def cancel_request(
        self, dto: CancelRequestDTO
    ) -> tuple[DeliveryRequest, RequestCancelledEvent]:
        request = await self.request_repo.get_by_id(dto.request_id)
        if request is None:
            raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")

        if dto.cancelled_by == CancelledBy.STUDENT and not can_student_cancel(request, dto.actor_id):
            raise PermissionDeniedError("Student cannot cancel request in current status.")

        old_status = request.status
        if not can_transition(old_status, RequestStatus.CANCELLED):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {old_status} to {RequestStatus.CANCELLED}"
            )

        try:
            updated_request = await self.request_repo.update(
                dto.request_id,
                status=RequestStatus.CANCELLED,
                cancelled_by=dto.cancelled_by,
                cancellation_reason=dto.cancellation_reason,
            )
            await self.status_log_repo.create(
                request_id=request.id,
                old_status=old_status,
                new_status=RequestStatus.CANCELLED,
                changed_by_user_id=dto.actor_id,
                note=dto.cancellation_reason or f"Cancelled by {dto.cancelled_by}",
            )
            event = RequestCancelledEvent(
                request_id=request.id,
                cancelled_by=dto.cancelled_by,
                actor_id=dto.actor_id,
                reason=dto.cancellation_reason,
            )
            return updated_request, event
        except IntegrityError as exc:
            raise ValidationError("Failed to cancel request.") from exc

    async def submit_feedback(
        self, dto: CreateFeedbackDTO
    ) -> tuple[Feedback, FeedbackSubmittedEvent]:
        request = await self.request_repo.get_by_id(dto.request_id)
        if request is None:
            raise NotFoundError(f"DeliveryRequest with id={dto.request_id} not found")

        existing_feedback = await self.feedback_repo.get_for_request(dto.request_id)
        if not can_rate_delivery(request, existing_feedback):
            raise PermissionDeniedError("Delivery cannot be rated in current status or has already been rated.")

        if dto.rating < 1 or dto.rating > 5:
            raise ValidationError("Rating must be an integer between 1 and 5.")

        try:
            feedback = await self.feedback_repo.create(
                request_id=dto.request_id,
                student_id=dto.student_id,
                rating=dto.rating,
                comment=dto.comment,
            )
            event = FeedbackSubmittedEvent(
                feedback_id=feedback.id,
                request_id=dto.request_id,
                student_id=dto.student_id,
                rating=dto.rating,
            )
            return feedback, event
        except IntegrityError as exc:
            raise ValidationError("Feedback already submitted or invalid foreign key.") from exc
