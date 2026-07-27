import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.core.services.notification_service import notify_driver_approval_status
from bot.core.constants.messages import MSG_NOTIFY_DRIVER_APPROVED, MSG_NOTIFY_DRIVER_REJECTED


class TestNotifyDriverApprovalStatus:
    async def test_sends_approval_message(self):
        bot = MagicMock()
        bot.send_message = AsyncMock()

        result = await notify_driver_approval_status(
            bot=bot, telegram_id=123456789, approved=True
        )

        assert result is True
        bot.send_message.assert_awaited_once_with(
            chat_id=123456789,
            text=MSG_NOTIFY_DRIVER_APPROVED,
            parse_mode="Markdown",
        )

    async def test_sends_rejection_message(self):
        bot = MagicMock()
        bot.send_message = AsyncMock()

        result = await notify_driver_approval_status(
            bot=bot, telegram_id=123456789, approved=False, reason="Incomplete docs"
        )

        assert result is True
        call_kwargs = bot.send_message.call_args[1]
        assert "Incomplete docs" in call_kwargs["text"]
        assert call_kwargs["parse_mode"] == "Markdown"

    async def test_returns_false_on_send_failure(self):
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=Exception("Blocked user"))

        result = await notify_driver_approval_status(
            bot=bot, telegram_id=123456789, approved=True
        )

        assert result is False
