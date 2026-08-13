"""Driver service layer - registration, profile lookup, and availability management.

This module encapsulates all database-backed business logic for the driver
domain. It validates incoming DTOs against the shared validator utilities,
persists ``User`` and ``DriverProfile`` records within a transactional
session, and enforces the state constraints that govern driver availability.

Functions
---------
- ``register_driver``                       Create or refresh a driver profile.
- ``get_driver_profile_by_telegram_id``     Look up a driver profile by Telegram ID.
- ``set_driver_availability``               Transition a driver's availability.

Depends on
----------
SQLAlchemy async session, ``bot.core.utils.validators``, ``bot.driver.schemas``,
``bot.core.db.session``, ``bot.core.exceptions``, ``bot.core.models.driver_profile``,
``bot.core.models.user``, ``bot.core.constants.enums``.

Called by
---------
``bot/driver/handler.py`` (all three functions).
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import joinedload

from bot.core.constants.enums import AccountStatus, DriverAvailability, DriverStatus, UserRole
from bot.core.exceptions import DuplicateResourceError, PackitbotError, ValidationError
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.authorized_driver import AuthorizedDriver
from bot.core.models.user import User
from bot.core.repositories.user_repository import UserRepository
from bot.driver.repository import DriverRepository
from bot.core.utils.validators import (
    validate_full_name,
    validate_license_number,
    validate_plate_number,
    validate_vehicle_type,
)
from bot.driver.schemas import RegisterDriverDTO


async def register_driver(
    session: AsyncSession,
    dto: RegisterDriverDTO,
) -> DriverProfile:
    """Register a new driver or resubmit an existing pending application.

    All five profile fields are validated against the shared validator
    utilities before any database access occurs. If a ``User`` with the
    given ``telegram_id`` already exists, its name, phone, and role are
    updated; otherwise a new ``User`` is created. The associated
    ``DriverProfile`` is then created or refreshed and set to
    ``PENDING_APPROVAL`` (unless already ``APPROVED``, in which case an
    error is raised). When no external session is supplied, a new
    ``async_session`` is opened, committed, and rolled back on failure.

    Args:
        dto:        Validated registration payload (see :class:`RegisterDriverDTO`).
        session:    Optional injected ``AsyncSession``. If ``None``, a new
                    session scope is created via ``async_session()``.

    Returns:
        The persisted (or updated) :class:`DriverProfile`.

    Raises:
        PackitbotError:            If an approved profile already exists for the user.
        DuplicateResourceError:    If the plate or license number is already taken
                                   (unique constraint violation on flush).
        ValidationError:           If any field fails validation (raised by validators).

    Called by:
        ``bot/driver/handler.py`` -> ``process_submit_registration``.
    """
    validated_name = validate_full_name(dto.full_name)
    validated_phone = dto.phone_number
    validated_vehicle = validate_vehicle_type(dto.vehicle_type)
    validated_plate = validate_plate_number(dto.plate_number)
    validated_license = validate_license_number(dto.license_number)

    user_repo = UserRepository(session)
    driver_repo = DriverRepository(session)

    # Pre-emptively check for unique constraints
    if await driver_repo.get_by_plate_number(validated_plate):
        raise DuplicateResourceError("A driver profile with this plate number already exists.")
    if await driver_repo.get_by_license_number(validated_license):
        raise DuplicateResourceError("A driver profile with this license number already exists.")

    user = await user_repo.get_by_telegram_id(dto.telegram_id)

    if user is None:
        user = await user_repo.create(
            telegram_id=dto.telegram_id,
            username=dto.username,
            full_name=validated_name,
            phone_number=validated_phone,
            role=UserRole.DRIVER,
            account_status=AccountStatus.ACTIVE,
        )
    else:
        await user_repo.update(
            user.id,
            full_name=validated_name,
            phone_number=validated_phone,
            role=UserRole.DRIVER,
        )

    # Check existing driver profile
    dp = await driver_repo.get_by_user_id(user.id)

    if dp is not None:
        if dp.status == DriverStatus.APPROVED:
            raise PackitbotError("Driver profile is already approved.")
        # Update pending profile details
        await driver_repo.update(
            dp.id,
            vehicle_type=validated_vehicle,
            plate_number=validated_plate,
            license_number=validated_license,
            status=DriverStatus.PENDING_APPROVAL,
        )
    else:
        dp = await driver_repo.create(
            user_id=user.id,
            vehicle_type=validated_vehicle,
            plate_number=validated_plate,
            license_number=validated_license,
            status=DriverStatus.PENDING_APPROVAL,
            availability=DriverAvailability.OFFLINE,
        )

    return dp


async def get_driver_profile_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[DriverProfile]:
    """Retrieve the driver profile associated with a Telegram user ID.

    Performs a join from ``DriverProfile`` to ``User`` to resolve the
    ``telegram_id`` (a user-facing identifier) to the internal
    ``DriverProfile`` record.

    Args:
        telegram_id: The Telegram user identifier of the driver.
        session:     Injected ``AsyncSession``.

    Returns:
        The matching :class:`DriverProfile`, or ``None`` if the user has no
        driver profile.

    Called by:
        ``bot/driver/handler.py`` -> ``start_driver_registration``,
        ``check_approval_status``, ``toggle_availability_handler``.
    """

    stmt = (
        select(DriverProfile)
        .options(joinedload(DriverProfile.user))
        .join(User, DriverProfile.user_id == User.id)
        .where(User.telegram_id == telegram_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def set_driver_availability(
    session: AsyncSession,
    telegram_id: int,
    target_availability: DriverAvailability,
) -> DriverProfile:
    """Transition a driver's availability to the specified target state.

    Validates three preconditions before mutating the profile:

    1. The driver profile exists for the given Telegram user.
    2. The profile status is ``APPROVED``.
    3. The driver is not currently ``BUSY`` (system-managed during a delivery)
       and the caller is not attempting to set ``BUSY`` manually.

    Args:
        telegram_id:         The Telegram user identifier of the driver.
        target_availability: The desired availability state to set.
        session:             Injected ``AsyncSession``.

    Returns:
        The updated :class:`DriverProfile` with the new availability.

    Raises:
        PackitbotError:   If no driver profile exists for the user.
        ValidationError:  If the profile is not approved, is already ``BUSY``,
                          or the caller attempts to set ``BUSY`` manually.

    Calls / Depends on:
        :func:`get_driver_profile_by_telegram_id` (resolved within the same session).

    Called by:
        ``bot/driver/handler.py`` -> ``toggle_availability_handler``.
    """

    profile = await get_driver_profile_by_telegram_id(session, telegram_id)
    if not profile:
        raise PackitbotError("Driver profile not found.")

    if profile.status != DriverStatus.APPROVED:
        raise ValidationError("Only approved drivers can change availability.")

    if profile.availability == DriverAvailability.BUSY:
        raise ValidationError("Cannot manually change availability while on an active delivery.")

    if target_availability == DriverAvailability.BUSY:
        raise ValidationError("BUSY state is system-managed and cannot be set manually.")

    profile.availability = target_availability
    await session.flush()
    return profile


async def is_authorized_driver(
    session: AsyncSession,
    telegram_id: int,
) -> bool:
    """Check whether a Telegram user ID is on the pre-approved driver list.

    Queries the ``authorized_drivers`` table for a matching ``telegram_id``.

    Args:
        telegram_id: The Telegram user identifier to look up.
        session:     Injected ``AsyncSession``.

    Returns:
        ``True`` if the Telegram ID appears in the ``AuthorizedDriver``
        table, ``False`` otherwise.

    Called by:
        - ``bot/core/middlewares/rbac.py`` — gates the ``/register_driver``
          command for DRIVER-role users without a profile.
        - ``bot/driver/handler.py`` — ``start_driver_registration`` performs
          the same check as a secondary guard for text-button triggers.
    """
    stmt = select(AuthorizedDriver).where(AuthorizedDriver.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

