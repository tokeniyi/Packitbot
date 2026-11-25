"""Exercise Telegram updates through production routing, RBAC, FSM, and sessions."""

import json
from datetime import date, timedelta
from itertools import count
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.methods import AnswerCallbackQuery, SendMessage, SetMyCommands
from aiogram.types import Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.admin.service import get_stats
from bot.core.config import get_settings
from bot.core.constants.enums import DriverAvailability, DriverStatus, RequestStatus, UserRole
from bot.core.middlewares import db_session as db_middleware
from bot.core.middlewares.auth import AuthMiddleware
from bot.core.middlewares.callback_message import CallbackMessageGuardMiddleware
from bot.core.middlewares.rbac import RBACMiddleware
from bot.core.models.admin_profile import AdminProfile
from bot.core.models.authorized_driver import AuthorizedDriver
from bot.core.models.delivery_request import DeliveryRequest
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.feedback import Feedback
from bot.core.models.user import User
from bot.main import setup_routers

STUDENT = 1001
DRIVER = 1002
ADMIN = 1003


@pytest.fixture
async def telegram(async_engine, monkeypatch):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    monkeypatch.setattr(db_middleware, "async_session", factory)
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    setup_routers(dp)
    dp.update.outer_middleware(db_middleware.DbSessionMiddleware())
    dp.update.outer_middleware(AuthMiddleware(get_settings()))
    dp.update.outer_middleware(RBACMiddleware())
    dp.callback_query.outer_middleware(CallbackMessageGuardMiddleware())
    bot = Bot(token="123:test")
    transport = AsyncMock(return_value=True)
    monkeypatch.setattr(bot.session, "make_request", transport)
    update_ids = count(1)

    async def send(user_id, *, text=None, data=None):
        update_id = next(update_ids)
        actor = {"id": user_id, "is_bot": False, "first_name": "Test"}
        message = {
            "message_id": update_id,
            "date": 1_750_000_000,
            "chat": {"id": user_id, "type": "private"},
            "from": actor,
            "text": text or "Keyboard",
        }
        if data is not None:
            payload = {"callback_query": {
                "id": str(update_id),
                "data": data,
                "from": actor,
                "chat_instance": "test",
                "message": message,
            }}
        else:
            if text.startswith("/"):
                message["entities"] = [
                    {"type": "bot_command", "offset": 0, "length": len(text.split()[0])}
                ]
            payload = {"message": message}
        transport.reset_mock()
        await dp.feed_update(bot, Update.model_validate({"update_id": update_id, **payload}))
        return [call.args[1] for call in transport.await_args_list]

    async with factory.begin() as session:
        admin = User(telegram_id=ADMIN, role=UserRole.ADMIN, full_name="Test Admin")
        session.add(admin)
        await session.flush()
        session.add_all([
            AdminProfile(user_id=admin.id),
            AuthorizedDriver(telegram_id=DRIVER, added_by_admin_id=admin.id),
        ])

    yield send, factory, dp, bot

    for router in dp.sub_routers:
        router._parent_router = None
    await bot.session.close()


async def register_student(send):
    await send(STUDENT, text="/start")
    await send(STUDENT, data="role:student")
    await send(STUDENT, text="Test Student")
    await send(STUDENT, data="hall_select:Esther Hall")
    await send(STUDENT, text="08023456789")
    await send(STUDENT, data="review_submit")


async def register_driver(send):
    await send(DRIVER, text="/register_driver")
    await send(DRIVER, data="driver_cancel_reg")
    await send(DRIVER, data="role:driver")
    await send(DRIVER, text="Test Driver")
    await send(DRIVER, text="08023456789")
    await send(DRIVER, data="driver_vtype:sedan")
    await send(DRIVER, text="ABC-123DE")
    await send(DRIVER, text="DL-987654")
    await send(DRIVER, data="driver_submit_reg")


async def create_request(send):
    await send(STUDENT, text="📦 New Request")
    await send(STUDENT, text="Campus main gate")
    await send(STUDENT, text="Room 102, campus residence")
    await send(STUDENT, data="req_skip_landmark")
    await send(STUDENT, data="req_hall:Esther Hall")
    await send(STUDENT, text="Jane Student")
    await send(STUDENT, text="08023456789")
    await send(STUDENT, data="req_size:small")
    await send(STUDENT, text="1")
    expired = (date.today() - timedelta(days=1)).isoformat()
    replies = await send(STUDENT, data=f"req_date:{expired}")
    assert any(isinstance(reply, AnswerCallbackQuery) and reply.show_alert for reply in replies)
    await send(STUDENT, data=f"req_date:{date.today().isoformat()}")
    await send(STUDENT, data="req_time:8am-11am")
    await send(STUDENT, data="req_skip_instructions")
    await send(STUDENT, data="req_submit")


async def test_student_admin_and_driver_complete_delivery(telegram):
    send, factory, _, _ = telegram
    await register_student(send)
    await register_driver(send)
    await create_request(send)

    async with factory() as session:
        request = (await session.scalars(select(DeliveryRequest))).one()
        profile = (await session.scalars(select(DriverProfile))).one()
        assert request.status == RequestStatus.PENDING
        assert profile.status == DriverStatus.PENDING_APPROVAL
        request_id, profile_id, driver_id = request.id, profile.id, profile.user_id

    await send(ADMIN, text="/verify")
    await send(ADMIN, data=f"admin_driver:approve:{profile_id}")
    await send(ADMIN, data=f"admin_driver:reject:{profile_id}")  # Expired review button.
    menu = await send(DRIVER, text="/menu")
    assert all(
        len({item.command for item in reply.commands}) == len(reply.commands)
        for reply in menu if isinstance(reply, SetMyCommands)
    )
    assert any(isinstance(reply, SetMyCommands) for reply in menu)
    await send(DRIVER, text="/duty")
    await send(ADMIN, data=f"admin_assign:{request_id}:{profile_id}")

    async with factory() as session:
        profile = await session.get(DriverProfile, profile_id)
        request = await session.get(DeliveryRequest, request_id)
        assert profile.status == DriverStatus.APPROVED
        assert profile.approved_by_admin_id is not None
        assert profile.availability == DriverAvailability.BUSY
        assert request.status == RequestStatus.ASSIGNED
        assert request.driver_id == driver_id

    replies = await send(DRIVER, text="📋 Assigned Deliveries")
    assert any(
        button.callback_data == f"driver_accept:{request_id}"
        for reply in replies if getattr(getattr(reply, "reply_markup", None), "inline_keyboard", None)
        for row in reply.reply_markup.inline_keyboard for button in row
    )
    await send(DRIVER, data=f"driver_reject:{request_id}")
    async with factory() as session:
        assert (await session.get(DriverProfile, profile_id)).availability == DriverAvailability.AVAILABLE
        assert (await session.get(DeliveryRequest, request_id)).status == RequestStatus.PENDING
        assert (await get_stats(session)).rejected_by_driver_requests == 1

    await send(ADMIN, data=f"admin_assign:{request_id}:{profile_id}")
    await send(DRIVER, data=f"driver_accept:{request_id}")
    for step in ("en_route", "picked_up", "in_transit", "delivered"):
        await send(DRIVER, data=f"driver_step:{step}:{request_id}")

    async with factory() as session:
        request = await session.get(DeliveryRequest, request_id)
        profile = await session.get(DriverProfile, profile_id)
        assert request.status == RequestStatus.DELIVERED
        assert profile.availability == DriverAvailability.AVAILABLE
        assert profile.total_deliveries == 1

    details = await send(STUDENT, data=f"my_req_detail:{request_id}")
    assert any(
        button.callback_data == f"my_req_rate:{request_id}"
        for reply in details if getattr(getattr(reply, "reply_markup", None), "inline_keyboard", None)
        for row in reply.reply_markup.inline_keyboard for button in row
    )
    await send(STUDENT, data=f"my_req_rate:{request_id}")
    await send(STUDENT, data=f"rate:{request_id + 1}:2")  # Older button cannot retarget the form.
    await send(STUDENT, data=f"rate:{request_id}:5")
    await send(STUDENT, data=f"feedback_skip_comment:{request_id}")

    async with factory() as session:
        feedback = (await session.scalars(select(Feedback))).one()
        assert feedback.request_id == request_id
        assert feedback.rating == 5
        assert (await session.get(DriverProfile, profile_id)).rating_avg == 5.0


async def test_student_edits_date_with_redis_compatible_state_and_cancels(telegram):
    send, factory, dp, bot = telegram
    await register_student(send)
    await create_request(send)

    async with factory() as session:
        request_id = (await session.scalars(select(DeliveryRequest.id))).one()

    await send(STUDENT, data=f"my_req_edit:{request_id}")
    await send(STUDENT, data=f"req_update_field:{request_id}:preferred_date")
    new_date = (date.today() + timedelta(days=1)).isoformat()
    await send(STUDENT, text=new_date)
    state = dp.fsm.get_context(bot=bot, chat_id=STUDENT, user_id=STUDENT)
    assert json.loads(json.dumps(await state.get_data()))["changes"]["preferred_date"] == new_date
    await send(STUDENT, data=f"req_update_confirm:{request_id + 1}")
    await send(STUDENT, data=f"req_update_confirm:{request_id}")
    await send(STUDENT, data=f"my_req_cancel_confirm:{request_id}")

    async with factory() as session:
        request = await session.get(DeliveryRequest, request_id)
        assert request.preferred_date.isoformat() == new_date
        assert request.status == RequestStatus.CANCELLED


async def test_admin_broadcast_cancel_and_promotion_use_real_routes(telegram):
    send, factory, _, _ = telegram
    await register_student(send)

    await send(ADMIN, text="/broadcast")
    await send(ADMIN, data="broadcast_audience:students")
    await send(ADMIN, text="/cancel")
    replies = await send(ADMIN, data="broadcast_confirm:send")
    assert not any(isinstance(reply, SendMessage) and reply.chat_id == STUDENT for reply in replies)

    await send(ADMIN, text="/broadcast")
    await send(ADMIN, data="broadcast_audience:students")
    prefix = "[Campus update: _ordinary text* "
    content = prefix.ljust(4096, "x")
    preview = await send(ADMIN, text=content)
    assert any(isinstance(reply, SendMessage) and reply.text == content for reply in preview)
    replies = await send(ADMIN, data="broadcast_confirm:send")
    assert [(reply.chat_id, reply.text) for reply in replies if isinstance(reply, SendMessage)] == [
        (STUDENT, content)
    ]

    async with factory() as session:
        user_id = await session.scalar(select(User.id).where(User.telegram_id == STUDENT))
    await send(ADMIN, data=f"admin_user:promote:{user_id}")
    await send(STUDENT, data="role:student")  # A previously displayed role picker cannot demote an admin.
    replies = await send(STUDENT, text="/admin")
    assert any(isinstance(reply, SendMessage) and "Management Panel" in reply.text for reply in replies)
    async with factory() as session:
        assert (await session.get(User, user_id)).role == UserRole.ADMIN
        assert await session.scalar(select(AdminProfile).where(AdminProfile.user_id == user_id))
