# bot/admin/service.py
import logging
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.constants.enums import AdminActionType, DriverStatus, UserRole
from bot.core.db.session import async_session
from bot.core.exceptions import NotFoundError, PackitbotError, ValidationError
from bot.core.models.admin_action_log import AdminActionLog
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.admin.schemas import DriverApplicationDetailDTO, ReviewDriverDTO

logger = logging.getLogger(__name__)


async def get_pending_drivers(
    page: int = 1,
    per_page: int = 5,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[DriverApplicationDetailDTO], int]:
    """Retrieves paginated pending driver applications and total pages count."""
    async def _execute(sess: AsyncSession):
        offset = (page - 1) * per_page

        count_stmt = (
            select(func.count(DriverProfile.id))
            .where(DriverProfile.status == DriverStatus.PENDING_APPROVAL)
        )
        total_res = await sess.execute(count_stmt)
        total_count = total_res.scalar() or 0
        total_pages = max(1, (total_count + per_page - 1) // per_page)

        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .where(DriverProfile.status == DriverStatus.PENDING_APPROVAL)
            .order_by(DriverProfile.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        res = await sess.execute(stmt)
        rows = res.all()

        dtos = []
        for dp, user in rows:
            dtos.append(
                DriverApplicationDetailDTO(
                    driver_id=dp.id,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    full_name=user.full_name,
                    phone_number=user.phone_number,
                    vehicle_type=dp.vehicle_type,
                    plate_number=dp.plate_number,
                    license_number=dp.license_number,
                    status=dp.status,
                    username=user.username,
                )
            )
        return dtos, total_pages

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_driver_application_detail(
    driver_id: int,
    session: Optional[AsyncSession] = None,
) -> DriverApplicationDetailDTO:
    """Gets detailed application info for a driver by driver_id."""
    async def _execute(sess: AsyncSession):
        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .where(DriverProfile.id == driver_id)
        )
        res = await sess.execute(stmt)
        row = res.first()
        if not row:
            raise NotFoundError(f"Driver profile with ID {driver_id} not found.")

        dp, user = row
        return DriverApplicationDetailDTO(
            driver_id=dp.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=user.full_name,
            phone_number=user.phone_number,
            vehicle_type=dp.vehicle_type,
            plate_number=dp.plate_number,
            license_number=dp.license_number,
            status=dp.status,
            username=user.username,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def approve_driver(
    dto: ReviewDriverDTO,
    session: Optional[AsyncSession] = None,
) -> DriverApplicationDetailDTO:
    """Approves a pending driver application, logs admin action, and returns detail DTO."""
    async def _execute(sess: AsyncSession):
        # 1. Fetch admin user
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # 2. Fetch driver profile & user
        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .where(DriverProfile.id == dto.driver_id)
        )
        res = await sess.execute(stmt)
        row = res.first()
        if not row:
            raise NotFoundError(f"Driver profile with ID {dto.driver_id} not found.")

        dp, driver_user = row

        if dp.status == DriverStatus.APPROVED:
            raise ValidationError("Driver application is already approved.")

        # 3. Update driver profile status
        dp.status = DriverStatus.APPROVED
        driver_user.role = UserRole.DRIVER

        # 4. Create admin action log
        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.APPROVE_DRIVER,
            target_user_id=driver_user.id,
            details=f"Approved driver profile #{dp.id}",
        )
        sess.add(log_entry)
        await sess.flush()

        return DriverApplicationDetailDTO(
            driver_id=dp.id,
            user_id=driver_user.id,
            telegram_id=driver_user.telegram_id,
            full_name=driver_user.full_name,
            phone_number=driver_user.phone_number,
            vehicle_type=dp.vehicle_type,
            plate_number=dp.plate_number,
            license_number=dp.license_number,
            status=dp.status,
            username=driver_user.username,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            try:
                result_dto = await _execute(sess)
                await sess.commit()
                return result_dto
            except Exception:
                await sess.rollback()
                raise


async def reject_driver(
    dto: ReviewDriverDTO,
    session: Optional[AsyncSession] = None,
) -> DriverApplicationDetailDTO:
    """Rejects a pending driver application, logs admin action, and returns detail DTO."""
    async def _execute(sess: AsyncSession):
        # 1. Fetch admin user
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # 2. Fetch driver profile & user
        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .where(DriverProfile.id == dto.driver_id)
        )
        res = await sess.execute(stmt)
        row = res.first()
        if not row:
            raise NotFoundError(f"Driver profile with ID {dto.driver_id} not found.")

        dp, driver_user = row

        # 3. Update driver profile status
        dp.status = DriverStatus.REJECTED

        # 4. Create admin action log
        details_msg = f"Rejected driver profile #{dp.id}"
        if dto.rejection_reason:
            details_msg += f". Reason: {dto.rejection_reason}"

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.REJECT_DRIVER,
            target_user_id=driver_user.id,
            details=details_msg,
        )
        sess.add(log_entry)
        await sess.flush()

        return DriverApplicationDetailDTO(
            driver_id=dp.id,
            user_id=driver_user.id,
            telegram_id=driver_user.telegram_id,
            full_name=driver_user.full_name,
            phone_number=driver_user.phone_number,
            vehicle_type=dp.vehicle_type,
            plate_number=dp.plate_number,
            license_number=dp.license_number,
            status=dp.status,
            username=driver_user.username,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            try:
                result_dto = await _execute(sess)
                await sess.commit()
                return result_dto
            except Exception:
                await sess.rollback()
                raise
