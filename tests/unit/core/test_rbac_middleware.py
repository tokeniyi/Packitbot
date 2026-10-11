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
    ) as mock_authorized:
        result = await middleware(handler, update, {"user": user, "session": session})

    mock_authorized.assert_awaited_once_with(session=session, telegram_id=user.telegram_id)

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
    ) as mock_authorized:
        result = await middleware(handler, update, {"user": user, "session": session})

    mock_authorized.assert_awaited_once_with(session=session, telegram_id=user.telegram_id)
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
# 11. Non-command text allowed for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_command_text_allowed_for_unregistered_user():
    """Non-command text from a user with role=None passes through so that
    callback handlers (like role-selection buttons) and text-button flows
    can process it."""
    middleware = RBACMiddleware()
    update = _make_mock_update("some free text")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 12. Pre-authorized user with no role allowed for /register_driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_preauthorized_user_without_role_allowed_for_register_driver():
    """A user with role=None who is on the authorized list may invoke
    /register_driver — the pre-auth check bypasses the role requirement."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/register_driver")
    user = _make_user_mock(role=None, tid=42)
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
# 13. Non-command text allowed for registered user
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


# ---------------------------------------------------------------------------
# 14. Unknown command rejected with "unknown command" message
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_command_blocked_for_registered_user():
    """A registered user running an unknown command receives the
    'unknown command' message instead of a permission error."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/nonexistent")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 15. Unknown command rejected even for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_command_blocked_for_unregistered_user():
    """An unregistered user running an unknown command receives the
    'unknown command' message, not the 'registration incomplete' one."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/nonexistent")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 16. Unknown command rejected even for admin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_command_blocked_for_admin():
    """Even an admin running an unknown command receives 'unknown command'."""
    middleware = RBACMiddleware()
    update = _make_mock_update("/nonexistent")
    user = _make_user_mock(role=UserRole.ADMIN)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.message.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 17. Public callback (home) allowed for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_callback_allowed_for_unregistered_user():
    """A user with role=None can still invoke the 'home' callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("home")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 18. Public callback (role:student) allowed for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_role_selection_callback_allowed_for_unregistered_user():
    """A user with role=None can still invoke the role selection callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("role:student")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 19. Driver callback blocked for unregistered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_callback_blocked_for_unregistered_user():
    """A user with role=None is blocked from driver_accept callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_accept:123")
    user = _make_user_mock(role=None)
    session = _make_session_mock()

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 20. Driver callback blocked for student
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_callback_blocked_for_student():
    """A STUDENT is blocked from driver_accept callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_accept:123")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 21. Driver callback allowed for driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_callback_allowed_for_driver():
    """A fully-registered DRIVER can invoke driver_accept callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_accept:123")
    user = _make_user_mock(role=UserRole.DRIVER)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 22. Admin callback blocked for driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_callback_blocked_for_driver():
    """A DRIVER is blocked from admin callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("admin_req_page:1")
    user = _make_user_mock(role=UserRole.DRIVER)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 23. Admin callback allowed for admin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_callback_allowed_for_admin():
    """A fully-registered ADMIN can invoke admin callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("admin_req_page:1")
    user = _make_user_mock(role=UserRole.ADMIN)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 24. Student callback blocked for driver
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_callback_blocked_for_driver():
    """A DRIVER is blocked from student callback (my_req_detail)."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("my_req_detail:123")
    user = _make_user_mock(role=UserRole.DRIVER)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 25. Student callback allowed for student
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_callback_allowed_for_student():
    """A fully-registered STUDENT can invoke my_req_detail callback."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("my_req_detail:123")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result == "ok"
    handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# 26. Unknown callback blocked for registered user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_callback_blocked():
    """A registered user invoking an unknown callback receives 'unknown callback'."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("unknown_action:123")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=True)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 27. Driver registration callback requires pre-authorization
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_submit_reg_callback_requires_preauth():
    """A user trying to submit driver registration must be pre-authorized."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_submit_reg")
    user = _make_user_mock(role=None)
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
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 28. Driver registration callback allowed when pre-authorized
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_submit_reg_callback_allowed_when_preauthorized():
    """A pre-authorized user can submit driver registration."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_submit_reg")
    user = _make_user_mock(role=None)
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
# 29. Driver callback blocked for driver without approved profile
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_driver_callback_blocked_for_driver_without_profile():
    """A user with DRIVER role but no approved profile is blocked from driver callbacks."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("driver_accept:123")
    user = _make_user_mock(role=UserRole.DRIVER)
    session = _make_session_mock(profile_exists=False)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


# ---------------------------------------------------------------------------
# 30. Student callback blocked for student without profile
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_callback_blocked_for_student_without_profile():
    """A user with STUDENT role but no profile is blocked from student callbacks."""
    middleware = RBACMiddleware()
    update = _make_mock_callback("my_req_detail:123")
    user = _make_user_mock(role=UserRole.STUDENT)
    session = _make_session_mock(profile_exists=False)

    handler = AsyncMock(return_value="ok")

    result = await middleware(handler, update, {"user": user, "session": session})

    assert result is None
    handler.assert_not_awaited()
    update.callback_query.answer.assert_awaited_once()


def _make_mock_callback(callback_data: str) -> MagicMock:
    """Build a mock Update with a callback query containing *callback_data*."""
    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.is_bot = False

    mock_callback_query = MagicMock()
    mock_callback_query.from_user = mock_user
    mock_callback_query.data = callback_data
    mock_callback_query.answer = AsyncMock()

    mock_update = MagicMock()
    mock_update.message = None
    mock_update.callback_query = mock_callback_query
    mock_update.inline_query = None
    mock_update.poll_answer = None
    mock_update.poll = None
    mock_update.shipping_query = None
    mock_update.pre_checkout_query = None
    mock_update.my_chat_member = None
    mock_update.chat_member = None
    mock_update.chosen_inline_result = None
    return mock_update
