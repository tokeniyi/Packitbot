"""Regression tests for P1 #17 stage 2: admin legacy-Markdown messages.

Legacy ``parse_mode="Markdown"`` treats ``_``, ``*``, ````` and ``[`` as entity markers.
User-entered and database values containing them used to make Telegram reject the
whole admin message. Values now go through ``escape_markdown`` (or ``markdown_code``
inside code spans) at each call site, and these tests pin that behaviour.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot.admin.handler import (
    handle_unban_user,
    handle_view_driver_detail,
)
from bot.core.constants.enums import UserRole
from bot.core.models.user import User
from bot.core.utils.callback_data import AdminUserAction
from bot.core.utils.formatters import escape_markdown, markdown_code

NASTY = "a_b*c`d[e"


# --- helper behaviour -------------------------------------------------------

def test_escape_markdown_prefixes_each_special_character():
    assert escape_markdown("a_b*c[d") == "a\\_b\\*c\\[d"


def test_escape_markdown_escapes_backtick():
    assert escape_markdown("x`y") == "x\\`y"


def test_escape_markdown_leaves_plain_text_alone():
    assert escape_markdown("Ada Okafor 0801") == "Ada Okafor 0801"


def test_escape_markdown_none_becomes_empty_string():
    assert escape_markdown(None) == ""


def test_markdown_code_replaces_backticks_with_apostrophe():
    assert markdown_code("x`y") == "x'y"


def test_markdown_code_none_becomes_empty_string():
    assert markdown_code(None) == ""


# --- handler call sites -----------------------------------------------------

def _make_callback(data: str = "") -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = 1
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = MagicMock()
    return cb


def _admin() -> User:
    user = MagicMock(spec=User)
    user.telegram_id = 42
    user.id = 99
    user.role = UserRole.ADMIN
    return user


async def test_driver_detail_escapes_name_username_and_plate():
    callback = _make_callback(data="admin_driver_approval:view:1")
    detail = MagicMock()
    detail.full_name = NASTY
    detail.phone_number = "08012345678"
    detail.vehicle_type = "sedan"
    detail.plate_number = "AB_12*"
    detail.license_number = "DL_001"
    detail.status.value = "pending_approval"
    detail.username = "ada_user"
    detail.driver_id = 1

    with patch(
        "bot.admin.handler.get_driver_application_detail",
        new_callable=AsyncMock,
        return_value=detail,
    ):
        await handle_view_driver_detail(callback, MagicMock(), session=MagicMock(), user=_admin())

    sent = callback.message.edit_text.call_args.args[0]
    assert "a\\_b\\*c\\`d\\[e" in sent
    assert "@ada\\_user" in sent
    assert "AB\\_12\\*" in sent
    assert "DL\\_001" in sent
    # The raw, unescaped name must not appear.
    assert "a_b*c" not in sent


async def test_unban_message_escapes_name_and_handles_missing_name():
    callback = _make_callback(data="admin_user:unban:7")
    updated = MagicMock()
    updated.user_id = 7
    updated.full_name = "Bad_Name*"
    updated.banned_reason = None

    with patch("bot.admin.handler.unban_user", new_callable=AsyncMock, return_value=updated):
        await handle_unban_user(callback, AdminUserAction(action="unban", user_id=7), user=_admin(), session=MagicMock())

    sent = callback.message.edit_text.call_args.args[0]
    assert "Bad\\_Name\\*" in sent
    assert "Bad_Name*" not in sent

    updated.full_name = None
    callback = _make_callback(data="admin_user:unban:7")
    with patch("bot.admin.handler.unban_user", new_callable=AsyncMock, return_value=updated):
        await handle_unban_user(callback, AdminUserAction(action="unban", user_id=7), user=_admin(), session=MagicMock())
    assert "Name:** N/A" in callback.message.edit_text.call_args.args[0]
