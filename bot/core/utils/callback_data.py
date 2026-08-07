"""Callback data factory classes for inline keyboard interactions.

This module defines aiogram CallbackData subclasses
used to encode structured data into inline keyboard
button callbacks. Each class maps to a specific
interaction pattern in the bot.

Classes:
    - RequestAction: Generic request action callback.
    - RequestEditField: Edit a specific field in a request.
    - DriverStatusUpdate: Update driver status.
    - AdminAssign: Assign a driver to a request.
    - AdminDriverApproval: Approve or reject a driver.
    - AdminUserAction: Perform an action on a user.
    - ConfirmChoice: Yes/No confirmation choice.
    - SelectOption: Select an option with a value.
    - PaginationNav: Navigate between pages.
    - HallConfirm: Confirm hall selection.
    - DateQuickPick: Quick pick a date.
    - AddressQuickPick: Quick pick a frequent address.
    - ReviewFieldEdit: Edit a field on the review screen.
    - NavHome: Navigate to the home screen.

Cross-References:
    - Depends on: aiogram.filters.callback_data.CallbackData
    - Imported by: bot/student/handler.py, bot/student/handler_requests.py,
        bot/admin/handler.py, bot/driver/handler.py
"""

from aiogram.filters.callback_data import CallbackData


class RequestAction(CallbackData, prefix="req_action"):
    """Callback data for generic request actions."""
    action: str


class RequestEditField(CallbackData, prefix="req_edit"):
    """Callback data for editing a specific field on the review screen."""
    field: str


class DriverStatusUpdate(CallbackData, prefix="driver_status"):
    """Callback data for updating driver availability status."""
    status: str


class AdminAssign(CallbackData, prefix="admin_assign"):
    """Callback data for assigning a driver to a request."""
    request_id: int
    driver_id: int


class AdminDriverApproval(CallbackData, prefix="admin_driver"):
    """Callback data for approving or rejecting a driver."""
    action: str
    driver_id: int


class AdminDriverManage(CallbackData, prefix="admin_drv_mgr"):
    """Callback data for managing an individual driver record."""
    action: str
    driver_id: int


class AdminDriverEdit(CallbackData, prefix="admin_drv_edit"):
    """Callback data for editing a specific field on a driver record."""
    field: str
    driver_id: int


class AdminDriverRemove(CallbackData, prefix="admin_drv_rm"):
    """Callback data for removing a driver record."""
    action: str
    driver_id: int


class AdminUserAction(CallbackData, prefix="admin_user"):
    """Callback data for admin actions on a user."""
    action: str
    user_id: int


class ConfirmChoice(CallbackData, prefix="confirm"):
    """Callback data for yes/no confirmation choices."""
    choice: str


class SelectOption(CallbackData, prefix="select"):
    """Callback data for selecting an option with an associated value."""
    option: str
    value: str


class PaginationNav(CallbackData, prefix="nav"):
    """Callback data for pagination navigation."""
    page: int
    direction: str


class HallConfirm(CallbackData, prefix="hall_confirm"):
    """Callback data for confirming a hall selection."""
    action: str


class DateQuickPick(CallbackData, prefix="date_pick"):
    """Callback data for quick-picking a date."""
    choice: str


class AddressQuickPick(CallbackData, prefix="addr_pick"):
    """Callback data for quick-picking a frequent address."""
    choice: str
    address_index: int | None = None


class ReviewFieldEdit(CallbackData, prefix="review_edit"):
    """Callback data for editing a field on the registration review screen."""
    context: str
    field: str


class NavHome(CallbackData, prefix="nav"):
    """Callback data for navigating to the home screen."""
    action: str
