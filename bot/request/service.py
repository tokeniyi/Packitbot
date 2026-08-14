"""
Request Service Module
======================

Core orchestration layer for delivery request lifecycle operations.

This module provides the ``RequestService`` class which coordinates between
repositories, business rule validators, state machines, and domain events
to perform high-level request operations such as creation, updates, driver
assignment, status transitions, cancellation, and feedback submission.

**Key Dependencies:**
- *Uses:* ``bot.request.repository``, ``bot.request.schemas``, ``bot.request.state_machine``, ``bot.request.business_rules``, ``bot.request.events``
- *Uses by:* ``bot/student/handler.py``, ``bot/student/handler_requests.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``, ``tests/integration/handlers/test_request_lifecycle.py``
"""
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
    """Service layer encapsulating all delivery request business logic.

    Coordinates data access through repositories, enforces domain rules via
    business rule functions and the state machine, and emits domain events
    for each significant state change.

    **Calls / Depends on:** ``RequestRepository``, ``StatusLogRepository``, ``FeedbackRepository``, ``can_transition``, ``can_edit_request``, ``can_assign_driver``, ``can_student_cancel``, ``can_rate_delivery``, all event dataclasses.

    **Called by:** ``bot/student/handler.py``, ``bot/student/handler_requests.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``.
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with a database session and fresh repositories.

        Args:
            session: SQLAlchemy async session bound to the current request context.
        """
        self.session = session
        self.request_repo = RequestRepository(session)
        self.status_log_repo = StatusLogRepository(session)
        self.feedback_repo = FeedbackRepository(session)

    async def create_request(
        self, dto: CreateRequestDTO
    ) -> tuple[DeliveryRequest, RequestCreatedEvent]:
        """Persist a new delivery request and record its initial status.

        Creates the ``DeliveryRequest`` row with ``PENDING`` status, then
        writes a corresponding status log entry. The caller is responsible
        for handling the emitted ``RequestCreatedEvent`` (e.g., notifying
        the student or dispatching a notification).

        **Calls / Depends on:** ``RequestRepository.create``, ``StatusLogRepository.create``, ``RequestCreatedEvent``.

        **Called by:** ``bot/student/handler.py`` (student request creation flow).

        Args:
            dto: Validated DTO containing all fields required to create a request.

        Returns:
            A tuple of ``(created_delivery_request, request_created_event)``.

        Raises:
            ValidationError: If a database integrity constraint is violated
                (e.g., invalid ``student_id`` foreign key).
        """
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
            # Record the initial PENDING status so the audit trail starts here.
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
            # Translate low-level DB constraint errors into domain-level ValidationError.
            raise ValidationError("Failed to create request due to invalid foreign key reference.") from exc

    async def update_request(self, dto: UpdateRequestDTO) -> DeliveryRequest:
        """Apply partial updates to an existing delivery request.

        Only requests in ``PENDING`` status authored by ``actor_id`` may be
        edited. Updates are applied as a partial dict merge so only the
        fields present in ``changed_fields`` are touched.

        **Calls / Depends on:** ``RequestRepository.get_by_id``, ``RequestRepository.update``, ``can_edit_request``.

        **Called by:** ``bot/student/handler.py`` (student request edit flow).

        Args:
            dto: DTO containing the request ID, actor ID, and dict of fields to update.

        Returns:
            The updated ``DeliveryRequest`` instance.

        Raises:
            NotFoundError: If no request exists with the given ``request_id``.
            PermissionDeniedError: If the request cannot be edited (wrong status or actor).
            ValidationError: If a database integrity constraint is violated.
        """
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
        """Assign an approved, available driver to a request and mark it ASSIGNED.

        Performs three pre-condition checks before mutating state:
        1. The driver must be approved and available (business rule).
        2. The current request status must allow transitioning to ``ASSIGNED``.
        3. The request must exist.

        **Calls / Depends on:** ``RequestRepository.get_by_id``, ``RequestRepository.update``, ``StatusLogRepository.create``, ``can_assign_driver``, ``can_transition``, ``RequestAssignedEvent``.

        **Called by:** ``bot/admin/handler.py`` (admin driver assignment flow).

        Args:
            dto: DTO with ``request_id``, ``driver_id``, and ``admin_id``.
            driver_profile: The ``DriverProfile`` object retrieved beforehand.

        Returns:
            A tuple of ``(updated_request, request_assigned_event)``.

        Raises:
            NotFoundError: If the request does not exist.
            DriverUnavailableError: If the driver is not approved or available.
            InvalidStatusTransitionError: If the request's current status cannot
                transition to ``ASSIGNED``.
            ValidationError: If a database integrity constraint is violated.
        """
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
            # Log the status transition for audit and driver-side visibility.
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
        """Advance a request to a new status after validating the transition.

        Used by drivers (and potentially admins) to move requests through
        the operational pipeline (e.g., ACCEPTED -> EN_ROUTE_TO_PICKUP).

        **Calls / Depends on:** ``RequestRepository.get_by_id``, ``RequestRepository.update``, ``StatusLogRepository.create``, ``can_transition``, ``RequestStatusChangedEvent``.

        **Called by:** ``bot/driver/handler.py`` (driver action handlers).

        Args:
            dto: DTO with ``request_id``, ``new_status``, ``actor_id``, and optional ``note``.

        Returns:
            A tuple of ``(updated_request, request_status_changed_event)``.

        Raises:
            NotFoundError: If the request does not exist.
            InvalidStatusTransitionError: If the transition is not permitted by the state machine.
            ValidationError: If a database integrity constraint is violated.
        """
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
        """Cancel a delivery request after validating who is cancelling and why.

        Students may only cancel requests they own and only while the request
        is in PENDING, ASSIGNED, or ACCEPTED status. Admins/drivers may
        cancel from any terminal-ish state that the state machine permits.

        **Calls / Depends on:** ``RequestRepository.get_by_id``, ``RequestRepository.update``, ``StatusLogRepository.create``, ``can_student_cancel``, ``can_transition``, ``RequestCancelledEvent``.

        **Called by:** ``bot/student/handler.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``.

        Args:
            dto: DTO with ``request_id``, ``actor_id``, ``cancelled_by``, and optional ``cancellation_reason``.

        Returns:
            A tuple of ``(updated_request, request_cancelled_event)``.

        Raises:
            NotFoundError: If the request does not exist.
            PermissionDeniedError: If a student tries to cancel a request they
                do not own, or a request in a non-cancellable status.
            InvalidStatusTransitionError: If the current status cannot
                transition to ``CANCELLED``.
            ValidationError: If a database integrity constraint is violated.
        """
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
        """Record student feedback (rating + optional comment) for a delivered request.

        Ensures the request is in ``DELIVERED`` status and has not already
        received feedback. The rating is validated to be within [1, 5].

        **Calls / Depends on:** ``RequestRepository.get_by_id``, ``FeedbackRepository.get_for_request``, ``FeedbackRepository.create``, ``can_rate_delivery``, ``FeedbackSubmittedEvent``.

        **Called by:** ``bot/student/handler.py`` (student feedback flow).

        Args:
            dto: DTO with ``request_id``, ``student_id``, ``rating``, and optional ``comment``.

        Returns:
            A tuple of ``(created_feedback, feedback_submitted_event)``.

        Raises:
            NotFoundError: If the request does not exist.
            PermissionDeniedError: If the request is not in DELIVERED status
                or feedback already exists.
            ValidationError: If the rating is outside [1, 5] or a database
                integrity constraint is violated.
        """
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
            # Raised when feedback already exists or FK constraints fail.
            raise ValidationError("Feedback already submitted or invalid foreign key.") from exc
