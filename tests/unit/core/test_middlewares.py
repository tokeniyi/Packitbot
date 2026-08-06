import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, Message, Update, User

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.middlewares.auth import AuthMiddleware
from bot.core.middlewares.db_session import DbSessionMiddleware
from bot.core.middlewares.throttling import ThrottlingMiddleware


"""Unit tests for core middlewares and common handlers.

This module contains pytest test cases for the
authentication, database session, and throttling
middlewares, as well as common handler functions
for start, help, about, and fallback flows.

Test Functions:
    - test_db_session_middleware_rolls_back_on_exception
    - test_db_session_middleware_commits_on_success
    - test_auth_middleware_creates_user_on_first_update
    - test_auth_middleware_short_circuits_banned_user
    - test_throttling_middleware_denies_rapid_updates
    - test_start_handler_shows_role_buttons
    - test_help_handler_responds
    - test_about_handler_responds
    - test_fallback_handler_replies_with_home

Cross-References:
    - Depends on: pytest, unittest.mock, aiogram types,
        bot.core.middlewares.auth, bot.core.middlewares.db_session,
        bot.core.middlewares.throttling, bot.common.start, bot.common.help,
        bot.common.fallback
    - Imported by: pytest runner
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_update(user_id: int = 1, text: str = "hello") -> Update:
    """Build a minimal aiogram Update object for middleware testing.

    Args:
        user_id: The Telegram user ID to embed in the mock message.
        text: The text content of the mock message.

    Returns:
        A minimal Update object with a Message containing the given user.
    """
    chat = Chat(id=1, type="private")
    user = User(id=user_id, is_bot=False, first_name="Test", username="t")
    message = Message(
        message_id=1,
        date=datetime.utcnow(),
        chat=chat,
        from_user=user,
        text=text,
    )
    return Update(update_id=1, message=message)


def _make_fake_session():
    """Create an AsyncMock SQLAlchemy session with common methods mocked.

    Returns:
        An AsyncMock session with execute, commit, rollback, close, flush, and add methods.
    """
    session = AsyncMock()
    session.in_transaction = MagicMock(return_value=True)
    session.close = AsyncMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


def _make_mock_update(user_id: int = 1, mock_answer: bool = True) -> MagicMock:
    """Build a mock Update-like object for lightweight handler testing.

    Args:
        user_id: The Telegram user ID to embed in the mock.
        mock_answer: Whether to mock the answer method on the message.

    Returns:
        A MagicMock object mimicking an aiogram Update.
    """
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_bot = False
    mock_user.first_name = "Test"
    mock_user.username = "t"

    mock_message = MagicMock()
    mock_message.from_user = mock_user
    if mock_answer:
        mock_message.answer = AsyncMock()

    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.callback_query = None
    mock_update.inline_query = None
    mock_update.poll_answer = None
    mock_update.poll = None
    mock_update.shipping_query = None
    mock_update.pre_checkout_query = None
    mock_update.my_chat_member = None
    mock_update.chat_member = None
    mock_update.chosen_inline_result = None

    return mock_update


# ---------------------------------------------------------------------------
# 1. DbSessionMiddleware rolls back on handler exception
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_db_session_middleware_rolls_back_on_exception(monkeypatch):
    """Verify that DbSessionMiddleware rolls back and closes session on handler exception."""
    fake_session = _make_fake_session()
    fake_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    def fake_async_session():
        return fake_session

    monkeypatch.setattr("bot.core.middlewares.db_session.async_session", fake_async_session)

    middleware = DbSessionMiddleware()

    async def fake_handler(event, data):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await middleware(fake_handler, _make_update(), {})

    fake_session.rollback.assert_awaited_once()
    fake_session.commit.assert_not_called()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_db_session_middleware_commits_on_success(monkeypatch):
    """Verify that DbSessionMiddleware commits and closes session on successful handler execution."""
    fake_session = _make_fake_session()
    fake_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    def fake_async_session():
        return fake_session

    monkeypatch.setattr("bot.core.middlewares.db_session.async_session", fake_async_session)

    middleware = DbSessionMiddleware()

    async def fake_handler(event, data):
        return "ok"

    result = await middleware(fake_handler, _make_update(), {})
    assert result == "ok"
    fake_session.commit.assert_awaited_once()
    fake_session.rollback.assert_not_called()
    fake_session.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. AuthMiddleware creates a new User on first-ever update
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_middleware_creates_user_on_first_update(monkeypatch):
    """Verify that AuthMiddleware persists a new User when no user exists yet."""
    settings = MagicMock()
    settings.seed_admin_telegram_ids = ""

    fake_session = _make_fake_session()
    fake_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    async def fake_get_or_create(self, session, telegram_id):
        fake_user = MagicMock()
        fake_user.telegram_id = telegram_id
        fake_user.account_status = AccountStatus.ACTIVE
        fake_user.role = None
        session.add(fake_user)
        await session.flush()
        return fake_user

    def fake_async_session():
        return fake_session

    monkeypatch.setattr("bot.core.middlewares.auth.async_session", fake_async_session)
    monkeypatch.setattr(AuthMiddleware, "_get_or_create_user", fake_get_or_create)

    middleware = AuthMiddleware(settings)

    async def fake_handler(event, data):
        return "handled"

    result = await middleware(fake_handler, _make_update(user_id=42), {"session": fake_session})

    assert result == "handled"
    fake_session.add.assert_called_once()
    fake_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. AuthMiddleware short-circuits banned users before any handler executes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_middleware_short_circuits_banned_user(monkeypatch):
    """Verify that AuthMiddleware rejects banned users without invoking downstream handlers."""
    settings = MagicMock()
    settings.seed_admin_telegram_ids = ""

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.telegram_id = 99
    fake_user.account_status = AccountStatus.BANNED
    fake_user.role = UserRole.STUDENT

    fake_session = _make_fake_session()
    fake_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=fake_user))
    )

    async def fake_get_or_create(self, session, telegram_id):
        return fake_user

    def fake_async_session():
        return fake_session

    monkeypatch.setattr("bot.core.middlewares.auth.async_session", fake_async_session)
    monkeypatch.setattr(AuthMiddleware, "_get_or_create_user", fake_get_or_create)

    middleware = AuthMiddleware(settings)

    async def fake_handler(event, data):
        return "should_not_be_called"

    mock_update = _make_mock_update(user_id=99, mock_answer=True)
    mock_update.message.from_user.id = 99
    with patch("bot.core.middlewares.auth.HomeButton", return_value=MagicMock()):
        result = await middleware(fake_handler, mock_update, {"session": fake_session})

    assert result is None
    mock_update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. ThrottlingMiddleware drops rapid-fire updates beyond configured rate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_throttling_middleware_denies_rapid_updates():
    """Verify that ThrottlingMiddleware blocks updates when rate limit is exhausted."""
    settings = MagicMock()
    settings.default_throttle_rate = 0  # effectively no tokens regenerate

    middleware = ThrottlingMiddleware(settings)
    middleware.tokens = {}

    mock_update = _make_mock_update(user_id=1, mock_answer=True)
    mock_update.message.from_user.id = 1

    async def fake_handler(event, data):
        return "ok"

    # First call should pass
    result1 = await middleware(fake_handler, mock_update, {})
    assert result1 == "ok"

    # Immediate second call should be blocked (0 tokens regenerate)
    result2 = await middleware(fake_handler, mock_update, {})
    assert result2 is None
    mock_update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. /start shows Student/Driver buttons, no typing required
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_start_handler_shows_role_buttons():
    """Verify that /start presents a menu with Student and Driver role options."""
    from bot.common.start import cmd_start

    fake_user = MagicMock()
    fake_user.role = None

    fake_bot = AsyncMock()  # <--- Added bot mock
    message = AsyncMock()   # <--- Switched to AsyncMock for clean async calls

    state = AsyncMock()
    
    # Pass fake_bot as the missing positional argument
    await cmd_start(message, bot=fake_bot, state=state, user=fake_user)

    # Inspect the reply_markup passed to message.answer
    assert message.answer.called
    _, kwargs = message.answer.call_args
    markup = kwargs.get("reply_markup")

    assert markup is not None
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    texts = [btn.text for btn in buttons]
    assert any("Student" in t for t in texts)
    assert any("Driver" in t for t in texts)


# ---------------------------------------------------------------------------
# 6. /help responds
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_help_handler_responds():
    """Verify that /help handler sends a help message to the user."""
    from bot.common.help import cmd_help

    message = MagicMock()
    message.answer = AsyncMock()
    await cmd_help(message)
    message.answer.assert_awaited_once()
    assert "help" in message.answer.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# 7. /about responds
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_about_handler_responds():
    """Verify that /about handler sends an about message mentioning PackitBot."""
    from bot.common.help import cmd_about

    message = MagicMock()
    message.answer = AsyncMock()
    await cmd_about(message)
    message.answer.assert_awaited_once()
    assert "packitbot" in message.answer.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# 8. Unrecognized input shows fallback message with Home button
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fallback_handler_replies_with_home():
    """Verify that unrecognized input triggers the catch-all fallback with a Home button."""
    from bot.common.fallback import catch_all_message

    message = MagicMock()
    message.answer = AsyncMock()
    message.chat = MagicMock()
    message.chat.id = 1
    message.chat.type = "private"

    await catch_all_message(message)
    message.answer.assert_awaited_once()
