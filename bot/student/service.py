"""Student registration and profile management service layer.

This module provides async service functions for student-related operations
including registration, profile retrieval, and registration status checks.
It orchestrates database sessions, validates input, and coordinates with
the repository and model layers.

Function Calls:
    - register_student(telegram_id, username, full_name, hall, phone) -> StudentProfile
    - get_profile(user_id) -> StudentProfile | None
    - is_registered(telegram_id) -> bool

Cross-References:
    - Depends on: bot.core.db.session.async_session, bot.core.models.user.User,
        bot.core.models.student_profile.StudentProfile, bot.core.utils.validators,
        bot.core.constants.enums.AccountStatus, bot.core.constants.enums.UserRole
    - Imported by: bot/student/handler.py, bot/student/handler_registration.py
"""

from typing import Optional

from sqlalchemy import select

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.db.session import async_session
from bot.core.exceptions import ValidationError
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.utils.validators import (
    validate_full_name,
    validate_phone,
)


async def register_student(
    telegram_id: int,
    username: Optional[str],
    full_name: str,
    hall: str,
    phone: Optional[str] = None,
) -> StudentProfile:
    """Register a student user, creating or updating the User and StudentProfile records.

    Validates the full name and phone number, then either updates an existing
    User record or creates a new one. Ensures a corresponding StudentProfile
    exists, creating it if missing. Commits the transaction and refreshes
    the profile before returning.

    Args:
        telegram_id: The unique Telegram user identifier.
        username: Optional Telegram username.
        full_name: The student's full name; validated and normalized.
        hall: The student's hall of residence.
        phone: Optional phone number; validated if provided.

    Returns:
        The persisted StudentProfile record.

    Raises:
        ValidationError: If full_name or phone validation fails.
    """
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

        # Entering / exiting `async with session.begin()` handles
        # automatic commit on success or rollback on exception.
        await session.refresh(profile)
        return profile


async def get_profile(user_id: int) -> Optional[StudentProfile]:
    """Fetch a StudentProfile by the internal user ID.

    Args:
        user_id: The primary key of the related User record.

    Returns:
        The matching StudentProfile if found, otherwise None.
    """
    session = async_session()
    try:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    finally:
        await session.close()


async def is_registered(telegram_id: int) -> bool:
    """Check whether a Telegram user is registered as a student.

    Looks up the user by telegram_id and verifies their role is Student.

    Args:
        telegram_id: The unique Telegram user identifier.

    Returns:
        True if the user exists and has the Student role, False otherwise.
    """
    session = async_session()
    try:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user is not None and user.role == UserRole.STUDENT
    finally:
        await session.close()