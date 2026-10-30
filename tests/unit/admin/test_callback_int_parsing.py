"""Regression tests for backlog P1 #22 — unguarded ``int()`` parsing of callback
data in ``bot/admin/handler.py``.

Before the fix, ``handle_select_request_for_assignment`` parsed its request id with a
bare ``int(callback.data.split(":")[1])``.  A malformed payload (``admin_assign_req:``
or ``admin_assign_req:abc``) raised an unhandled ``ValueError`` / ``IndexError`` out of
the handler, which the global error handler at ``bot/main.py`` surfaced as a generic
"something went wrong" alert with no clue as to the real cause.

The handler now guards the parse and answers ``ErrorMessages.INVALID_INPUT``.  Each
malformed-payload test is a tripwire: with the guard absent the ``await`` itself
raises, so the test fails; with the guard present the handler answers ``INVALID_INPUT``
and the downstream service is never called.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from bot.admin.handler import handle_select_request_for_assignment
from bot.core.constants.enums import UserRole
from bot.core.constants.messages import ErrorMessages


def _make_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = 42
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _make_admin_user() -> MagicMock:
    user = MagicMock()
    user.telegram_id = 42
    user.id = 99
    user.role = UserRole.ADMIN
    return user


class TestAssignRequestCallbackIntParsing:
    async def test_missing_request_id_answers_invalid_input(self):
        # "admin_assign_req:" -> split yields ["admin_assign_req", ""] -> int("") -> ValueError
        cb = _make_callback("admin_assign_req:")
        session = AsyncMock()

        with patch(
            "bot.admin.handler.get_available_drivers_ranked",
            new_callable=AsyncMock,
        ) as mock_ranked:
            await handle_select_request_for_assignment(
                cb, user=_make_admin_user(), session=session
            )

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True
        mock_ranked.assert_not_awaited()

    async def test_non_numeric_request_id_answers_invalid_input(self):
        cb = _make_callback("admin_assign_req:abc")
        session = AsyncMock()

        with patch(
            "bot.admin.handler.get_available_drivers_ranked",
            new_callable=AsyncMock,
        ) as mock_ranked:
            await handle_select_request_for_assignment(
                cb, user=_make_admin_user(), session=session
            )

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True
        mock_ranked.assert_not_awaited()

    async def test_valid_request_id_still_proceeds(self):
        """Positive control: a well-formed payload is not short-circuited by the guard."""
        cb = _make_callback("admin_assign_req:5")
        session = AsyncMock()

        with patch(
            "bot.admin.handler.get_available_drivers_ranked",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_ranked:
            await handle_select_request_for_assignment(
                cb, user=_make_admin_user(), session=session
            )

        mock_ranked.assert_awaited_once_with(session=session)
        # None drivers -> the "no drivers" warning, *not* INVALID_INPUT
        cb.answer.assert_awaited_once()
        assert "No active/available approved drivers" in cb.answer.call_args.args[0]
