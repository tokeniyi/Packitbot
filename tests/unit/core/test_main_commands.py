"""Regression tests for ``bot.main.set_bot_commands`` (backlog item P1 #8).

Bug under test
--------------
``_apply_menu_for_chats`` used to contain::

    await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=chat_id))
    if bot.set_my_commands():          # <-- second coroutine, never awaited
        print("Successfully set ...")
    else:
        print("Failed to set ...")

``Bot.set_my_commands`` is a coroutine function, so the bare ``if``
expression created a *new* coroutine object and never awaited it.  Two
consequences:

1. The object is always truthy, so the ``Failed`` branch was unreachable and a
   success/failure report could never be printed.
2. Every never-awaited coroutine emits a ``RuntimeWarning`` at garbage
   collection time — one per registered chat, on every bot boot.

The fix deletes the dead block and replaces the raw ``print`` with a
``logger.info`` call so the success path is observable through the project
logger (which is what the surrounding error branch already uses).

Test strategy
-------------
``bot.main`` performs real DB work at call time, so the two chat-id lookups
are patched out and a ``Bot`` double is used.

The decisive assertion is the *await count*.  With the fixture below the
function must await ``set_my_commands`` exactly 8 times:

    1  default scope
    2  students   (patched lookup returns [111, 222])
    2  drivers    (patched lookup returns [111, 222])
    3  admins     (patched [111, 222] union settings [999])

The old buggy code issued those 8 awaited calls *plus* 7 un-awaited coroutine
objects, so any second call trips the regression assertion.
"""

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault

from bot.core.constants.commands import (
    ADMIN_COMMANDS,
    DEFAULT_COMMANDS,
    DRIVER_COMMANDS,
    STUDENT_COMMANDS,
)
from bot.main import set_bot_commands

# 1 default + 2 students + 2 drivers + 3 admins.
EXPECTED_AWAIT_COUNT = 8

# Per-chat menus: everything except the single default scope.
EXPECTED_CHAT_SCOPE_COUNT = 7


def _make_bot() -> MagicMock:
    """A Bot double whose ``set_my_commands`` is an awaitable AsyncMock."""
    bot = MagicMock()
    bot.set_my_commands = AsyncMock(return_value=True)
    return bot


def _patched_lookups():
    """Patch the two chat-id lookups that feed the role menus."""
    return (
        patch("bot.main.get_user_chats_by_role", new=AsyncMock(return_value=[111, 222])),
        patch("bot.main.get_admin_chats_from_settings", return_value=[999]),
    )


async def test_set_my_commands_awaits_exactly_one_call_per_chat():
    """The success path must not create a second, un-awaited coroutine.

    An extra call to ``set_my_commands`` means the old dead ``if`` block is
    back, and a ``RuntimeWarning`` fires when the coroutine is collected.
    """
    bot = _make_bot()
    p_students, p_admins = _patched_lookups()
    with p_students, p_admins:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await set_bot_commands(bot)

    assert bot.set_my_commands.await_count == EXPECTED_AWAIT_COUNT, (
        "set_my_commands must be awaited exactly once per target scope; "
        "an extra call means an un-awaited coroutine was created"
    )
    never_awaited = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not never_awaited, (
        f"RuntimeWarning raised: {[str(w.message) for w in never_awaited]}"
    )


async def test_set_bot_commands_logs_instead_of_printing(capsys):
    """Success reporting must go through the logger, not bare ``print``.

    The old code called ``print`` directly, which bypasses the project
    logger and its PII scrubbing.  After the fix nothing reaches stdout.
    """
    bot = _make_bot()
    p_students, p_admins = _patched_lookups()
    with p_students, p_admins:
        await set_bot_commands(bot)

    assert capsys.readouterr().out == ""


async def test_set_bot_commands_applies_default_and_role_scopes():
    """Each scope must be requested with the right command list and scope object."""
    bot = _make_bot()
    p_students, p_admins = _patched_lookups()
    with p_students, p_admins:
        await set_bot_commands(bot)

    calls = bot.set_my_commands.await_args_list
    commands_by_role = [c.args[0] for c in calls]

    assert DEFAULT_COMMANDS in commands_by_role
    assert STUDENT_COMMANDS in commands_by_role
    assert DRIVER_COMMANDS in commands_by_role
    assert ADMIN_COMMANDS in commands_by_role

    # ``scope`` is always passed as a keyword argument.
    scopes = [c.kwargs["scope"] for c in calls]
    assert sum(isinstance(s, BotCommandScopeDefault) for s in scopes) == 1
    assert sum(isinstance(s, BotCommandScopeChat) for s in scopes) == EXPECTED_CHAT_SCOPE_COUNT

    # Every chat-scoped call must target one of the patched chat ids.
    chat_ids = {s.chat_id for s in scopes if isinstance(s, BotCommandScopeChat)}
    assert chat_ids == {111, 222, 999}


async def test_per_chat_failure_is_caught_and_loop_continues(caplog):
    """A raising per-chat ``set_my_commands`` must be caught, not crash the loop.

    Confirms the existing ``try/except`` around each chat is preserved: one
    unreachable chat is logged as a warning for each role, the remaining
    chats are still processed, and every scope is still attempted exactly
    once (the count stays at the happy-path total).
    """
    bot = _make_bot()
    ok = object()

    async def _flaky(commands, scope):
        # The default scope succeeds; one specific chat always fails.
        if isinstance(scope, BotCommandScopeChat) and scope.chat_id == 111:
            raise RuntimeError("telegram unavailable")
        return ok

    bot.set_my_commands = AsyncMock(side_effect=_flaky)
    p_students, p_admins = _patched_lookups()
    with p_students, p_admins:
        with caplog.at_level("WARNING", logger="bot.core.middlewares.logging"):
            await set_bot_commands(bot)  # must not raise

    # Every scope is still attempted exactly once — a failing chat does not
    # abort the loop and does not trigger a second (un-awaited) call.
    assert bot.set_my_commands.await_count == EXPECTED_AWAIT_COUNT

    # The failure is reported once per role for the offending chat id.
    failures = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(failures) == 3, f"expected 3 warnings (one per role), got {len(failures)}"
    assert all("chat_id=111" in r.getMessage() for r in failures)
    assert {r.getMessage().split()[3] for r in failures} == {"student", "driver", "admin"}
