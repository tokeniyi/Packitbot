"""
Request Repository Module
==========================

Data-access layer for delivery requests, their status logs, and feedback.

Provides three SQLAlchemy async repositories:

1. ``RequestRepository`` -- CRUD for ``DeliveryRequest`` plus several
   specialized query methods (pending list, active-for-driver, student
   history, and dropoff-address autocomplete).
2. ``StatusLogRepository`` -- Read access to ``RequestStatusLog`` entries.
3. ``FeedbackRepository`` -- Read/write access to ``Feedback`` records.

All repositories extend ``BaseRepository`` which supplies generic
``create``, ``get_by_id``, ``update``, and ``delete`` methods.

**Key Dependencies:**
- *Uses:* ``bot.core.constants.enums``, ``bot.core.constants.limits`` (``PAGE_SIZE``), ``bot.core.models``, ``bot.core.repositories.base_repository``
- *Used by:* ``bot/request/service.py``, ``bot/student/handler.py``, ``bot/student/handler_requests.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``, ``tests/unit/request/test_repository.py``, ``tests/integration/handlers/test_request_lifecycle.py``
"""
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.constants.enums import RequestStatus
from bot.core.constants.limits import PAGE_SIZE
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.feedback import Feedback
from bot.core.models.status_log import RequestStatusLog
from bot.core.repositories.base_repository import BaseRepository


class RequestRepository(BaseRepository[DeliveryRequest]):
    """Async repository for ``DeliveryRequest`` persistence and querying.

    Inherits generic CRUD from ``BaseRepository`` and adds domain-specific
    query methods used by the service layer and handlers.

    **Calls / Depends on:** ``BaseRepository`` (generic CRUD), ``AsyncSession``,
    ``PAGE_SIZE`` constant.

    **Called by:** ``bot/request/service.py`` (all service methods),
    ``bot/student/handler.py``, ``bot/admin/handler.py``, ``bot/driver/handler.py``.
    """

    def __init__(self, session: AsyncSession):
        """Bind this repository to an existing async database session.

        Args:
            session: SQLAlchemy ``AsyncSession`` scoped to the current request context.
        """
        super().__init__(session, DeliveryRequest)

    async def get_pending(self, page: int = 1) -> list[DeliveryRequest]:
        """Retrieve a paginated list of requests awaiting driver assignment.

        Ordered by creation time descending so the newest pending requests
        appear first to admins.

        **Calls / Depends on:** ``BaseRepository.session`` (inherited),
        ``PAGE_SIZE``, ``RequestStatus.PENDING``.

        **Called by:** ``bot/admin/handler.py`` (admin dashboard / driver assignment).

        Args:
            page: 1-based page number for pagination.

        Returns:
            List of ``DeliveryRequest`` objects in PENDING status, up to
            ``PAGE_SIZE`` per page, newest first.
        """
        offset = (page - 1) * PAGE_SIZE
        stmt = (
            select(DeliveryRequest)
            .where(DeliveryRequest.status == RequestStatus.PENDING)
            .order_by(desc(DeliveryRequest.created_at))
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_driver(self, driver_id: int) -> DeliveryRequest | None:
        """Retrieve the single currently active request for a given driver.

        "Active" means any status except DELIVERED, CANCELLED, or FAILED.
        This prevents a driver from being assigned overlapping deliveries.

        The query orders by creation time descending; in practice there
        should be at most one active request per driver, so ordering is
        primarily a safety net.

        **Calls / Depends on:** ``RequestStatus`` terminal states.

        **Called by:** ``bot/driver/handler.py`` (driver active delivery lookup).

        Args:
            driver_id: Telegram user ID of the driver.

        Returns:
            The most recent active ``DeliveryRequest`` for the driver, or
            ``None`` if the driver has no active requests.
        """
        stmt = (
            select(DeliveryRequest)
            .where(
                DeliveryRequest.driver_id == driver_id,
                # Exclude terminal states so we only see in-flight deliveries.
                DeliveryRequest.status.not_in(
                    {
                        RequestStatus.DELIVERED,
                        RequestStatus.CANCELLED,
                        RequestStatus.FAILED,
                    }
                ),
            )
            .order_by(desc(DeliveryRequest.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history_for_student(
        self, student_id: int, page: int = 1
    ) -> list[DeliveryRequest]:
        """Retrieve a paginated delivery history for a student.

        Returns all requests (regardless of status) authored by the student,
        ordered newest first.

        **Calls / Depends on:** ``PAGE_SIZE``.

        **Called by:** ``bot/student/handler.py`` (student delivery history).

        Args:
            student_id: Telegram user ID of the student.
            page: 1-based page number for pagination.

        Returns:
            List of ``DeliveryRequest`` objects, up to ``PAGE_SIZE`` per page.
        """
        offset = (page - 1) * PAGE_SIZE
        stmt = (
            select(DeliveryRequest)
            .where(DeliveryRequest.student_id == student_id)
            .order_by(desc(DeliveryRequest.created_at))
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dropoff_address_history_for_student(
        self, student_id: int, limit: int = 5
    ) -> list[str]:
        """Retrieve distinct recent dropoff addresses for a student.

        Used to populate an autocomplete or quick-select widget when the
        student creates a new request. Addresses are grouped by value and
        the most recently used ones are returned first.

        **Calls / Depends on:** ``func.max`` for latest timestamp per group.

        **Called by:** ``bot/student/handler.py`` (address suggestion feature).

        Args:
            student_id: Telegram user ID of the student.
            limit: Maximum number of distinct addresses to return (default 5).

        Returns:
            List of unique dropoff address strings, most recently used first.
        """
        stmt = (
            select(DeliveryRequest.dropoff_address)
            .where(DeliveryRequest.student_id == student_id)
            # Group by address so each distinct address appears once.
            .group_by(DeliveryRequest.dropoff_address)
            # Order by the *most recent* request time per address.
            .order_by(desc(func.max(DeliveryRequest.created_at)))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        # ``result.all()`` returns tuples of one column each; extract the value.
        return [row[0] for row in result.all()]


class StatusLogRepository(BaseRepository[RequestStatusLog]):
    """Async repository for ``RequestStatusLog`` read/write access.

    **Calls / Depends on:** ``BaseRepository``.

    **Called by:** ``bot/request/service.py`` (status-change logging).
    """

    def __init__(self, session: AsyncSession):
        """Bind this repository to an existing async database session.

        Args:
            session: SQLAlchemy ``AsyncSession`` scoped to the current request context.
        """
        super().__init__(session, RequestStatusLog)

    async def get_for_request(self, request_id: int) -> list[RequestStatusLog]:
        """Retrieve the complete status-change history for a request.

        Ordered chronologically ascending so the first event appears first.

        **Calls / Depends on:** ``AsyncSession.execute``.

        **Called by:** ``bot/request/service.py`` (status logging),
        ``bot/admin/handler.py`` (admin audit view).

        Args:
            request_id: Primary key of the ``DeliveryRequest``.

        Returns:
            List of ``RequestStatusLog`` entries ordered oldest to newest.
        """
        stmt = (
            select(RequestStatusLog)
            .where(RequestStatusLog.request_id == request_id)
            .order_by(RequestStatusLog.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FeedbackRepository(BaseRepository[Feedback]):
    """Async repository for ``Feedback`` read/write access.

    **Calls / Depends on:** ``BaseRepository``.

    **Called by:** ``bot/request/service.py`` (feedback creation and lookup),
    ``bot/student/handler.py`` (feedback flow).
    """

    def __init__(self, session: AsyncSession):
        """Bind this repository to an existing async database session.

        Args:
            session: SQLAlchemy ``AsyncSession`` scoped to the current request context.
        """
        super().__init__(session, Feedback)

    async def get_for_request(self, request_id: int) -> Optional[Feedback]:
        """Retrieve existing feedback for a specific delivery request.

        **Calls / Depends on:** ``AsyncSession.execute``, ``scalar_one_or_none``.

        **Called by:** ``bot/request/service.py::RequestService.submit_feedback``,
        ``bot/student/handler.py`` (feedback eligibility check).

        Args:
            request_id: Primary key of the ``DeliveryRequest``.

        Returns:
            The ``Feedback`` instance if one exists; ``None`` otherwise.
        """
        stmt = select(Feedback).where(Feedback.request_id == request_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
