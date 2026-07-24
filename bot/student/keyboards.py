from datetime import date, timedelta
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from bot.core.constants.enums import LuggageSize
from bot.core.constants.halls import CU_HALLS
from bot.core.constants.quick_replies import (
    BTN_HOME,
    BTN_BACK,
    BTN_CANCEL,
    BTN_SKIP,
    BTN_EDIT,
    BTN_SUBMIT,
    DATE_QUICK_PICK_TODAY,
    DATE_QUICK_PICK_TOMORROW,
    TIME_WINDOW_MORNING,
    TIME_WINDOW_AFTERNOON,
    TIME_WINDOW_EVENING,
)
from bot.core.utils.validators import TIME_WINDOW_SLOTS


def hall_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=hall, callback_data=f"hall_select:{hall}")]
        for hall in CU_HALLS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def student_persistent_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="\U0001F4E6 New Request"),
                KeyboardButton(text="\U0001F4CB My Requests"),
            ],
            [
                KeyboardButton(text="\U0001F464 Profile"),
                KeyboardButton(text="\U0001F6C8 Help"),
            ],
        ],
        resize_keyboard=True,
    )


def date_quick_pick_keyboard() -> InlineKeyboardMarkup:
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=DATE_QUICK_PICK_TODAY, callback_data=f"req_date:{today_str}"),
                InlineKeyboardButton(text=DATE_QUICK_PICK_TOMORROW, callback_data=f"req_date:{tomorrow_str}"),
            ],
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")],
        ]
    )


def frequent_address_keyboard(frequent_addresses: List[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=addr, callback_data=f"req_addr:{idx}")]
        for idx, addr in enumerate(frequent_addresses)
    ]
    buttons.append([InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def req_hall_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=hall, callback_data=f"req_hall:{hall}")]
        for hall in CU_HALLS
    ]
    buttons.append([InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def luggage_size_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Small (🎒)", callback_data="req_size:small"),
                InlineKeyboardButton(text="Medium (🧳)", callback_data="req_size:medium"),
                InlineKeyboardButton(text="Large (📦)", callback_data="req_size:large"),
            ],
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")],
        ]
    )


def time_window_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=TIME_WINDOW_MORNING, callback_data="req_time:8am-11am"),
                InlineKeyboardButton(text=TIME_WINDOW_AFTERNOON, callback_data="req_time:12pm-3pm"),
                InlineKeyboardButton(text=TIME_WINDOW_EVENING, callback_data="req_time:4pm-7pm"),
            ],
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")],
        ]
    )


def skip_or_cancel_keyboard(skip_callback: str = "req_skip") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SKIP, callback_data=skip_callback)],
            [InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel")],
        ]
    )


def request_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Pickup Detail ✏️", callback_data="req_edit:pickup_detail"),
                InlineKeyboardButton(text="Dropoff Addr ✏️", callback_data="req_edit:dropoff_address"),
            ],
            [
                InlineKeyboardButton(text="Landmark ✏️", callback_data="req_edit:dropoff_landmark"),
                InlineKeyboardButton(text="Hall ✏️", callback_data="req_edit:hall"),
            ],
            [
                InlineKeyboardButton(text="Recipient Name ✏️", callback_data="req_edit:recipient_name"),
                InlineKeyboardButton(text="Recipient Phone ✏️", callback_data="req_edit:recipient_phone"),
            ],
            [
                InlineKeyboardButton(text="Luggage Size ✏️", callback_data="req_edit:luggage_size"),
                InlineKeyboardButton(text="Luggage Count ✏️", callback_data="req_edit:luggage_count"),
            ],
            [
                InlineKeyboardButton(text="Preferred Date ✏️", callback_data="req_edit:preferred_date"),
                InlineKeyboardButton(text="Time Window ✏️", callback_data="req_edit:preferred_time_window"),
            ],
            [
                InlineKeyboardButton(text="Special Instructions ✏️", callback_data="req_edit:special_instructions"),
            ],
            [
                InlineKeyboardButton(text=BTN_SUBMIT, callback_data="req_submit"),
                InlineKeyboardButton(text=BTN_CANCEL, callback_data="req_cancel"),
            ],
        ]
    )