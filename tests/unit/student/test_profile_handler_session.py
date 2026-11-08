"""Regression guard for the student profile handlers' session parameter.

The student service functions now require a real ``AsyncSession`` (P1 #18).
The profile handlers used to declare ``session=None``, which would pass
``None`` straight into the service and fail with an obscure ``AttributeError``
if the middleware ever stopped injecting the session. The parameter must be
required so a missing session fails loudly at call time.
"""

import inspect

import pytest

from bot.student.handlers import profile

HANDLERS = [
    profile._show_profile,
    profile.show_profile,
    profile.process_profile_phone_edit,
    profile.process_profile_hall_edit,
]


@pytest.mark.parametrize("handler", HANDLERS, ids=lambda h: h.__name__)
def test_profile_handler_session_is_required(handler):
    param = inspect.signature(handler).parameters["session"]
    assert param.default is inspect.Parameter.empty, (
        f"{handler.__name__} must not default session to None"
    )
