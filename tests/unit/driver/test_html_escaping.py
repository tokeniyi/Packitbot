"""Regression tests for P1 #17 stage 2c: driver-side HTML messages escape user input.

``bot/driver/handler.py`` sends several ``parse_mode="HTML"`` messages that
interpolate student- and driver-entered values (pickup detail, hall, dropoff,
recipient, names, phone numbers, instructions). A value such as ``<b>x</b>``
used to change the formatting of the message, and a malformed one made Telegram
reject it. Each site below now goes through ``escape_html``.

These tests drive the four handlers with mocked sessions and services, then
assert the text that would be sent contains the escaped payload and not the raw
markup. They pin the behaviour per site: accept, status update, active-delivery
dashboard, and the student notification sent on accept.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.constants.enums import LuggageSize, RequestStatus
from bot.core.utils.formatters import escape_html
from bot.driver.handler import (
    active_delivery_dashboard_handler,
    process_delivery_status_step,
    process_driver_accept,
)

PAYLOAD = "<b>pwned</b> & <a href='x'>link</a>"
ESCAPED = escape_html(PAYLOAD)


def _result(*, one=None, first=None):
    """A stand-in for an ``AsyncSession.execute`` result."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = one
    res.scalar_one.return_value = one
    res.scalars.return_value.first.return_value = first
    return res


def _session(*results):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(results))
    return session


def _student():
    return SimpleNamespace(full_name=PAYLOAD, phone_number=PAYLOAD, telegram_id=99)


def _request(status=RequestStatus.ACCEPTED):
    return SimpleNamespace(
        id=7,
        status=status,
        pickup_detail=PAYLOAD,
        hall_of_residence=PAYLOAD,
        dropoff_address=PAYLOAD,
        dropoff_landmark=PAYLOAD,
        recipient_name=PAYLOAD,
        recipient_phone=PAYLOAD,
        special_instructions=PAYLOAD,
        luggage_size=LuggageSize.SMALL,
        luggage_count=1,
        student=_student(),
        driver=SimpleNamespace(full_name=PAYLOAD, phone_number=PAYLOAD),
    )


def _driver_user():
    return SimpleNamespace(id=5, full_name="Driver", phone_number="08000000000")


def _callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = 42
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = MagicMock()
    cb.bot.send_message = AsyncMock()
    return cb


def _service(updated=None):
    svc = MagicMock()
    svc.transition_status = AsyncMock(return_value=(updated, None))
    return svc


async def test_accept_escapes_driver_message_fields():
    req = _request()
    session = _session(_result(one=_driver_user()), _result(one=req))
    cb = _callback("driver_accept:7")

    with patch("bot.driver.handler.RequestService", return_value=_service(req)):
        await process_driver_accept(cb, session=session)

    text = cb.message.edit_text.call_args.args[0]
    assert "<b>pwned</b>" not in text
    assert "<a href" not in text
    # pickup, hall, dropoff, recipient name and phone, student name and phone.
    assert text.count(ESCAPED) == 7
    assert "<b>Assignment Accepted!</b>" in text


async def test_accept_escapes_student_notification_driver_fields():
    req = _request()
    session = _session(_result(one=_driver_user()), _result(one=req))
    cb = _callback("driver_accept:7")

    with patch("bot.driver.handler.RequestService", return_value=_service(req)):
        await process_driver_accept(cb, session=session)

    notif = cb.bot.send_message.call_args.kwargs["text"]
    assert "<b>pwned</b>" not in notif
    assert "• Name: " + ESCAPED in notif
    assert "• Phone: " + ESCAPED in notif
    assert "<b>Driver Accepted Your Request!</b>" in notif


async def test_status_update_escapes_message_fields():
    req = _request(status=RequestStatus.PICKED_UP)
    # Calls: driver lookup, then request re-fetch (no driver profile for PICKED_UP).
    session = _session(_result(one=_driver_user()), _result(one=req))
    cb = _callback("driver_step:picked_up:7")

    with patch("bot.driver.handler.RequestService", return_value=_service(req)):
        await process_delivery_status_step(cb, session=session)

    text = cb.message.edit_text.call_args.args[0]
    assert "<b>pwned</b>" not in text
    assert "<a href" not in text
    assert text.count(ESCAPED) == 7
    assert "<b>🔄 Status Updated: Picked Up</b>" in text


async def test_active_dashboard_escapes_message_fields():
    req = _request(status=RequestStatus.IN_TRANSIT)
    session = _session(_result(one=_driver_user()), _result(first=req))
    message = MagicMock()
    message.from_user.id = 42
    message.answer = AsyncMock()

    await active_delivery_dashboard_handler(message, session=session)

    text = message.answer.call_args.args[0]
    assert "<b>pwned</b>" not in text
    assert "<a href" not in text
    # pickup, hall, dropoff, landmark, recipient name, phone, instructions,
    # student name, student phone.
    assert text.count(ESCAPED) == 9
    assert "<b>Current Delivery Dashboard</b>" in text
