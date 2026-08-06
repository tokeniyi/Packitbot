"""
Inline and reply keyboard factories for the admin module.

This module provides all keyboard layouts used in admin conversation flows.
Each function returns an ``InlineKeyboardMarkup`` or ``ReplyKeyboardMarkup``
configured with the appropriate callback data for admin actions such as
driver approval, request assignment, user management, and broadcast messaging.

Typical usage:
    These keyboards are constructed in ``bot/admin/handler.py`` and passed
    as ``reply_markup`` arguments to ``message.answer`` or
    ``callback.message.edit_text``.

Key exports:
    - ``driver_approval_keyboard``
    - ``pending_drivers_list_keyboard``
    - ``pending_requests_list_keyboard``
    - ``available_drivers_keyboard``
    - ``user_action_keyboard``
    - ``broadcast_audience_keyboard``
    - ``broadcast_confirm_keyboard``

Dependencies:
    - ``aiogram.types.InlineKeyboardButton``, ``InlineKeyboardMarkup``
    - ``bot.core.constants.quick_replies``: ``BTN_BACK``, ``BTN_HOME``
    - ``bot.core.utils.callback_data``: ``AdminAssign``, ``AdminDriverApproval``,
      ``AdminUserAction``, ``PaginationNav``
    - ``bot.admin.schemas``: ``AvailableDriverDTO``, ``UserDetailDTO``

Called by:
    - ``bot/admin/handler.py``: All admin handler functions that render menus.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.core.constants.quick_replies import BTN_BACK, BTN_HOME
from bot.core.utils.callback_data import AdminAssign, AdminDriverApproval, AdminUserAction, PaginationNav
from bot.admin.schemas import AvailableDriverDTO, UserDetailDTO


def driver_approval_keyboard(driver_id: int) -> InlineKeyboardMarkup:
    """Build approval/rejection controls for a specific driver application.

    Args:
        driver_id (int): The primary key of the ``DriverProfile`` being reviewed.

    Returns:
        InlineKeyboardMarkup: A 2-row inline keyboard with Approve/Reject
        buttons in the first row and Back/Home navigation in the second row.

    Called by:
        - ``bot/admin/handler.py``: ``handle_view_driver_detail``
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Approve",
                    callback_data=AdminDriverApproval(action="approve", driver_id=driver_id).pack(),
                ),
                InlineKeyboardButton(
                    text="Reject",
                    callback_data=AdminDriverApproval(action="reject", driver_id=driver_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(text=BTN_BACK, callback_data="admin_pending_drivers_back"),
                InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
            ],
        ]
    )


def pending_drivers_list_keyboard(
    drivers: list,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Build a paginated list of pending driver applications.

    Each driver is rendered as a button that triggers a "view" callback.
    Pagination controls are shown only when there are multiple pages.

    Args:
        drivers (list): Iterable of driver items. Each item may be a
            ``DriverApplicationDetailDTO`` or an object with ``driver_id``
            and ``full_name`` attributes.
        page (int): Current page number (1-indexed). Defaults to 1.
        total_pages (int): Total number of pages available. Defaults to 1.

    Returns:
        InlineKeyboardMarkup: Paginated inline keyboard with driver entries
        and optional Prev/Next navigation.

    Called by:
        - ``bot/admin/handler.py``: ``cmd_verify_drivers``,
          ``handle_back_to_pending_list``
    """
    buttons = []
    for d in drivers:
        # Support both DTO objects and lightweight tuples/dicts.
        driver_id = getattr(d, "driver_id", None) or getattr(d, "id", None)
        name = getattr(d, "full_name", None) or "Driver"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📋 {name} (ID: {driver_id})",
                    callback_data=AdminDriverApproval(action="view", driver_id=driver_id).pack(),
                )
            ]
        )

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=PaginationNav(page=page - 1, direction="prev").pack(),
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️ Next",
                callback_data=PaginationNav(page=page + 1, direction="next").pack(),
            )
        )
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pending_requests_list_keyboard(
    requests: list,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Build a paginated list of pending delivery requests for assignment.

    Each request is rendered as a button that opens the driver selection flow.
    Pagination controls are shown only when there are multiple pages.

    Args:
        requests (list): Iterable of ``DeliveryRequest`` objects.
        page (int): Current page number (1-indexed). Defaults to 1.
        total_pages (int): Total number of pages available. Defaults to 1.

    Returns:
        InlineKeyboardMarkup: Paginated inline keyboard with request entries
        and optional Prev/Next navigation.

    Called by:
        - ``bot/admin/handler.py``: ``cmd_pending_requests``,
          ``handle_pending_requests_pagination``,
          ``handle_back_to_pending_requests``
    """
    buttons = []
    for req in requests:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📦 #{req.id} - {req.hall_of_residence} ➡️ {req.dropoff_address[:15]}...",
                    callback_data=f"admin_assign_req:{req.id}",
                )
            ]
        )

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"admin_req_page:{page - 1}",
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️ Next",
                callback_data=f"admin_req_page:{page + 1}",
            )
        )
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def available_drivers_keyboard(
    drivers: list[AvailableDriverDTO],
    request_id: int,
) -> InlineKeyboardMarkup:
    """Build a ranked list of available drivers for a specific request assignment.

    Drivers are displayed with their average rating and total delivery count.
    Selecting a driver triggers the ``AdminAssign`` callback with the
    ``request_id`` and ``driver_id`` embedded.

    Args:
        drivers (list[AvailableDriverDTO]): Ranked list of available drivers.
        request_id (int): The ``DeliveryRequest`` ID being assigned.

    Returns:
        InlineKeyboardMarkup: Inline keyboard with driver selection buttons
        and Back/Home navigation.

    Called by:
        - ``bot/admin/handler.py``: ``handle_select_request_for_assignment``
    """
    buttons = []
    for d in drivers:
        rating_str = f"⭐ {d.rating_avg:.1f}" if d.rating_avg > 0 else "⭐ New"
        text = f"🚗 {d.full_name} ({rating_str} | 📦 {d.total_deliveries})"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=AdminAssign(request_id=request_id, driver_id=d.driver_id).pack(),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(text=BTN_BACK, callback_data="admin_pending_req_back"),
            InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_action_keyboard(user_detail: UserDetailDTO) -> InlineKeyboardMarkup:
    """Build management action buttons for a specific user.

    The available actions depend on the user's current state:
        - Banned users show an "Unban" button.
        - Active users show a "Ban" button.
        - Non-admin users show a "Promote to Admin" button.

    Args:
        user_detail (UserDetailDTO): Snapshot of the target user's profile.

    Returns:
        InlineKeyboardMarkup: Inline keyboard with contextual user management
        actions and a Home button.

    Called by:
        - ``bot/admin/handler.py``: ``process_user_search``
    """
    buttons = []
    action_row = []

    if user_detail.account_status == "banned":
        action_row.append(
            InlineKeyboardButton(
                text="🟢 Unban User",
                callback_data=AdminUserAction(action="unban", user_id=user_detail.user_id).pack(),
            )
        )
    else:
        action_row.append(
            InlineKeyboardButton(
                text="🔴 Ban User",
                callback_data=AdminUserAction(action="ban", user_id=user_detail.user_id).pack(),
            )
        )

    if user_detail.role != "admin":
        action_row.append(
            InlineKeyboardButton(
                text="⭐ Promote to Admin",
                callback_data=AdminUserAction(action="promote", user_id=user_detail.user_id).pack(),
            )
        )

    if action_row:
        buttons.append(action_row)

    buttons.append([
        InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    """Build the audience selection keyboard for the broadcast flow.

    Returns:
        InlineKeyboardMarkup: Inline keyboard with Students, Drivers, and
        All Users options, plus Back and Home navigation.

    Called by:
        - ``bot/admin/handler.py``: ``cmd_broadcast``
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎓 Students", callback_data="broadcast_audience:students"),
                InlineKeyboardButton(text="🚗 Drivers", callback_data="broadcast_audience:drivers"),
            ],
            [
                InlineKeyboardButton(text="👥 All Users", callback_data="broadcast_audience:all"),
            ],
            [
                InlineKeyboardButton(text=BTN_BACK, callback_data="broadcast_cancel"),
                InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
            ],
        ]
    )


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build the preview confirmation keyboard for the broadcast flow.

    Returns:
        InlineKeyboardMarkup: Inline keyboard with Send Broadcast and Cancel
        buttons, plus Home navigation.

    Called by:
        - ``bot/admin/handler.py``: ``process_broadcast_content``
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Send Broadcast", callback_data="broadcast_confirm:send"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="broadcast_cancel"),
            ],
            [
                InlineKeyboardButton(text=BTN_HOME, callback_data="home"),
            ],
        ]
    )
