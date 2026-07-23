from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from bot.core.constants.enums import (
    AccountStatus,
    AdminActionType,
    DriverAvailability,
    DriverStatus,
    LuggageSize,
    RequestStatus,
    UserRole,
    VerificationStatus,
)
from bot.core.db.base_class import Base
from bot.core.models.admin_action_log import AdminActionLog
from bot.core.models.admin_profile import AdminProfile
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.models.status_log import RequestStatusLog
from bot.core.models.student_profile import StudentProfile
from bot.core.models.user import User
from bot.core.repositories.base_repository import BaseRepository


@pytest.mark.asyncio
async def test_user_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    repo = BaseRepository(session, User)
    user = await repo.create(
        telegram_id=12345,
        username="testuser",
        full_name="Test User",
        phone_number="+234801234567",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()
    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.telegram_id == 12345
    assert fetched.full_name == "Test User"
    assert fetched.role == UserRole.STUDENT
    assert fetched.account_status == AccountStatus.ACTIVE
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_student_profile_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    user = await user_repo.create(
        telegram_id=1,
        full_name="Student",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    profile_repo = BaseRepository(session, StudentProfile)
    profile = await profile_repo.create(
        user_id=user.id,
        matric_number="123/456",
        hall_of_residence="Esther Hall",
        verification_status=VerificationStatus.UNVERIFIED,
    )
    await session.commit()
    fetched = await profile_repo.get_by_id(profile.id)
    assert fetched.matric_number == "123/456"
    assert fetched.hall_of_residence == "Esther Hall"
    assert fetched.verification_status == VerificationStatus.UNVERIFIED
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_driver_profile_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    user = await user_repo.create(
        telegram_id=2,
        full_name="Driver",
        role=UserRole.DRIVER,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    profile_repo = BaseRepository(session, DriverProfile)
    profile = await profile_repo.create(
        user_id=user.id,
        vehicle_type="Sedan",
        plate_number="ABC123",
        license_number="DL12345",
        status=DriverStatus.PENDING_APPROVAL,
        availability=DriverAvailability.OFFLINE,
    )
    await session.commit()
    fetched = await profile_repo.get_by_id(profile.id)
    assert fetched.plate_number == "ABC123"
    assert fetched.status == DriverStatus.PENDING_APPROVAL
    assert fetched.availability == DriverAvailability.OFFLINE
    assert fetched.rating_avg == 0.0
    assert fetched.total_deliveries == 0
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_profile_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    admin_user = await user_repo.create(
        telegram_id=3,
        full_name="Admin User",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    added_by = await user_repo.create(
        telegram_id=4,
        full_name="Super Admin",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    profile_repo = BaseRepository(session, AdminProfile)
    profile = await profile_repo.create(
        user_id=admin_user.id,
        added_by_admin_id=added_by.id,
    )
    await session.commit()
    fetched = await profile_repo.get_by_id(profile.id)
    assert fetched.user_id == admin_user.id
    assert fetched.added_by_admin_id == added_by.id
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_delivery_request_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    student = await user_repo.create(
        telegram_id=5,
        full_name="Student",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    repo = BaseRepository(session, DeliveryRequest)
    req = await repo.create(
        student_id=student.id,
        pickup_detail="Block B, room 12",
        dropoff_address="Lagos, Ikeja",
        dropoff_landmark="Near gate",
        hall_of_residence="Esther Hall",
        recipient_name="John Doe",
        recipient_phone="+234809876543",
        luggage_size=LuggageSize.MEDIUM,
        luggage_count=2,
        preferred_date=date.today() + timedelta(days=1),
        preferred_time_window="8am-11am",
        status=RequestStatus.PENDING,
    )
    await session.commit()
    fetched = await repo.get_by_id(req.id)
    assert fetched.pickup_detail == "Block B, room 12"
    assert fetched.dropoff_address == "Lagos, Ikeja"
    assert fetched.luggage_size == LuggageSize.MEDIUM
    assert fetched.luggage_count == 2
    assert fetched.status == RequestStatus.PENDING
    assert fetched.hall_of_residence == "Esther Hall"
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_request_status_log_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    student = await user_repo.create(
        telegram_id=6,
        full_name="Student",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    req_repo = BaseRepository(session, DeliveryRequest)
    req = await req_repo.create(
        student_id=student.id,
        pickup_detail="Block B",
        dropoff_address="Ikeja",
        hall_of_residence="Esther Hall",
        recipient_name="John",
        recipient_phone="+234801234567",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        preferred_date=date.today(),
        preferred_time_window="8am-11am",
        status=RequestStatus.PENDING,
    )
    await session.commit()

    repo = BaseRepository(session, RequestStatusLog)
    log = await repo.create(
        request_id=req.id,
        new_status=RequestStatus.ASSIGNED,
    )
    await session.commit()
    fetched = await repo.get_by_id(log.id)
    assert fetched.request_id == req.id
    assert fetched.new_status == RequestStatus.ASSIGNED
    assert fetched.old_status is None
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_feedback_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    student = await user_repo.create(
        telegram_id=7,
        full_name="Student",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    req_repo = BaseRepository(session, DeliveryRequest)
    req = await req_repo.create(
        student_id=student.id,
        pickup_detail="Block B",
        dropoff_address="Ikeja",
        hall_of_residence="Esther Hall",
        recipient_name="John",
        recipient_phone="+234801234567",
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        preferred_date=date.today(),
        preferred_time_window="8am-11am",
        status=RequestStatus.DELIVERED,
    )
    await session.commit()

    repo = BaseRepository(session, Feedback)
    feedback = await repo.create(
        request_id=req.id,
        student_id=student.id,
        rating=5,
        comment="Great service!",
    )
    await session.commit()
    fetched = await repo.get_by_id(feedback.id)
    assert fetched.request_id == req.id
    assert fetched.student_id == student.id
    assert fetched.rating == 5
    assert fetched.comment == "Great service!"
    await session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_action_log_round_trip():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    user_repo = BaseRepository(session, User)
    admin = await user_repo.create(
        telegram_id=8,
        full_name="Admin",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    target = await user_repo.create(
        telegram_id=9,
        full_name="Target",
        role=UserRole.STUDENT,
        account_status=AccountStatus.ACTIVE,
    )
    await session.commit()

    repo = BaseRepository(session, AdminActionLog)
    log = await repo.create(
        admin_id=admin.id,
        action_type=AdminActionType.BAN_USER,
        target_user_id=target.id,
        details="Spam",
    )
    await session.commit()
    fetched = await repo.get_by_id(log.id)
    assert fetched.admin_id == admin.id
    assert fetched.action_type == AdminActionType.BAN_USER
    assert fetched.target_user_id == target.id
    assert fetched.details == "Spam"
    await session.close()
    await engine.dispose()
