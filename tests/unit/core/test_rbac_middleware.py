"""Unit tests for the RBAC middleware.

These tests verify the role-based access control rules applied to
slash-commands before they reach downstream handlers.  They cover:

1. Public commands allowed for unregistered users.
2. Unregistered users (role == None) blocked from role-specific commands.
3. Student without a profile blocked from /request.
4. Student with a profile allowed for /request.
5. DRIVER not on the authorized list blocked from /register_driver.
6. DRIVER on the authorized list allowed for /register_driver.
7. Student blocked from an admin-only command (/admin).
8. Admin allowed to use /admin.
9. Fully registered DRIVER allowed for /register_driver.
10. No user in data → passes through.
11. Non-command text allowed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.constants.enums import AccountStatus, UserRole
from bot.core.middlewares.rbac import RBACMiddleware


def _make_user_mock(role=None, tid: int = 123):
    """Build a lightweight mock of the ORM ``User`` injected by AuthMiddleware."""
    user = MagicMock()
    user.id = 1
    user.telegram_id = tid
    user.role = role
    user.account_status = AccountStatus.ACTIVE
    return user


def _make_mock_update(text: str = "", has_callback: bool = False) -> MagicMock:
    """Build a mock Update-like object with a message containing *text*.

    Mirrors the ``_make_mock_update`` helper in ``test_middlewares.py``
    so that ``event.message.answer`` is an ``AsyncMock`` rather than a
    real aiogram method that requires a bot instance.
    """
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.is_bot = False

    mock_message = MagicMock()
    mock_message.from_user = mock_user
    mock_message.text = text
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


def _make_session_mock(profile_exists: bool = False):
    """Create an ``AsyncMock`` session whose ``execute`` returns a result
    whose ``scalar_one_or_none`` returns a truthy profile or ``None``."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(
        return_value=("profile" if profile_exists else None)
    )
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# 1. Public command /start allowed for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_command_allowed_for_unregistered_user():
    """A user with role=None can still invoke /start."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/start")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. Unregistered user blocked from /admin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unregistered_user_blocked_from_admin_command():
    """A user with role=None is blocked from /admin."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/admin")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Student with no profile blocked from /request
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_without_profile_blocked_from_request():
    """STUDENT role but no StudentProfile row -> blocked from /request."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/request")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=False)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. Student with profile allowed for /request
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_with_profile_allowed_for_request():
    """STUDENT role with a StudentProfile row -> /request reaches the handler."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/request")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. DRIVER not in authorized list blocked from /register_driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_not_authorized_blocked_from_register_driver():
    """DRIVER role without profile; not on the authorized list -> blocked."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/register_driver")
    user = _make_user_mock(role=UserRole.DRIVER, tid=42)
    session = _make_session_mock(profile_exists=False)

    handler = AsyncMock(return_value="ok")

    with patch(
        "bot.driver.service.is_authorized_driver",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6. DRIVER in authorized list allowed for /register_driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_authorized_allowed_for_register_driver():
    """DRIVER role without profile; on the authorized list -> handler runs."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/register_driver")
    user = _make_user_mock(role=UserRole.DRIVER, tid=42)
    session = _make_session_mock(profile_exists=False)

    handler = AsyncMock(return_value="ok")

    with patch(
        "bot.driver.service.is_authorized_driver",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. Student blocked from admin command /admin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_blocked_from_admin_command():
    """A fully-registered STUDENT may not invoke /admin."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/admin")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. Admin allowed to use /admin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_allowed_for_admin_command():
    """ADMIN role with AdminProfile -> /admin reaches the handler."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/admin")
    user = _make_user_mock(role=UserRole.ADMIN)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 9. Fully registered DRIVER allowed for /register_driver (has profile)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_registered_driver_allowed_for_register_driver():
    """A DRIVER with a profile (already registered) may still invoke
    /register_driver -- the handler will show already-registered info."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/register_driver")
    user = _make_user_mock(role=UserRole.DRIVER, tid=42)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 10. No user in data -> passes through
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_user_passes_through():
    """When ``user`` is absent from data the middleware is a no-op."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/admin")
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 11. Non-command text blocked for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_command_text_blocked_for_unregistered_user():
    """Non-command text from a user with role=None is blocked because the
    user is not registered — only public slash-commands bypass the gate."""
    middleware = RBACMiddleware()
    update = _make_mock_update("some free text")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()


# ---------------------------------------------------------------------------
# 12. Non-command text allowed for registered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_command_text_allowed_for_registered_user():
    """Non-command text from a fully-registered STUDENT passes through so that
    text-button / reply-keyboard triggers reach the handler."""
    middleware = RBACMiddleware()
    update = _make_mock_update("📦 New Request")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()
