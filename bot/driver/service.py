# bot/driver/service.py
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.constants.enums import AccountStatus, DriverAvailability, DriverStatus, UserRole
from bot.core.db.session import async_session
from bot.core.exceptions import DuplicateResourceError, PackitbotError, ValidationError
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.user import User
from bot.core.utils.validators import (
    validate_full_name,
    validate_license_number,
    validate_phone,
    validate_plate_number,
    validate_vehicle_type,
)
from bot.driver.schemas import RegisterDriverDTO


async def register_driver(
    dto: RegisterDriverDTO,
    session: Optional[AsyncSession] = None,
) -> DriverProfile:
    """Registers a driver with PENDING_APPROVAL status."""
    validated_name = validate_full_name(dto.full_name)
    validated_phone = validate_phone(dto.phone_number)
    validated_vehicle = validate_vehicle_type(dto.vehicle_type)
    validated_plate = validate_plate_number(dto.plate_number)
    validated_license = validate_license_number(dto.license_number)

    async def _execute_register(sess: AsyncSession) -> DriverProfile:
        # Check existing user by telegram_id
        stmt = select(User).where(User.telegram_id == dto.telegram_id)
        result = await sess.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=dto.telegram_id,
                username=dto.username,
                full_name=validated_name,
                phone_number=validated_phone,
                role=UserRole.DRIVER,
                account_status=AccountStatus.ACTIVE,
            )
            sess.add(user)
            await sess.flush()
        else:
            user.full_name = validated_name
            user.phone_number = validated_phone
            user.role = UserRole.DRIVER

        # Check existing driver profile
        stmt_dp = select(DriverProfile).where(DriverProfile.user_id == user.id)
        res_dp = await sess.execute(stmt_dp)
        dp = res_dp.scalar_one_or_none()

        if dp is not None:
            if dp.status == DriverStatus.APPROVED:
                raise PackitbotError("Driver profile is already approved.")
            # Update pending profile details
            dp.vehicle_type = validated_vehicle
            dp.plate_number = validated_plate
            dp.license_number = validated_license
            dp.status = DriverStatus.PENDING_APPROVAL
        else:
            dp = DriverProfile(
                user_id=user.id,
                vehicle_type=validated_vehicle,
                plate_number=validated_plate,
                license_number=validated_license,
                status=DriverStatus.PENDING_APPROVAL,
                availability=DriverAvailability.OFFLINE,
            )
            sess.add(dp)

        try:
            await sess.flush()
        except IntegrityError as e:
            raise DuplicateResourceError("A driver profile with this plate number or license number already exists.") from e

        return dp

    if session is not None:
        return await _execute_register(session)
    else:
        async with async_session() as sess:
            try:
                dp = await _execute_register(sess)
                await sess.commit()
                return dp
            except Exception:
                await sess.rollback()
                raise


async def get_driver_profile_by_telegram_id(
    telegram_id: int,
    session: Optional[AsyncSession] = None,
) -> Optional[DriverProfile]:

    async def _execute_get(sess: AsyncSession) -> Optional[DriverProfile]:
        stmt = (
            select(DriverProfile)
            .join(User, DriverProfile.user_id == User.id)
            .where(User.telegram_id == telegram_id)
        )
        res = await sess.execute(stmt)
        return res.scalar_one_or_none()

    if session is not None:
        return await _execute_get(session)
    else:
        async with async_session() as sess:
            return await _execute_get(sess)


async def set_driver_availability(
    telegram_id: int,
    target_availability: DriverAvailability,
    session: Optional[AsyncSession] = None,
) -> DriverProfile:
    """Sets driver availability status after verifying status and busy constraints."""

    async def _execute_set(sess: AsyncSession) -> DriverProfile:
        profile = await get_driver_profile_by_telegram_id(telegram_id, session=sess)
        if not profile:
            raise PackitbotError("Driver profile not found.")

        if profile.status != DriverStatus.APPROVED:
            raise ValidationError("Only approved drivers can change availability.")

        if profile.availability == DriverAvailability.BUSY:
            raise ValidationError("Cannot manually change availability while on an active delivery.")

        if target_availability == DriverAvailability.BUSY:
            raise ValidationError("BUSY state is system-managed and cannot be set manually.")

        profile.availability = target_availability
        await sess.flush()
        return profile

    if session is not None:
        return await _execute_set(session)
    else:
        async with async_session() as sess:
            try:
                dp = await _execute_set(sess)
                await sess.commit()
                return dp
            except Exception:
                await sess.rollback()
                raise

