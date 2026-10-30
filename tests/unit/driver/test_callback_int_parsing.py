"""Regression tests for backlog P1 #22 — unguarded ``int()`` parsing of callback
data in ``bot/driver/handler.py``.

``process_driver_accept`` and ``process_driver_reject`` parsed the request id from the
``driver_accept:<id>`` / ``driver_reject:<id>`` payload with a bare
``int(callback.data.split(":")[1])``.  A malformed payload raised an unhandled
``ValueError`` / ``IndexError`` out of the handler (-> generic "something went
wrong").  Both handlers now guard the parse and answer ``ErrorMessages.INVALID_INPUT``.

There is no happy-path positive test here because the accept/reject bodies open a DB
session and drive ``RequestService``; the existing ``test_handler.py`` suite already
covers those flows.  These tests pin the guard itself, which is the defect being fixed.
"""
from unittest.mock import AsyncMock, MagicMock

from bot.core.constants.messages import ErrorMessages
from bot.driver.handler import process_driver_accept, process_driver_reject


def _make_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = 42
    cb.from_user.username = "driver_user"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


class TestDriverAcceptCallbackIntParsing:
    async def test_missing_request_id_answers_invalid_input(self):
        # "driver_accept:" -> int("") -> ValueError
        cb = _make_callback("driver_accept:")
        session = AsyncMock()

        await process_driver_accept(cb, session=session)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True

    async def test_non_numeric_request_id_answers_invalid_input(self):
        cb = _make_callback("driver_accept:abc")
        session = AsyncMock()

        await process_driver_accept(cb, session=session)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True


class TestDriverRejectCallbackIntParsing:
    async def test_missing_request_id_answers_invalid_input(self):
        cb = _make_callback("driver_reject:")
        session = AsyncMock()

        await process_driver_reject(cb, session=session)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True

    async def test_non_numeric_request_id_answers_invalid_input(self):
        cb = _make_callback("driver_reject:abc")
        session = AsyncMock()

        await process_driver_reject(cb, session=session)

        cb.answer.assert_awaited_once()
        assert cb.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        assert cb.answer.call_args.kwargs.get("show_alert") is True
