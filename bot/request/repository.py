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
    def __init__(self, session: AsyncSession):
        super().__init__(session, DeliveryRequest)

    async def get_pending(self, page: int = 1) -> list[DeliveryRequest]:
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
        stmt = (
            select(DeliveryRequest)
            .where(
                DeliveryRequest.driver_id == driver_id,
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
        stmt = (
            select(DeliveryRequest.dropoff_address)
            .where(DeliveryRequest.student_id == student_id)
            .group_by(DeliveryRequest.dropoff_address)
            .order_by(desc(func.max(DeliveryRequest.created_at)))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]


class StatusLogRepository(BaseRepository[RequestStatusLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, RequestStatusLog)

    async def get_for_request(self, request_id: int) -> list[RequestStatusLog]:
        stmt = (
            select(RequestStatusLog)
            .where(RequestStatusLog.request_id == request_id)
            .order_by(RequestStatusLog.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FeedbackRepository(BaseRepository[Feedback]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Feedback)

    async def get_for_request(self, request_id: int) -> Optional[Feedback]:
        stmt = select(Feedback).where(Feedback.request_id == request_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()