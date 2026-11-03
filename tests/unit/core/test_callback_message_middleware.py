"""Tests for CallbackMessageGuardMiddleware (P1 #21 stage 1).

Covers the middleware in isolation and, more importantly, through a real
aiogram ``Dispatcher`` with a nested router, to confirm the observer-level
middleware guards handlers on sub-routers.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import CallbackQuery, Chat, InaccessibleMessage, Message, Update, User

from bot.core.constants.messages import ErrorMessages
from bot.core.middlewares.callback_message import CallbackMessageGuardMiddleware

CHAT = Chat(id=42, type="private")
USER = User(id=42, is_bot=False, first_name="Tester")


def _callback(message, data: str = "admin_driver_detail:1") -> CallbackQuery:
    return CallbackQuery(
        id="cbq-1",
        from_user=USER,
        chat_instance="ci-1",
        data=data,
        message=message,
    )


def _real_message() -> Message:
    return Message(
        message_id=7,
        date=datetime.now(timezone.utc),
        chat=CHAT,
        text="menu",
    )


def _inaccessible_message() -> InaccessibleMessage:
    return InaccessibleMessage(chat=CHAT, message_id=7)


@pytest.fixture
def answer_mock():
    with patch.object(CallbackQuery, "answer", new_callable=AsyncMock) as mock:
        yield mock


class TestCallbackMessageGuardMiddleware:
    async def test_real_message_is_forwarded(self, answer_mock):
        middleware = CallbackMessageGuardMiddleware()
        handler = AsyncMock(return_value="handled")
        event = _callback(_real_message())

        result = await middleware(handler, event, {})

        assert result == "handled"
        handler.assert_awaited_once()
        answer_mock.assert_not_awaited()

    async def test_inaccessible_message_is_blocked_with_alert(self, answer_mock):
        middleware = CallbackMessageGuardMiddleware()
        handler = AsyncMock()
        event = _callback(_inaccessible_message())

        result = await middleware(handler, event, {})

        assert result is None
        handler.assert_not_awaited()
        answer_mock.assert_awaited_once_with(ErrorMessages.MESSAGE_EXPIRED, show_alert=True)

    async def test_missing_message_is_blocked_with_alert(self, answer_mock):
        middleware = CallbackMessageGuardMiddleware()
        handler = AsyncMock()
        event = _callback(None)

        result = await middleware(handler, event, {})

        assert result is None
        handler.assert_not_awaited()
        answer_mock.assert_awaited_once_with(ErrorMessages.MESSAGE_EXPIRED, show_alert=True)

    async def test_non_callback_event_passes_through(self, answer_mock):
        middleware = CallbackMessageGuardMiddleware()
        handler = AsyncMock(return_value="ok")
        event = _real_message()

        result = await middleware(handler, event, {})

        assert result == "ok"
        handler.assert_awaited_once()
        answer_mock.assert_not_awaited()

    def test_expired_message_text_is_user_facing(self):
        assert ErrorMessages.MESSAGE_EXPIRED.startswith("⌛")
        assert "start again" in ErrorMessages.MESSAGE_EXPIRED


class TestGuardThroughDispatcher:
    """The middleware is registered on the dispatcher's callback observer.

    A handler on a nested router that calls ``edit_text`` must be shielded
    from an ``InaccessibleMessage`` (which has no ``edit_text``) and must run
    normally for a real message.
    """

    @staticmethod
    def _build(calls: list[str], guarded: bool) -> tuple[Dispatcher, Bot]:
        dp = Dispatcher()
        router = Router(name="admin-like")

        @router.callback_query(F.data.startswith("admin_driver_detail:"))
        async def detail_handler(callback: CallbackQuery) -> None:
            calls.append("called")
            await callback.message.edit_text("detail")

        dp.include_router(router)
        if guarded:
            dp.callback_query.outer_middleware(CallbackMessageGuardMiddleware())
        return dp, Bot(token="123456:TEST-TOKEN")

    @staticmethod
    def _update(message) -> Update:
        return Update(update_id=1, callback_query=_callback(message))

    async def test_handler_not_called_for_inaccessible_message(self, answer_mock):
        calls: list[str] = []
        dp, bot = self._build(calls, guarded=True)

        await dp.feed_update(bot, self._update(_inaccessible_message()))

        assert calls == []
        answer_mock.assert_awaited_once_with(ErrorMessages.MESSAGE_EXPIRED, show_alert=True)

    async def test_handler_runs_for_real_message(self, answer_mock):
        calls: list[str] = []
        dp, bot = self._build(calls, guarded=True)

        with patch.object(Message, "edit_text", new_callable=AsyncMock) as edit:
            await dp.feed_update(bot, self._update(_real_message()))

        assert calls == ["called"]
        edit.assert_awaited_once_with("detail")
        answer_mock.assert_not_awaited()

    async def test_unguarded_dispatcher_reaches_handler_with_inaccessible_message(self, answer_mock):
        """Fail-before check: without the guard the handler is reached and crashes.

        This documents the bug the middleware fixes. The handler's
        ``edit_text`` call raises AttributeError on InaccessibleMessage.
        """
        calls: list[str] = []
        dp, bot = self._build(calls, guarded=False)

        with pytest.raises(AttributeError, match="edit_text"):
            await dp.feed_update(bot, self._update(_inaccessible_message()))

        assert calls == ["called"]
