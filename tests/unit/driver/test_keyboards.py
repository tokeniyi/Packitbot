import pytest

from bot.core.constants.enums import DriverAvailability
from bot.driver.keyboards import (
    driver_pending_menu,
    driver_persistent_menu,
    driver_registration_review_keyboard,
    vehicle_type_keyboard,
)


class TestVehicleTypeKeyboard:
    def test_returns_inline_keyboard(self):
        kb = vehicle_type_keyboard()
        assert kb.inline_keyboard is not None

    def test_has_vehicle_options(self):
        kb = vehicle_type_keyboard()
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Sedan 🚗" in texts
        assert "SUV 🚙" in texts
        assert "Bus 🚌" in texts
        assert "Bike 🏍️" in texts
        assert "Van 🚐" in texts

    def test_has_cancel_button(self):
        kb = vehicle_type_keyboard()
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "❌ Cancel" in texts

    def test_callback_data_format(self):
        kb = vehicle_type_keyboard()
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.text != "❌ Cancel":
                    assert btn.callback_data.startswith("driver_vtype:")


class TestDriverRegistrationReviewKeyboard:
    def test_returns_inline_keyboard(self):
        kb = driver_registration_review_keyboard()
        assert kb.inline_keyboard is not None

    def test_has_edit_buttons(self):
        kb = driver_registration_review_keyboard()
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Full Name ✏️" in texts
        assert "Phone ✏️" in texts
        assert "Vehicle Type ✏️" in texts
        assert "Plate Number ✏️" in texts
        assert "License Number ✏️" in texts

    def test_has_submit_and_cancel(self):
        kb = driver_registration_review_keyboard()
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "✅ Submit Registration" in texts
        assert "❌ Cancel" in texts


class TestDriverPendingMenu:
    def test_returns_reply_keyboard(self):
        kb = driver_pending_menu()
        assert kb.keyboard is not None

    def test_has_check_status_button(self):
        kb = driver_pending_menu()
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🔄 Check Approval Status" in texts


class TestDriverPersistentMenu:
    def test_returns_reply_keyboard(self):
        kb = driver_persistent_menu()
        assert kb.keyboard is not None

    def test_available_shows_go_offline(self):
        kb = driver_persistent_menu(DriverAvailability.AVAILABLE)
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🔴 Go Offline" in texts

    def test_offline_shows_go_available(self):
        kb = driver_persistent_menu(DriverAvailability.OFFLINE)
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🟢 Go Available" in texts

    def test_busy_shows_go_offline(self):
        kb = driver_persistent_menu(DriverAvailability.BUSY)
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🔴 Go Offline" in texts
