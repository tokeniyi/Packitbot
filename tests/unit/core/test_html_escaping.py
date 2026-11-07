"""Regression tests for P1 #17: user input must be escaped in HTML-mode messages.

Messages sent with ``parse_mode="HTML"`` interpret ``<``, ``>`` and ``&`` as
markup. Student-entered values (pickup detail, recipient name, instructions,
and so on) used to be interpolated raw, so a value such as ``<b>x</b>`` changed
the formatting of the message, and a malformed one made Telegram reject it.

After the fix every such value goes through ``escape_html``, and these tests
pin that behaviour at the rendering functions.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bot.core.constants.enums import LuggageSize, RequestStatus
from bot.core.utils.formatters import escape_html
from bot.student.handlers.requests import (
    _format_request_detail,
    _show_request_review,
)

PAYLOAD = "<b>pwned</b> & <a href='x'>link</a>"
ESCAPED = "&lt;b&gt;pwned&lt;/b&gt; &amp; &lt;a href='x'&gt;link&lt;/a&gt;"


def test_escape_html_escapes_markup_and_ampersand():
    assert escape_html(PAYLOAD) == ESCAPED


def test_escape_html_none_becomes_empty_string():
    assert escape_html(None) == ""


def test_escape_html_converts_non_strings():
    assert escape_html(42) == "42"


def test_escape_html_leaves_plain_text_unchanged():
    assert escape_html("Hall 3, Room 12") == "Hall 3, Room 12"


def _request(**overrides):
    base = dict(
        id=7,
        status=RequestStatus.PENDING,
        luggage_size=LuggageSize.SMALL,
        pickup_detail=PAYLOAD,
        hall_of_residence=PAYLOAD,
        dropoff_address=PAYLOAD,
        dropoff_landmark=PAYLOAD,
        recipient_name=PAYLOAD,
        recipient_phone=PAYLOAD,
        luggage_count=1,
        preferred_date="2026-11-10",
        preferred_time_window=PAYLOAD,
        special_instructions=PAYLOAD,
        driver=None,
        cancelled_by=None,
        cancellation_reason=PAYLOAD,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_request_detail_escapes_user_fields():
    text = _format_request_detail(_request())

    assert "<b>pwned</b>" not in text
    assert "<a href" not in text
    assert text.count(ESCAPED) >= 8


def test_request_detail_still_renders_its_own_markup():
    text = _format_request_detail(_request())

    assert "<b>Request Detail #7</b>" in text
    assert "<b>Pickup Detail:</b>" in text


def test_request_detail_escapes_driver_and_vehicle_fields():
    driver = SimpleNamespace(
        full_name=PAYLOAD,
        phone_number=PAYLOAD,
        driver_profile=SimpleNamespace(vehicle_type=PAYLOAD, plate_number=PAYLOAD),
    )
    text = _format_request_detail(_request(driver=driver))

    assert "<b>pwned</b>" not in text
    assert "Vehicle: " + ESCAPED in text


async def test_request_review_escapes_user_entered_values():
    state = MagicMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={
            "pickup_detail": PAYLOAD,
            "dropoff_address": PAYLOAD,
            "dropoff_landmark": None,
            "hall_of_residence": "Hall A",
            "recipient_name": PAYLOAD,
            "recipient_phone": "08000000000",
            "luggage_size": "small",
            "luggage_count": 1,
            "preferred_date": "2026-11-10",
            "preferred_time_window": "morning",
            "special_instructions": PAYLOAD,
        }
    )
    # A plain (non-CallbackQuery) target takes the ``target.answer`` branch.
    target = AsyncMock()

    await _show_request_review(target, state)

    sent = target.answer.call_args.args[0]
    assert "<b>pwned</b>" not in sent
    assert sent.count(ESCAPED) == 4
    assert "<b>Delivery Request Review</b>" in sent
    assert "<b>Landmark:</b> None" in sent
