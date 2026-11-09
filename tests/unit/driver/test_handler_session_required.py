"""Regression guard: driver handlers require an injected ``session``.

The driver handlers used to declare ``session=None``. A missing session then
produced a "session unavailable" reply or, worse, a silent no-op, instead of
failing loudly. ``DbSessionMiddleware`` always injects the session, so the
parameter must be required (P1 #18 follow-up).
"""

import inspect

import pytest

from bot.driver import handler

HANDLERS = [
    handler.start_driver_registration,
    handler.process_submit_registration,
    handler.check_approval_status,
    handler.toggle_availability_handler,
    handler.process_driver_accept,
    handler.active_delivery_dashboard_handler,
    handler.process_delivery_status_step,
    handler.process_driver_reject,
]


@pytest.mark.parametrize("func", HANDLERS, ids=lambda f: f.__name__)
def test_driver_handler_session_is_required(func):
    param = inspect.signature(func).parameters["session"]
    assert param.default is inspect.Parameter.empty, (
        f"{func.__name__} must not default session to None"
    )
