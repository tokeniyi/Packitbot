"""Keyboard factories for driver conversation flows.

This module defines all aiogram keyboard factories used by the driver flow.
It provides inline and reply keyboards for registration, menu navigation,
delivery assignment response, and step-by-step status progression.

Factories
---------
- ``vehicle_type_keyboard``                -> used in ``process_vehicle_type`` and ``process_edit_field``
- ``driver_registration_review_keyboard`` -> used in ``_show_review_screen``
- ``driver_pending_menu``                -> used in ``start_driver_registration``, ``check_approval_status``, ``toggle_availability_handler``
- ``driver_persistent_menu``             -> used in ``start_driver_registration``, ``check_approval_status``, ``toggle_availability_handler``, ``active_delivery_dashboard_handler``
- ``driver_assignment_response_keyboard`` -> used when a driver is assigned a request
- ``delivery_status_update_keyboard``    -> used in ``process_driver_accept``, ``process_delivery_status_step``

Depends on
----------
``aiogram.types`` (InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton),
``bot.core.constants.enums`` (DriverAvailability, DriverStatus, RequestStatus).

Imported by
-----------
``bot/driver/handler.py``, ``bot/admin/handler.py`` (assignment notifications).
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.core.constants.enums import DriverAvailability, DriverStatus, RequestStatus


def vehicle_type_keyboard() -> InlineKeyboardMarkup:
    """Build the inline keyboard for selecting a vehicle type during registration.

    Each button emits a ``driver_vtype:<type>`` callback that is consumed by
    :func:`process_vehicle_type` in ``handler.py``.

    Returns:
        An :class:`InlineKeyboardMarkup` with Sedan, SUV, Bus, Bike, Van,
        Cancel, and Home buttons.
    """
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
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
            ],
        ]
    )


def driver_registration_review_keyboard() -> InlineKeyboardMarkup:
    """Build the review-and-edit inline keyboard shown after all fields are collected.

    Presents five edit buttons (``driver_edit:<field>``) one per collected
    field, plus Submit and Cancel actions. Consumed by
    :func:`_show_review_screen` in ``handler.py``.

    Returns:
        An :class:`InlineKeyboardMarkup` with edit, submit, cancel, and home
        buttons.
    """
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
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
            ],
        ]
    )


def driver_pending_menu() -> ReplyKeyboardMarkup:
    """Build the restricted reply menu shown while registration is pending or rejected.

    Provides access to status checking and help/support only, as approved
    driver features are unavailable at this stage.

    Returns:
        A :class:`ReplyKeyboardMarkup` with "Check Approval Status" and
        "Help / Support" buttons.
    """
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
    """Build the full persistent menu for approved drivers.

    The availability toggle button text changes based on the driver's
    current availability state: "Go Offline" when ``AVAILABLE``, "Go
    Available" when ``OFFLINE``, and "Go Offline" when ``BUSY`` (since
    busy drivers cannot manually toggle).

    Args:
        availability: The driver's current :class:`DriverAvailability` state.
                      Defaults to ``OFFLINE``.

    Returns:
        A :class:`ReplyKeyboardMarkup` with toggle, assigned deliveries,
        active delivery, and profile buttons.
    """
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
    """Build the inline keyboard for a driver to accept or reject a delivery assignment.

    Each button emits a ``driver_accept:<request_id>`` or
    ``driver_reject:<request_id>`` callback consumed by
    :func:`process_driver_accept` / :func:`process_driver_reject` in
    ``handler.py``.

    Args:
        request_id: The database primary key of the :class:`DeliveryRequest`
                    being offered to the driver.

    Returns:
        An :class:`InlineKeyboardMarkup` with Accept, Reject, and Home
        buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Accept", callback_data=f"driver_accept:{request_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"driver_reject:{request_id}"),
            ],
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
            ],
        ]
    )


def delivery_status_update_keyboard(request_id: int, current_status: RequestStatus) -> InlineKeyboardMarkup:
    """Build the contextual status-progression keyboard for an active delivery.

    Based on the current :class:`RequestStatus`, returns a single
    next-step action button (or two terminal options when ``IN_TRANSIT``)
    plus a Home button. Callback data uses the ``driver_step:<action>:<request_id>``
    schema, parsed by :func:`process_delivery_status_step` in ``handler.py``.

    Args:
        request_id:    The database primary key of the :class:`DeliveryRequest`.
        current_status: The request's current :class:`RequestStatus`. Selects
                        which button(s) to render.

    Returns:
        An :class:`InlineKeyboardMarkup` whose contents depend on
        ``current_status``. Returns only the Home button if the status does
        not match any known transitional state.
    """
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

    # Every status-flow keyboard ends with a Home button for global navigation.
    buttons.append([InlineKeyboardButton(text="🏠 Home", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
