"""Regression guard: the shared ``/start`` role handler requires ``session``.

``process_role_driver`` used to declare ``session=None``. The session comes
from ``DbSessionMiddleware``, so the default is removed (P1 #18 follow-up).
"""

import inspect

import pytest

from bot.common import start

HANDLERS = [start.process_role_driver]


@pytest.mark.parametrize("func", HANDLERS, ids=lambda f: f.__name__)
def test_start_handler_session_is_required(func):
    param = inspect.signature(func).parameters["session"]
    assert param.default is inspect.Parameter.empty, (
        f"{func.__name__} must not default session to None"
    )
