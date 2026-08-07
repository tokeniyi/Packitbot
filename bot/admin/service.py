"""
Admin service layer for the Packit bot.

This module contains the business logic for all admin operations, including:
- Delivery request management (listing pending requests, assigning drivers)
- Driver lifecycle management (listing pending applications, approving, rejecting)
- Driver record management (listing all drivers, viewing details, updating fields, removing records)
- User management (searching, banning, unbanning, promoting to admin)
- System statistics aggregation
- Broadcast target audience resolution

All public functions follow a consistent pattern:
    1. Verify the calling user has admin privileges.
    2. Perform the database operation within a transaction.
    3. Log the action in ``AdminActionLog`` for audit trail.
    4. Return a DTO for the handler to render.

Key exports:
    - ``get_pending_requests``
    - ``get_available_drivers_ranked``
    - ``get_pending_drivers``
    - ``get_driver_application_detail``
    - ``approve_driver``
    - ``reject_driver``
    - ``get_stats``
    - ``ban_user``
    - ``unban_user``
    - ``promote_admin``
    - ``search_user_by_identifier``
    - ``get_broadcast_target_telegram_ids``
    - ``get_all_drivers``
    - ``get_driver_by_id``
    - ``update_driver_field``
    - ``remove_driver``

Dependencies:
    - ``sqlalchemy``: Query construction and async execution.
    - ``bot.core.db.session``: ``async_session`` factory.
    - ``bot.core.models``: ORM models for database operations.
    - ``bot.admin.schemas``: DTOs for input validation and output shaping.

Called by:
    - ``bot/admin/handler.py``: All admin command and callback handlers.
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
from bot.core.constants.enums import AccountStatus, AdminActionType, DriverAvailability, DriverStatus, RequestStatus, UserRole
from bot.core.db.session import async_session
from bot.core.exceptions import DuplicateResourceError, NotFoundError, PackitbotError, ValidationError
from bot.core.models.admin_action_log import AdminActionLog
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.models.user import User
from bot.core.utils.validators import (
    validate_full_name,
    validate_license_number,
    validate_phone,
    validate_plate_number,
    validate_vehicle_type,
)
from bot.driver.repository import DriverRepository
from bot.admin.schemas import (
    AvailableDriverDTO,
    BanUserDTO,
    DriverApplicationDetailDTO,
    DriverDetailDTO,
    DriverListItemDTO,
    PromoteAdminDTO,
    RemoveDriverDTO,
    ReviewDriverDTO,
    SystemStatsDTO,
    UnbanUserDTO,
    UpdateDriverFieldDTO,
    UserDetailDTO,
)

logger = logging.getLogger(__name__)


async def get_pending_requests(
    page: int = 1,
    per_page: int = 5,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[DeliveryRequest], int]:
    """Retrieve paginated delivery requests with PENDING status.

    This function is used by the admin portal to display requests awaiting
    driver assignment. It returns both the page of results and the total
    page count for pagination UI rendering.

    Args:
        page (int): 1-indexed page number. Defaults to 1.
        per_page (int): Number of records per page. Defaults to 5.
        session (Optional[AsyncSession]): Optional existing database session.
            If omitted, a new session is created and closed automatically.

    Returns:
        Tuple[List[DeliveryRequest], int]: A tuple of (requests, total_pages).

    Raises:
        None directly, but database errors propagate as ``PackitbotError``
        via the global error handler.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``func.count``
        - ``bot.core.models.delivery_request.DeliveryRequest``
        - ``bot.core.constants.enums.RequestStatus``

    Called by:
        - ``bot/admin/handler.py``: ``cmd_pending_requests``,
          ``handle_pending_requests_pagination``,
          ``handle_back_to_pending_requests``
    """
    async def _execute(sess: AsyncSession):
        offset = (page - 1) * per_page

        count_stmt = (
            select(func.count(DeliveryRequest.id))
            .where(DeliveryRequest.status == RequestStatus.PENDING)
        )
        total_res = await sess.execute(count_stmt)
        total_count = total_res.scalar() or 0
        # Ceiling division to ensure at least 1 page when records exist.
        total_pages = max(1, (total_count + per_page - 1) // per_page)

        stmt = (
            select(DeliveryRequest)
            .where(DeliveryRequest.status == RequestStatus.PENDING)
            .order_by(DeliveryRequest.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        res = await sess.execute(stmt)
        requests = list(res.scalars().all())
        return requests, total_pages

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_available_drivers_ranked(
    session: Optional[AsyncSession] = None,
) -> List[AvailableDriverDTO]:
    """Retrieve approved, non-offline drivers ranked by rating and delivery volume.

    Drivers are ordered by descending average rating, then descending total
    deliveries, then ascending ID as a tiebreaker. This ranking is used when
    an admin assigns a driver to a pending request.

    Args:
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        List[AvailableDriverDTO]: Ranked list of available drivers.

    Raises:
        None directly.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.user.User``
        - ``bot.core.constants.enums.DriverStatus``, ``DriverAvailability``
        - ``bot.admin.schemas.AvailableDriverDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_select_request_for_assignment``
    """
    async def _execute(sess: AsyncSession):
        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .where(
                DriverProfile.status == DriverStatus.APPROVED,
                DriverProfile.availability != DriverAvailability.OFFLINE,
            )
            .order_by(
                DriverProfile.rating_avg.desc(),
                DriverProfile.total_deliveries.desc(),
                DriverProfile.id.asc(),
            )
        )
        res = await sess.execute(stmt)
        rows = res.all()

        dtos = []
        for dp, user in rows:
            dtos.append(
                AvailableDriverDTO(
                    driver_id=dp.id,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    full_name=user.full_name or "Unknown Driver",
                    phone_number=user.phone_number or "N/A",
                    vehicle_type=dp.vehicle_type,
                    rating_avg=dp.rating_avg,
                    total_deliveries=dp.total_deliveries,
                    username=user.username,
                )
            )
        return dtos

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_pending_drivers(
    page: int = 1,
    per_page: int = 5,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[DriverApplicationDetailDTO], int]:
    """Retrieve paginated driver applications pending approval.

    Args:
        page (int): 1-indexed page number. Defaults to 1.
        per_page (int): Number of records per page. Defaults to 5.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        Tuple[List[DriverApplicationDetailDTO], int]: A tuple of
        (driver_applications, total_pages).

    Raises:
        None directly.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``func.count``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.user.User``
        - ``bot.core.constants.enums.DriverStatus``
        - ``bot.admin.schemas.DriverApplicationDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``cmd_verify_drivers``,
          ``handle_back_to_pending_list``
    """
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
    """Fetch detailed information for a specific driver application.

    Args:
        driver_id (int): Primary key of the ``DriverProfile`` to inspect.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        DriverApplicationDetailDTO: Populated DTO with driver and user details.

    Raises:
        NotFoundError: If no driver profile exists with the given ``driver_id``.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.user.User``
        - ``bot.admin.schemas.DriverApplicationDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_view_driver_detail``
    """
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
    """Approve a pending driver application and log the admin action.

    This function performs the following steps atomically:
        1. Verifies the requesting user is an admin.
        2. Loads the driver profile and associated user.
        3. Validates that the profile is not already approved.
        4. Sets the profile status to ``APPROVED`` and the user role to ``DRIVER``.
        5. Creates an ``AdminActionLog`` entry for audit purposes.

    Args:
        dto (ReviewDriverDTO): Payload containing the driver ID and admin
            Telegram ID.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        DriverApplicationDetailDTO: Updated driver detail DTO reflecting the
        new ``APPROVED`` status.

    Raises:
        ValidationError: If the caller is not an admin or the driver is
            already approved.
        NotFoundError: If the driver profile does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.UserRole``, ``DriverStatus``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``
        - ``bot.admin.schemas.DriverApplicationDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_approve_driver``
    """
    async def _execute(sess: AsyncSession):
        # 1. Verify admin user
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # 2. Fetch driver profile and associated user
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

        # 3. Update driver profile and user role
        dp.status = DriverStatus.APPROVED
        driver_user.role = UserRole.DRIVER

        # 4. Create audit log entry
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
    """Reject a pending driver application and log the admin action.

    This function performs the following steps atomically:
        1. Verifies the requesting user is an admin.
        2. Loads the driver profile and associated user.
        3. Sets the profile status to ``REJECTED``.
        4. Creates an ``AdminActionLog`` entry for audit purposes.

    Args:
        dto (ReviewDriverDTO): Payload containing the driver ID, admin
            Telegram ID, and optional rejection reason.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        DriverApplicationDetailDTO: Updated driver detail DTO reflecting the
        new ``REJECTED`` status.

    Raises:
        ValidationError: If the caller is not an admin.
        NotFoundError: If the driver profile does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.UserRole``, ``DriverStatus``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``
        - ``bot.admin.schemas.DriverApplicationDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_reject_driver``
    """
    async def _execute(sess: AsyncSession):
        # 1. Verify admin user
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # 2. Fetch driver profile and associated user
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

        # 4. Create audit log entry
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


async def get_stats(
    session: Optional[AsyncSession] = None,
) -> SystemStatsDTO:
    """Aggregate system-wide delivery metrics and user statistics.

    This function runs multiple COUNT and AVG queries across the primary
    entities and also computes average delivery duration by correlating
    ``RequestStatusLog`` timestamps for ``ACCEPTED`` and ``DELIVERED`` events.

    Args:
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        SystemStatsDTO: Populated DTO containing all aggregated metrics.

    Raises:
        None directly, but database errors propagate to the caller.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``func.count``, ``func.avg``
        - ``bot.core.models.delivery_request.DeliveryRequest``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.feedback.Feedback``
        - ``bot.core.models.user.User``
        - ``bot.core.models.status_log.RequestStatusLog``
        - ``bot.core.constants.enums.RequestStatus``, ``UserRole``,
          ``DriverStatus``, ``DriverAvailability``
        - ``bot.admin.schemas.SystemStatsDTO``

    Called by:
        - ``bot/admin/handler.py``: ``cmd_stats``
    """
    async def _execute(sess: AsyncSession):
        # Request status counts
        total_requests = (await sess.execute(select(func.count(DeliveryRequest.id)))).scalar() or 0
        pending_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.PENDING)
        )).scalar() or 0
        assigned_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.ASSIGNED)
        )).scalar() or 0
        accepted_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.ACCEPTED)
        )).scalar() or 0
        en_route_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.EN_ROUTE_TO_PICKUP)
        )).scalar() or 0
        picked_up_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.PICKED_UP)
        )).scalar() or 0
        in_transit_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.IN_TRANSIT)
        )).scalar() or 0
        delivered_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.DELIVERED)
        )).scalar() or 0
        cancelled_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.CANCELLED)
        )).scalar() or 0
        failed_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.FAILED)
        )).scalar() or 0
        rejected_by_driver_requests = (await sess.execute(
            select(func.count(DeliveryRequest.id)).where(DeliveryRequest.status == RequestStatus.REJECTED_BY_DRIVER)
        )).scalar() or 0

        # User role counts
        total_users = (await sess.execute(select(func.count(User.id)))).scalar() or 0
        total_students = (await sess.execute(
            select(func.count(User.id)).where(User.role == UserRole.STUDENT)
        )).scalar() or 0
        total_drivers = (await sess.execute(
            select(func.count(User.id)).where(User.role == UserRole.DRIVER)
        )).scalar() or 0
        total_admins = (await sess.execute(
            select(func.count(User.id)).where(User.role == UserRole.ADMIN)
        )).scalar() or 0

        # Driver profile status counts
        approved_drivers = (await sess.execute(
            select(func.count(DriverProfile.id)).where(DriverProfile.status == DriverStatus.APPROVED)
        )).scalar() or 0
        active_drivers = (await sess.execute(
            select(func.count(DriverProfile.id)).where(
                DriverProfile.status == DriverStatus.APPROVED,
                DriverProfile.availability != DriverAvailability.OFFLINE,
            )
        )).scalar() or 0
        pending_drivers = (await sess.execute(
            select(func.count(DriverProfile.id)).where(DriverProfile.status == DriverStatus.PENDING_APPROVAL)
        )).scalar() or 0
        rejected_drivers = (await sess.execute(
            select(func.count(DriverProfile.id)).where(DriverProfile.status == DriverStatus.REJECTED)
        )).scalar() or 0
        suspended_drivers = (await sess.execute(
            select(func.count(DriverProfile.id)).where(DriverProfile.status == DriverStatus.SUSPENDED)
        )).scalar() or 0

        # Feedback metrics
        total_feedbacks = (await sess.execute(select(func.count(Feedback.id)))).scalar() or 0
        avg_rating = (await sess.execute(select(func.avg(Feedback.rating)))).scalar()

        # Average delivery duration: correlate ACCEPTED and DELIVERED log timestamps
        from bot.core.models.status_log import RequestStatusLog
        start_logs = select(
            RequestStatusLog.request_id,
            func.min(RequestStatusLog.created_at).label("start_time"),
        ).where(
            RequestStatusLog.new_status == RequestStatus.ACCEPTED
        ).group_by(RequestStatusLog.request_id).subquery()

        end_logs = select(
            RequestStatusLog.request_id,
            func.max(RequestStatusLog.created_at).label("end_time"),
        ).where(
            RequestStatusLog.new_status == RequestStatus.DELIVERED
        ).group_by(RequestStatusLog.request_id).subquery()

        duration_stmt = select(start_logs.c.start_time, end_logs.c.end_time).join(
            end_logs, start_logs.c.request_id == end_logs.c.request_id
        )
        duration_res = await sess.execute(duration_stmt)
        durations = [
            (end_t - start_t).total_seconds() / 60.0
            for start_t, end_t in duration_res.all()
            if start_t and end_t and end_t > start_t
        ]
        avg_delivery_duration_minutes = (
            round(sum(durations) / len(durations), 1) if durations else None
        )

        return SystemStatsDTO(
            total_requests=total_requests,
            pending_requests=pending_requests,
            assigned_requests=assigned_requests,
            accepted_requests=accepted_requests,
            en_route_requests=en_route_requests,
            picked_up_requests=picked_up_requests,
            in_transit_requests=in_transit_requests,
            delivered_requests=delivered_requests,
            cancelled_requests=cancelled_requests,
            failed_requests=failed_requests,
            rejected_by_driver_requests=rejected_by_driver_requests,
            total_users=total_users,
            total_students=total_students,
            total_drivers=total_drivers,
            total_admins=total_admins,
            approved_drivers=approved_drivers,
            active_drivers=active_drivers,
            pending_drivers=pending_drivers,
            rejected_drivers=rejected_drivers,
            suspended_drivers=suspended_drivers,
            total_feedbacks=total_feedbacks,
            avg_rating=round(avg_rating, 1) if avg_rating is not None else None,
            avg_delivery_duration_minutes=avg_delivery_duration_minutes,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def ban_user(
    dto: BanUserDTO,
    session: Optional[AsyncSession] = None,
) -> UserDetailDTO:
    """Ban a user and record the action in the audit log.

    Args:
        dto (BanUserDTO): Payload containing the target user ID, admin
            Telegram ID, and optional ban reason.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        UserDetailDTO: Updated user snapshot reflecting the banned state.

    Raises:
        ValidationError: If the caller is not an admin or the user is
            already banned.
        NotFoundError: If the target user does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.AccountStatus``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``
        - ``bot.admin.schemas.UserDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``process_ban_reason``
    """
    async def _execute(sess: AsyncSession):
        # Verify admin
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # Target user
        target_stmt = select(User).where(User.id == dto.target_user_id)
        target_res = await sess.execute(target_stmt)
        target_user = target_res.scalar_one_or_none()
        if not target_user:
            raise NotFoundError(f"User with ID {dto.target_user_id} not found.")

        if target_user.account_status == AccountStatus.BANNED:
            raise ValidationError("User is already banned.")

        target_user.account_status = AccountStatus.BANNED
        target_user.banned_reason = dto.reason
        target_user.banned_at = datetime.utcnow()

        details_msg = f"Banned user #{target_user.id}"
        if dto.reason:
            details_msg += f". Reason: {dto.reason}"

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.BAN_USER,
            target_user_id=target_user.id,
            details=details_msg,
        )
        sess.add(log_entry)
        await sess.flush()

        return UserDetailDTO(
            user_id=target_user.id,
            telegram_id=target_user.telegram_id,
            full_name=target_user.full_name,
            username=target_user.username,
            phone_number=target_user.phone_number,
            role=target_user.role.value if target_user.role else None,
            account_status=target_user.account_status.value,
            banned_reason=target_user.banned_reason,
            banned_at=target_user.banned_at.strftime("%Y-%m-%d %H:%M:%S UTC") if target_user.banned_at else None,
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


async def unban_user(
    dto: UnbanUserDTO,
    session: Optional[AsyncSession] = None,
) -> UserDetailDTO:
    """Unban a user and record the action in the audit log.

    Args:
        dto (UnbanUserDTO): Payload containing the target user ID, admin
            Telegram ID, and optional unban note.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        UserDetailDTO: Updated user snapshot reflecting the active state.

    Raises:
        ValidationError: If the caller is not an admin or the user is
            not currently banned.
        NotFoundError: If the target user does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.AccountStatus``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``
        - ``bot.admin.schemas.UserDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_unban_user``
    """
    async def _execute(sess: AsyncSession):
        # Verify admin
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # Target user
        target_stmt = select(User).where(User.id == dto.target_user_id)
        target_res = await sess.execute(target_stmt)
        target_user = target_res.scalar_one_or_none()
        if not target_user:
            raise NotFoundError(f"User with ID {dto.target_user_id} not found.")

        if target_user.account_status != AccountStatus.BANNED:
            raise ValidationError("User is not currently banned.")

        target_user.account_status = AccountStatus.ACTIVE
        target_user.banned_reason = None
        target_user.banned_at = None

        details_msg = f"Unbanned user #{target_user.id}"
        if dto.reason:
            details_msg += f". Reason: {dto.reason}"

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.UNBAN_USER,
            target_user_id=target_user.id,
            details=details_msg,
        )
        sess.add(log_entry)
        await sess.flush()

        return UserDetailDTO(
            user_id=target_user.id,
            telegram_id=target_user.telegram_id,
            full_name=target_user.full_name,
            username=target_user.username,
            phone_number=target_user.phone_number,
            role=target_user.role.value if target_user.role else None,
            account_status=target_user.account_status.value,
            banned_reason=target_user.banned_reason,
            banned_at=None,
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


async def promote_admin(
    dto: PromoteAdminDTO,
    session: Optional[AsyncSession] = None,
) -> UserDetailDTO:
    """Promote a user to the admin role and log the action.

    Args:
        dto (PromoteAdminDTO): Payload containing the target user ID and
            admin Telegram ID.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        UserDetailDTO: Updated user snapshot reflecting the admin role.

    Raises:
        ValidationError: If the caller is not an admin or the target user
            is already an admin.
        NotFoundError: If the target user does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.UserRole``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``
        - ``bot.admin.schemas.UserDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_promote_admin``
    """
    async def _execute(sess: AsyncSession):
        # Verify admin
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

        # Target user
        target_stmt = select(User).where(User.id == dto.target_user_id)
        target_res = await sess.execute(target_stmt)
        target_user = target_res.scalar_one_or_none()
        if not target_user:
            raise NotFoundError(f"User with ID {dto.target_user_id} not found.")

        if target_user.role == UserRole.ADMIN:
            raise ValidationError("User is already an admin.")

        target_user.role = UserRole.ADMIN

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.PROMOTE_ADMIN,
            target_user_id=target_user.id,
            details=f"Promoted user #{target_user.id} to ADMIN",
        )
        sess.add(log_entry)
        await sess.flush()

        return UserDetailDTO(
            user_id=target_user.id,
            telegram_id=target_user.telegram_id,
            full_name=target_user.full_name,
            username=target_user.username,
            phone_number=target_user.phone_number,
            role=target_user.role.value if target_user.role else None,
            account_status=target_user.account_status.value,
            banned_reason=target_user.banned_reason,
            banned_at=target_user.banned_at.strftime("%Y-%m-%d %H:%M:%S UTC") if target_user.banned_at else None,
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


async def search_user_by_identifier(
    identifier: str,
    session: Optional[AsyncSession] = None,
) -> Optional[UserDetailDTO]:
    """Find a user by internal DB ID, Telegram ID, or username.

    The search logic is:
        - If the identifier is numeric, it matches both ``User.id`` and
          ``User.telegram_id`` using an OR condition.
        - If the identifier is non-numeric, it performs a case-insensitive
          match against ``User.username`` (after stripping any leading '@').

    Args:
        identifier (str): User ID, Telegram ID, or @username to search for.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        Optional[UserDetailDTO]: Matching user snapshot, or ``None`` if not found.

    Raises:
        None directly.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``func.lower``
        - ``bot.core.models.user.User``
        - ``bot.admin.schemas.UserDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``process_user_search``
    """
    async def _execute(sess: AsyncSession):
        clean_id = identifier.strip().lstrip("@")
        stmt = None

        if clean_id.isdigit():
            val = int(clean_id)
            stmt = select(User).where((User.id == val) | (User.telegram_id == val))
        else:
            stmt = select(User).where(func.lower(User.username) == clean_id.lower())

        res = await sess.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            return None

        return UserDetailDTO(
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=user.full_name,
            username=user.username,
            phone_number=user.phone_number,
            role=user.role.value if user.role else None,
            account_status=user.account_status.value,
            banned_reason=user.banned_reason,
            banned_at=user.banned_at.strftime("%Y-%m-%d %H:%M:%S UTC") if user.banned_at else None,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_broadcast_target_telegram_ids(
    audience: str,
    session: Optional[AsyncSession] = None,
) -> List[int]:
    """Resolve the list of target Telegram IDs for a broadcast audience.

    Only ``ACTIVE`` users are included. The audience filter narrows the
    result set by role when specified.

    Args:
        audience (str): Target audience identifier. Valid values:
            "students", "drivers", or "all" (no role filter).
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        List[int]: Telegram IDs of users matching the audience criteria.

    Raises:
        None directly.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.constants.enums.AccountStatus``, ``UserRole``

    Called by:
        - ``bot/admin/handler.py``: ``execute_broadcast``
    """
    async def _execute(sess: AsyncSession):
        stmt = select(User.telegram_id).where(User.account_status == AccountStatus.ACTIVE)
        if audience == "students":
            stmt = stmt.where(User.role == UserRole.STUDENT)
        elif audience == "drivers":
            stmt = stmt.where(User.role == UserRole.DRIVER)

        res = await sess.execute(stmt)
        return list(res.scalars().all())

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_all_drivers(
    page: int = 1,
    per_page: int = 5,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[DriverListItemDTO], int]:
    """Retrieve paginated list of all driver records for admin management.

    Args:
        page (int): 1-indexed page number. Defaults to 1.
        per_page (int): Number of records per page. Defaults to 5.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        Tuple[List[DriverListItemDTO], int]: A tuple of (drivers, total_pages).

    Raises:
        None directly.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``func.count``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.user.User``
        - ``bot.core.constants.enums.DriverStatus``, ``DriverAvailability``
        - ``bot.admin.schemas.DriverListItemDTO``

    Called by:
        - ``bot/admin/handler.py``: ``cmd_drivers``,
          ``handle_drivers_pagination``
    """
    async def _execute(sess: AsyncSession):
        offset = (page - 1) * per_page

        count_stmt = select(func.count(DriverProfile.id))
        total_res = await sess.execute(count_stmt)
        total_count = total_res.scalar() or 0
        total_pages = max(1, (total_count + per_page - 1) // per_page)

        stmt = (
            select(DriverProfile, User)
            .join(User, DriverProfile.user_id == User.id)
            .order_by(DriverProfile.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        res = await sess.execute(stmt)
        rows = res.all()

        dtos = []
        for dp, user in rows:
            dtos.append(
                DriverListItemDTO(
                    driver_id=dp.id,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    full_name=user.full_name or "Unknown Driver",
                    phone_number=user.phone_number or "N/A",
                    vehicle_type=dp.vehicle_type,
                    plate_number=dp.plate_number,
                    license_number=dp.license_number,
                    status=dp.status,
                    availability=dp.availability.value,
                    rating_avg=dp.rating_avg,
                    total_deliveries=dp.total_deliveries,
                    username=user.username,
                )
            )
        return dtos, total_pages

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def get_driver_by_id(
    driver_id: int,
    session: Optional[AsyncSession] = None,
) -> DriverDetailDTO:
    """Retrieve detailed information for a specific driver record.

    Args:
        driver_id (int): Primary key of the ``DriverProfile`` to inspect.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        DriverDetailDTO: Populated DTO with driver and user details.

    Raises:
        NotFoundError: If no driver profile exists with the given ``driver_id``.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.user.User``
        - ``bot.core.constants.enums.DriverStatus``, ``DriverAvailability``
        - ``bot.admin.schemas.DriverDetailDTO``

    Called by:
        - ``bot/admin/handler.py``: ``handle_view_driver_detail``
    """
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
        return DriverDetailDTO(
            driver_id=dp.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=user.full_name or "Unknown Driver",
            phone_number=user.phone_number or "N/A",
            vehicle_type=dp.vehicle_type,
            plate_number=dp.plate_number,
            license_number=dp.license_number,
            status=dp.status,
            availability=dp.availability.value,
            rating_avg=dp.rating_avg,
            total_deliveries=dp.total_deliveries,
            username=user.username,
            account_status=user.account_status.value,
        )

    if session is not None:
        return await _execute(session)
    else:
        async with async_session() as sess:
            return await _execute(sess)


async def update_driver_field(
    dto: UpdateDriverFieldDTO,
    session: Optional[AsyncSession] = None,
) -> DriverDetailDTO:
    """Update a specific field on a driver record and log the admin action.

    Supported fields:
        - ``full_name``: Updates ``User.full_name``.
        - ``phone_number``: Updates ``User.phone_number``.
        - ``vehicle_type``: Updates ``DriverProfile.vehicle_type``.
        - ``plate_number``: Updates ``DriverProfile.plate_number``.
        - ``license_number``: Updates ``DriverProfile.license_number``.
        - ``status``: Updates ``DriverProfile.status``.

    Args:
        dto (UpdateDriverFieldDTO): Payload containing the driver ID, field
            name, new value, and admin Telegram ID.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        DriverDetailDTO: Updated driver detail DTO.

    Raises:
        ValidationError: If the caller is not an admin, the field is not
            recognized, or the value fails validation.
        NotFoundError: If the driver profile or associated user does not exist.
        DuplicateResourceError: If the new plate or license number is already taken.

    Calls / Depends on:
        - ``sqlalchemy.select``
        - ``bot.core.models.user.User``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.DriverStatus``, ``AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``,
          ``DuplicateResourceError``
        - ``bot.admin.schemas.DriverDetailDTO``
        - ``bot.driver.repository.DriverRepository``

    Called by:
        - ``bot/admin/handler.py``: ``handle_driver_field_input``
    """
    async def _execute(sess: AsyncSession):
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

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
        field = dto.field
        value = dto.value

        user_fields = {"full_name", "phone_number"}
        profile_fields = {"vehicle_type", "plate_number", "license_number", "status"}

        if field in user_fields:
            if field == "full_name":
                validated = validate_full_name(value)
                driver_user.full_name = validated
            elif field == "phone_number":
                validated = validate_phone(value)
                driver_user.phone_number = validated
        elif field in profile_fields:
            if field == "vehicle_type":
                validated = validate_vehicle_type(value)
                dp.vehicle_type = validated
            elif field == "plate_number":
                validated = validate_plate_number(value)
                repo = DriverRepository(sess)
                existing = await repo.get_by_plate_number(validated)
                if existing and existing.id != dp.id:
                    raise DuplicateResourceError("A driver profile with this plate number already exists.")
                dp.plate_number = validated
            elif field == "license_number":
                validated = validate_license_number(value)
                repo = DriverRepository(sess)
                existing = await repo.get_by_license_number(validated)
                if existing and existing.id != dp.id:
                    raise DuplicateResourceError("A driver profile with this license number already exists.")
                dp.license_number = validated
            elif field == "status":
                try:
                    validated = DriverStatus(value.strip().lower())
                except ValueError:
                    raise ValidationError("Invalid driver status. Choose: pending_approval, approved, rejected, suspended.")
                dp.status = validated
        else:
            raise ValidationError(f"Field '{field}' is not editable.")

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.UPDATE_DRIVER_FIELD,
            target_user_id=driver_user.id,
            details=f"Updated driver profile #{dp.id} field '{field}' to '{value}'",
        )
        sess.add(log_entry)
        await sess.flush()

        return DriverDetailDTO(
            driver_id=dp.id,
            user_id=driver_user.id,
            telegram_id=driver_user.telegram_id,
            full_name=driver_user.full_name or "Unknown Driver",
            phone_number=driver_user.phone_number or "N/A",
            vehicle_type=dp.vehicle_type,
            plate_number=dp.plate_number,
            license_number=dp.license_number,
            status=dp.status,
            availability=dp.availability.value,
            rating_avg=dp.rating_avg,
            total_deliveries=dp.total_deliveries,
            username=driver_user.username,
            account_status=driver_user.account_status.value,
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


async def remove_driver(
    dto: RemoveDriverDTO,
    session: Optional[AsyncSession] = None,
) -> None:
    """Remove a driver record and demote the associated user.

    This function performs the following steps atomically:
        1. Verifies the requesting user is an admin.
        2. Loads the driver profile and associated user.
        3. Deletes the ``DriverProfile`` record.
        4. Resets the user's role to ``None`` (removing driver privileges).
        5. Creates an ``AdminActionLog`` entry for audit purposes.

    Args:
        dto (RemoveDriverDTO): Payload containing the driver ID and admin
            Telegram ID.
        session (Optional[AsyncSession]): Optional existing database session.

    Returns:
        None

    Raises:
        ValidationError: If the caller is not an admin.
        NotFoundError: If the driver profile does not exist.

    Calls / Depends on:
        - ``sqlalchemy.select``, ``delete``
        - ``bot.core.models.user.User``
        - ``bot.core.models.driver_profile.DriverProfile``
        - ``bot.core.models.admin_action_log.AdminActionLog``
        - ``bot.core.constants.enums.AdminActionType``
        - ``bot.core.exceptions.ValidationError``, ``NotFoundError``

    Called by:
        - ``bot/admin/handler.py``: ``handle_remove_driver_execute``
    """
    async def _execute(sess: AsyncSession):
        admin_stmt = select(User).where(User.telegram_id == dto.admin_telegram_id)
        admin_res = await sess.execute(admin_stmt)
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user or admin_user.role != UserRole.ADMIN:
            raise ValidationError("Admin permission required.")

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

        await sess.delete(dp)
        driver_user.role = None

        log_entry = AdminActionLog(
            admin_id=admin_user.id,
            action_type=AdminActionType.REMOVE_DRIVER,
            target_user_id=driver_user.id,
            details=f"Removed driver profile #{dp.id} for user #{driver_user.id}",
        )
        sess.add(log_entry)
        await sess.flush()

    if session is not None:
        await _execute(session)
    else:
        async with async_session() as sess:
            try:
                await _execute(sess)
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise
