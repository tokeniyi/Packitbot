"""Student registration and profile management service layer.

This module provides async service functions for student-related operations
including registration, profile retrieval, profile updates, and statistics.
It orchestrates database sessions, validates input, and coordinates with
the repository and model layers.
"""

from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.constants.enums import AccountStatus, RequestStatus, UserRole, VerificationStatus
from bot.core.db.session import async_session
from bot.core.exceptions import NotFoundError, ValidationError
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.utils.validators import (
    validate_full_name,
    validate_hall,
    validate_phone,
)


async def register_student(
    telegram_id: int,
    username: Optional[str],
    full_name: str,
    hall: str,
    phone: Optional[str] = None,
) -> StudentProfile:
    """Register a student user, creating or updating the User and StudentProfile records."""
    validated_full_name = validate_full_name(full_name)
    validated_phone = validate_phone(phone) if phone else None

    async with async_session() as session:
        async with session.begin():
            # 1. Fetch existing user by telegram_id if present
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # Update existing user attributes
                user.username = username
                user.full_name = validated_full_name
                user.phone_number = validated_phone
                user.role = UserRole.STUDENT
                user.account_status = AccountStatus.ACTIVE
            else:
                # Create a new user record
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    full_name=validated_full_name,
                    phone_number=validated_phone,
                    role=UserRole.STUDENT,
                    account_status=AccountStatus.ACTIVE,
                )
                session.add(user)
                await session.flush()  # Ensures user.id is available

            # 2. Fetch or create the associated StudentProfile
            stmt_profile = select(StudentProfile).where(StudentProfile.user_id == user.id)
            profile_result = await session.execute(stmt_profile)
            profile = profile_result.scalar_one_or_none()

            if profile:
                # Update existing profile
                profile.hall_of_residence = hall
            else:
                # Create profile if missing
                profile = StudentProfile(
                    user_id=user.id,
                    hall_of_residence=hall,
                    verification_status=None,
                )
                session.add(profile)

        await session.refresh(profile)
        return profile


async def get_profile(user_id: int) -> Optional[StudentProfile]:
    """Fetch a StudentProfile by the internal user ID."""
    session = async_session()
    try:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    finally:
        await session.close()


async def is_registered(telegram_id: int) -> bool:
    """Check whether a Telegram user is registered as a student."""
    session = async_session()
    try:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user is not None and user.role == UserRole.STUDENT
    finally:
        await session.close()


async def resolve_user_id(telegram_id: int, session: Optional[AsyncSession] = None) -> Optional[int]:
    """Resolves a Telegram user ID to internal users.id."""
    if session:
        stmt = select(User.id).where(User.telegram_id == telegram_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async with async_session() as s:
        stmt = select(User.id).where(User.telegram_id == telegram_id)
        res = await s.execute(stmt)
        return res.scalar_one_or_none()


async def get_student_profile_with_stats(
    telegram_id: int,
    session: Optional[AsyncSession] = None,
) -> Tuple[Optional[User], Optional[StudentProfile], int, int, int]:
    """Retrieve User, StudentProfile and delivery counts (active, completed, cancelled) for a student."""
    async def _execute_queries(s: AsyncSession):
        user_res = await s.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_res.scalar_one_or_none()
        if not user:
            return None, None, 0, 0, 0

        prof_res = await s.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
        profile = prof_res.scalar_one_or_none()

        active_res = await s.execute(
            select(func.count(DeliveryRequest.id)).where(
                DeliveryRequest.student_id == user.id,
                DeliveryRequest.status.in_(
                    {
                        RequestStatus.PENDING,
                        RequestStatus.ASSIGNED,
                        RequestStatus.ACCEPTED,
                        RequestStatus.EN_ROUTE_TO_PICKUP,
                        RequestStatus.PICKED_UP,
                        RequestStatus.IN_TRANSIT,
                    }
                ),
            )
        )
        active_count = active_res.scalar() or 0

        comp_res = await s.execute(
            select(func.count(DeliveryRequest.id)).where(
                DeliveryRequest.student_id == user.id,
                DeliveryRequest.status == RequestStatus.DELIVERED,
            )
        )
        completed_count = comp_res.scalar() or 0

        canc_res = await s.execute(
            select(func.count(DeliveryRequest.id)).where(
                DeliveryRequest.student_id == user.id,
                DeliveryRequest.status == RequestStatus.CANCELLED,
            )
        )
        cancelled_count = canc_res.scalar() or 0

        return user, profile, active_count, completed_count, cancelled_count

    if session:
        return await _execute_queries(session)
    async with async_session() as s:
        return await _execute_queries(s)


async def update_student_hall(
    telegram_id: int,
    new_hall: str,
    session: Optional[AsyncSession] = None,
) -> StudentProfile:
    """Update student hall of residence."""
    validated_hall = validate_hall(new_hall)

    async def _update(s: AsyncSession):
        user_res = await s.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")

        prof_res = await s.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
        profile = prof_res.scalar_one_or_none()
        if not profile:
            raise NotFoundError("Student profile not found")

        profile.hall_of_residence = validated_hall
        return profile

    if session:
        return await _update(session)
    async with async_session() as s:
        async with s.begin():
            return await _update(s)


async def update_student_phone(
    telegram_id: int,
    new_phone: str,
    session: Optional[AsyncSession] = None,
) -> User:
    """Update student phone number."""
    validated_phone = validate_phone(new_phone)

    async def _update(s: AsyncSession):
        user_res = await s.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")

        user.phone_number = validated_phone
        return user

    if session:
        return await _update(session)
    async with async_session() as s:
        async with s.begin():
            return await _update(s)