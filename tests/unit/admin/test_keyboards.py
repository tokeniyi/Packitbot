import pytest
from unittest.mock import MagicMock

from aiogram.types import InlineKeyboardButton

from bot.admin.keyboards import driver_approval_keyboard, pending_drivers_list_keyboard
from bot.core.utils.callback_data import AdminDriverApproval


class TestDriverApprovalKeyboard:
    def test_returns_inline_keyboard(self):
        kb = driver_approval_keyboard(driver_id=1)
        assert kb.inline_keyboard is not None

    def test_has_approve_and_reject_buttons(self):
        kb = driver_approval_keyboard(driver_id=1)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "✅ Approve" in texts
        assert "❌ Reject" in texts

    def test_approve_callback_format(self):
        kb = driver_approval_keyboard(driver_id=1)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.text == "✅ Approve":
                    data = AdminDriverApproval.unpack(btn.callback_data)
                    assert data.action == "approve"
                    assert data.driver_id == 1

    def test_reject_callback_format(self):
        kb = driver_approval_keyboard(driver_id=1)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.text == "❌ Reject":
                    data = AdminDriverApproval.unpack(btn.callback_data)
                    assert data.action == "reject"
                    assert data.driver_id == 1


class TestPendingDriversListKeyboard:
    def test_returns_inline_keyboard(self):
        drivers = [
            MagicMock(driver_id=1, full_name="Alice"),
            MagicMock(driver_id=2, full_name="Bob"),
        ]
        kb = pending_drivers_list_keyboard(drivers, page=1, total_pages=1)
        assert kb.inline_keyboard is not None

    def test_lists_driver_names(self):
        drivers = [
            MagicMock(driver_id=1, full_name="Alice"),
            MagicMock(driver_id=2, full_name="Bob"),
        ]
        kb = pending_drivers_list_keyboard(drivers, page=1, total_pages=1)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "📋 Alice (ID: 1)" in texts
        assert "📋 Bob (ID: 2)" in texts

    def test_has_pagination_when_multiple_pages(self):
        drivers = []
        kb = pending_drivers_list_keyboard(drivers, page=2, total_pages=3)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "⬅️ Prev" in texts
        assert "➡️ Next" in texts

    def test_no_pagination_when_single_page(self):
        drivers = []
        kb = pending_drivers_list_keyboard(drivers, page=1, total_pages=1)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "⬅️ Prev" not in texts
        assert "➡️ Next" not in texts
