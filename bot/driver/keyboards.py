# bot/driver/keyboards.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.core.constants.enums import DriverAvailability, DriverStatus, RequestStatus



def vehicle_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Sedan 🚗", callback_data="driver_vtype:sedan"),
                InlineKeyboardButton(text="SUV 🚙", callback_data="driver_vtype:suv"),
            ],
            [
                InlineKeyboardButton(text="Bus 🚌", callback_data="driver_vtype:bus"),
                InlineKeyboardButton(text="Bike 🏍️", callback_data="driver_vtype:bike"),
                InlineKeyboardButton(text="Van 🚐", callback_data="driver_vtype:van"),
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="driver_cancel_reg"),
            ],
        ]
    )


def driver_registration_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Full Name ✏️", callback_data="driver_edit:full_name"),
                InlineKeyboardButton(text="Phone ✏️", callback_data="driver_edit:phone_number"),
            ],
            [
                InlineKeyboardButton(text="Vehicle Type ✏️", callback_data="driver_edit:vehicle_type"),
                InlineKeyboardButton(text="Plate Number ✏️", callback_data="driver_edit:plate_number"),
            ],
            [
                InlineKeyboardButton(text="License Number ✏️", callback_data="driver_edit:license_number"),
            ],
            [
                InlineKeyboardButton(text="✅ Submit Registration", callback_data="driver_submit_reg"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="driver_cancel_reg"),
            ],
        ]
    )


def driver_pending_menu() -> ReplyKeyboardMarkup:
    """Restricted menu when driver registration is pending approval or rejected."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Check Approval Status"),
                KeyboardButton(text="ℹ️ Help / Support"),
            ],
        ],
        resize_keyboard=True,
    )


def driver_persistent_menu(availability: DriverAvailability = DriverAvailability.OFFLINE) -> ReplyKeyboardMarkup:
    """Full persistent menu for approved drivers."""
    if availability == DriverAvailability.AVAILABLE:
        toggle_text = "🔴 Go Offline"
    elif availability == DriverAvailability.OFFLINE:
        toggle_text = "🟢 Go Available"
    else:
        # BUSY or default fallback
        toggle_text = "🔴 Go Offline"

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=toggle_text),
                KeyboardButton(text="📋 Assigned Deliveries"),
            ],
            [
                KeyboardButton(text="📊 Active Delivery"),
                KeyboardButton(text="👤 Driver Profile"),
            ],
        ],
        resize_keyboard=True,
    )


def driver_assignment_response_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for driver to accept or reject an assigned delivery request."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Accept", callback_data=f"driver_accept:{request_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"driver_reject:{request_id}"),
            ],
        ]
    )


def delivery_status_update_keyboard(request_id: int, current_status: RequestStatus) -> InlineKeyboardMarkup:
    """Returns contextual single next-step action button keyboard based on current status."""
    buttons: list[list[InlineKeyboardButton]] = []

    if current_status == RequestStatus.ACCEPTED:
        buttons.append([
            InlineKeyboardButton(text="🚗 En Route to Pickup", callback_data=f"driver_step:en_route:{request_id}")
        ])
    elif current_status == RequestStatus.EN_ROUTE_TO_PICKUP:
        buttons.append([
            InlineKeyboardButton(text="📦 Picked Up", callback_data=f"driver_step:picked_up:{request_id}")
        ])
    elif current_status == RequestStatus.PICKED_UP:
        buttons.append([
            InlineKeyboardButton(text="🚚 In Transit", callback_data=f"driver_step:in_transit:{request_id}")
        ])
    elif current_status == RequestStatus.IN_TRANSIT:
        buttons.append([
            InlineKeyboardButton(text="✅ Delivered", callback_data=f"driver_step:delivered:{request_id}"),
            InlineKeyboardButton(text="❌ Delivery Failed", callback_data=f"driver_step:failed:{request_id}"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


