"""Regression tests for backlog P1 #22 — unguarded ``int()`` parsing of callback
data in ``bot/student/handlers/feedback.py``.

``process_rating_selection`` parsed both the request id and the rating from the
``rate:<request_id>:<rating>`` payload with bare ``int(parts[1])`` / ``int(parts[2])``.
A malformed payload (``rate:abc:4``, ``rate:5`` with a missing rating, ``rate:5:abc``)
raised an unhandled ``ValueError`` / ``IndexError`` after the callback had already been
answered, bubbling up as a generic error and leaving the feedback workflow stuck.

The handler now guards the parses and answers ``ErrorMessages.INVALID_INPUT`` via
``callback.message`` (the callback was already acknowledged, so we must not call
``callback.answer`` a second time).  The valid-payload test is a positive control
proving the guard does not short-circuit a well-formed rating selection.
"""
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext

from bot.core.constants.messages import ErrorMessages
from bot.student.handlers.feedback import process_rating_selection


def _make_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = 7
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


class TestRatingSelectionCallbackIntParsing:
    async def test_non_numeric_request_id_answers_invalid_input(self):
        cb = _make_callback("rate:abc:4")
        state = AsyncMock(spec=FSMContext)

        await process_rating_selection(cb, state)

        cb.message.answer.assert_awaited_once()
        assert cb.message.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        state.update_data.assert_not_awaited()

    async def test_missing_rating_answers_invalid_input(self):
        # "rate:5" -> parts has length 2 -> parts[2] -> IndexError
        cb = _make_callback("rate:5")
        state = AsyncMock(spec=FSMContext)

        await process_rating_selection(cb, state)

        cb.message.answer.assert_awaited_once()
        assert cb.message.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        state.update_data.assert_not_awaited()

    async def test_non_numeric_rating_answers_invalid_input(self):
        cb = _make_callback("rate:5:abc")
        state = AsyncMock(spec=FSMContext)

        await process_rating_selection(cb, state)

        cb.message.answer.assert_awaited_once()
        assert cb.message.answer.call_args.args[0] == ErrorMessages.INVALID_INPUT
        state.update_data.assert_not_awaited()

    async def test_valid_payload_still_proceeds(self):
        """Positive control: a well-formed ``rate:5:4`` drives the state machine."""
        cb = _make_callback("rate:5:4")
        state = AsyncMock(spec=FSMContext)

        await process_rating_selection(cb, state)

        state.update_data.assert_awaited_once_with(request_id=5, rating=4)
        state.set_state.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()
