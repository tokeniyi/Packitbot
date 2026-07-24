from typing import Optional

from sqlalchemy import select

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.db.session import async_session
from bot.core.exceptions import ValidationError
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository
from bot.core.utils.validators import (
    validate_full_name,
    validate_phone,
    validate_matric,
)


async def register_student(
    telegram_id: int,
    full_name: str,
    matric_number: str,
    hall: str,
    phone: str,
) -> StudentProfile:
    validated_full_name = validate_full_name(full_name)
    validated_phone = validate_phone(phone)
    validated_matric = validate_matric(matric_number)

    session = async_session()
    try:
        existing = await session.execute(
            select(StudentProfile).where(
                StudentProfile.matric_number == validated_matric
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValidationError(
                "This matriculation number is already registered."
            )

        user = User(
            telegram_id=telegram_id,
            full_name=validated_full_name,
            phone_number=validated_phone,
            role=UserRole.STUDENT,
            account_status=AccountStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()

        profile = StudentProfile(
            user_id=user.id,
            matric_number=validated_matric,
            hall_of_residence=hall,
            verification_status=None,
        )
        session.add(profile)
        await session.flush()
        await session.commit()
        return profile
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_profile(user_id: int) -> Optional[StudentProfile]:
    session = async_session()
    try:
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    finally:
        await session.close()


async def is_registered(telegram_id: int) -> bool:
    session = async_session()
    try:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user is not None and user.role == UserRole.STUDENT
    finally:
        await session.close()