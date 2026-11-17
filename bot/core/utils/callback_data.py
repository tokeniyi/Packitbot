"""Callback data factory classes for inline keyboard interactions.

This module defines aiogram CallbackData subclasses
used to encode structured data into inline keyboard
button callbacks. Each class maps to a specific
interaction pattern in the bot.

Classes:
    - AdminAssign: Assign a driver to a request.
    - AdminDriverApproval: Approve or reject a driver.
    - AdminUserAction: Perform an action on a user.
    - PaginationNav: Navigate between pages.

Cross-References:
    - Depends on: aiogram.filters.callback_data.CallbackData
    - Imported by: bot/admin/keyboards.py, bot/admin/handler.py
"""

from aiogram.filters.callback_data import CallbackData


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


class PaginationNav(CallbackData, prefix="nav"):
    """Callback data for pagination navigation."""
    page: int
    direction: str
