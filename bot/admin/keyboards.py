# bot/admin/keyboards.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.core.constants.quick_replies import BTN_BACK, BTN_HOME
from bot.core.utils.callback_data import AdminDriverApproval, PaginationNav


def driver_approval_keyboard(driver_id: int) -> InlineKeyboardMarkup:
    """Returns approval/rejection controls for a specific driver application."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve",
                    callback_data=AdminDriverApproval(action="approve", driver_id=driver_id).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
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
    """Returns keyboard listing pending drivers and pagination controls."""
    buttons = []
    for d in drivers:
        # d can be a tuple or object/dict with driver_id and full_name
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
