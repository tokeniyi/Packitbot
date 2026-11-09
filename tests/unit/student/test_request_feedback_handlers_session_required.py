"""Regression guard: student request and feedback handlers require ``session``.

These handlers used to declare ``session=None``. ``DbSessionMiddleware``
always injects the session, so the parameter must be required (P1 #18
follow-up). ``show_my_requests_list`` keeps its ``page`` default.
"""

import inspect

import pytest

from bot.student.handlers import feedback, requests

HANDLERS = [
    requests.submit_request_creation,
    requests.show_my_requests_list,
    requests.my_requests_page_callback,
    requests.show_request_detail,
    requests.start_request_edit,
    requests.confirm_request_update,
    requests.prompt_cancel_request,
    requests.confirm_cancel_request,
    feedback.prompt_feedback_rating,
    feedback.process_feedback_skip_comment,
    feedback.process_feedback_comment_message,
]


@pytest.mark.parametrize("func", HANDLERS, ids=lambda f: f.__name__)
def test_request_feedback_handler_session_is_required(func):
    param = inspect.signature(func).parameters["session"]
    assert param.default is inspect.Parameter.empty, (
        f"{func.__name__} must not default session to None"
    )
