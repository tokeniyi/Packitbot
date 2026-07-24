from bot.core.utils.validators import validate_matric
from datetime import date, timedelta, datetime

import pytest

from bot.core.constants.limits import (
    MAX_BROADCAST_LENGTH,
    MAX_LUGGAGE_COUNT,
    MIN_LUGGAGE_COUNT,
    PAGE_SIZE,
    RATING_MAX,
    RATING_MIN,
)
from bot.core.constants.enums import LuggageSize
from bot.core.utils.callback_data import (
    AdminAssign,
    AdminDriverApproval,
    AdminUserAction,
    AddressQuickPick,
    ConfirmChoice,
    DateQuickPick,
    DriverStatusUpdate,
    HallConfirm,
    NavHome,
    PaginationNav,
    RequestAction,
    RequestEditField,
    ReviewFieldEdit,
    SelectOption,
)
from bot.core.utils.formatters import (
    format_account_status,
    format_admin_action_type,
    format_cancelled_by_label,
    format_datetime_for_display,
    format_date_for_display,
    format_driver_availability,
    format_driver_name,
    format_driver_status,
    format_luggage_size,
    format_request_summary,
    format_rating,
    format_status_label,
    format_verification_status,
)
from bot.core.utils.pagination import Page, paginate
from bot.core.utils.validators import (
    ValidationError,
    validate_cancellation_reason,
    validate_dropoff_address,
    validate_full_name,
    validate_hall,
    validate_license_number,
    validate_luggage_count,
    validate_luggage_size,
    validate_phone,
    validate_plate_number,
    validate_preferred_date,
    validate_pickup_detail,
    validate_rating,
    validate_recipient_name,
    validate_special_instructions,
    validate_time_window,
    validate_vehicle_type,
)


# --- phone ---
@pytest.mark.parametrize("raw,expected", [
    ("08023456789", "+2348023456789"),
    (" 08023456789 ", "+2348023456789"),
])
def test_phone_valid(raw, expected):
    assert validate_phone(raw) == expected


@pytest.mark.parametrize("raw", [
    "1234567890",
    "+234701234567890",
    "0801234567",
    "hello",
])
def test_phone_invalid(raw):
    with pytest.raises(ValidationError):
        validate_phone(raw)


# --- matric ---
@pytest.mark.parametrize("raw", ["12/3456", "99/9999"])
def test_matric_valid(raw):
    assert validate_matric(raw) == raw


@pytest.mark.parametrize("raw", ["1/3456", "12/34", "12-3456", "abc/def"])
def test_matric_invalid(raw):
    with pytest.raises(ValidationError):
        validate_matric(raw)


# --- names ---
@pytest.mark.parametrize("raw", ["John Doe", "Jane Mary-Jane O'Brien"])
def test_full_name_valid(raw):
    assert validate_full_name(raw) == raw


@pytest.mark.parametrize("raw", ["John", "John1", "John_Doe", ""])
def test_full_name_invalid(raw):
    with pytest.raises(ValidationError):
        validate_full_name(raw)


# --- hall ---
def test_hall_valid():
    assert validate_hall("Esther Hall") == "Esther Hall"


def test_hall_invalid():
    with pytest.raises(ValidationError):
        validate_hall("Unknown Hall")


# --- pickup ---
def test_pickup_detail_valid():
    assert validate_pickup_detail("Block B, room 12") == "Block B, room 12"


def test_pickup_detail_empty():
    with pytest.raises(ValidationError):
        validate_pickup_detail("   ")


# --- dropoff ---
def test_dropoff_address_valid():
    assert validate_dropoff_address("123 Main Street") == "123 Main Street"


def test_dropoff_address_too_short():
    with pytest.raises(ValidationError):
        validate_dropoff_address("Short")


# --- luggage size ---
def test_luggage_size_valid():
    assert validate_luggage_size("MEDIUM") == LuggageSize.MEDIUM


def test_luggage_size_invalid():
    with pytest.raises(ValidationError):
        validate_luggage_size("xlarge")


# --- luggage count ---
@pytest.mark.parametrize("raw", ["1", "5", "10"])
def test_luggage_count_valid(raw):
    assert validate_luggage_count(raw) == int(raw)


@pytest.mark.parametrize("raw", ["0", "-1", "11", "abc"])
def test_luggage_count_invalid(raw):
    with pytest.raises(ValidationError):
        validate_luggage_count(raw)


# --- preferred date ---
def test_preferred_date_today():
    assert validate_preferred_date(str(date.today())) == date.today()


def test_preferred_date_past():
    past = date.today() - timedelta(days=1)
    with pytest.raises(ValidationError):
        validate_preferred_date(str(past), max_lead_days=7)


def test_preferred_date_too_far():
    future = date.today() + timedelta(days=8)
    with pytest.raises(ValidationError):
        validate_preferred_date(str(future), max_lead_days=7)


# --- time window ---
def test_time_window_valid():
    assert validate_time_window("8am-11am") == "8am-11am"


def test_time_window_invalid():
    with pytest.raises(ValidationError):
        validate_time_window("midnight-morning")


# --- special instructions ---
def test_special_instructions_optional():
    assert validate_special_instructions(None) is None
    assert validate_special_instructions("") is None
    assert validate_special_instructions("  ") is None


def test_special_instructions_too_long():
    with pytest.raises(ValidationError):
        validate_special_instructions("x" * 501)


# --- plate number ---
def test_plate_valid():
    assert validate_plate_number("ABC-123DE") == "ABC-123DE"


def test_plate_invalid():
    with pytest.raises(ValidationError):
        validate_plate_number("123-ABC")


# --- license number ---
def test_license_valid():
    assert validate_license_number("DL12345") == "DL12345"


def test_license_empty():
    with pytest.raises(ValidationError):
        validate_license_number("   ")


# --- vehicle type ---
def test_vehicle_type_valid():
    assert validate_vehicle_type("SUV") == "suv"


def test_vehicle_type_invalid():
    with pytest.raises(ValidationError):
        validate_vehicle_type("truck")


# --- rating ---
@pytest.mark.parametrize("raw", ["1", "3", "5"])
def test_rating_valid(raw):
    assert validate_rating(raw) == int(raw)


@pytest.mark.parametrize("raw", ["0", "-1", "6", "abc"])
def test_rating_invalid(raw):
    with pytest.raises(ValidationError):
        validate_rating(raw)


# --- cancellation reason ---
def test_cancellation_reason_valid():
    assert validate_cancellation_reason("Changed plans") == "Changed plans"


def test_cancellation_reason_empty():
    with pytest.raises(ValidationError):
        validate_cancellation_reason("   ")


# --- recipient name ---
def test_recipient_name_valid():
    assert validate_recipient_name("John Doe") == "John Doe"


def test_recipient_name_invalid():
    with pytest.raises(ValidationError):
        validate_recipient_name("John")


# --- formatters ---
def test_format_date_for_display():
    d = date(2026, 7, 23)
    assert format_date_for_display(d) == "23 Jul 2026"


def test_format_datetime_for_display():
    dt = datetime(2026, 7, 23, 14, 30)
    assert format_datetime_for_display(dt) == "23 Jul 2026, 03:30 PM"


def test_format_status_label():
    from bot.core.constants.enums import RequestStatus
    label = format_status_label(RequestStatus.PENDING)
    assert "Pending" in label


def test_format_luggage_size():
    assert format_luggage_size(LuggageSize.MEDIUM) == "Medium"


def test_format_rating():
    assert format_rating(4.5) == "4.5"


def test_format_driver_name():
    assert format_driver_name("John Doe") == "John"


def test_format_cancelled_by_label_none():
    assert format_cancelled_by_label(None) is None


def test_format_request_summary():
    summary = format_request_summary(
        pickup_detail="Block B",
        dropoff_address="Ikeja",
        dropoff_landmark="Gate",
        hall_of_residence="Esther Hall",
        recipient_name="John",
        recipient_phone="+234801234567",
        luggage_size=LuggageSize.MEDIUM,
        luggage_count=2,
        preferred_date=date(2026, 7, 24),
        preferred_time_window="8am-11am",
        special_instructions="Call me",
    )
    assert "Pickup" in summary
    assert "Dropoff" in summary
    assert "Luggage" in summary


# --- callback data round-trip ---
@pytest.mark.parametrize("factory,expected_prefix", [
    (RequestAction, "req_action"),
    (RequestEditField, "req_edit"),
    (DriverStatusUpdate, "driver_status"),
    (AdminAssign, "admin_assign"),
    (AdminDriverApproval, "admin_driver"),
    (AdminUserAction, "admin_user"),
    (ConfirmChoice, "confirm"),
    (SelectOption, "select"),
    (PaginationNav, "nav"),
    (HallConfirm, "hall_confirm"),
    (DateQuickPick, "date_pick"),
    (AddressQuickPick, "addr_pick"),
    (ReviewFieldEdit, "review_edit"),
    (NavHome, "nav"),
])
def test_callback_data_factory_prefix(factory, expected_prefix):
    assert factory.__prefix__ == expected_prefix


def test_pagination_nav_roundtrip():
    cb = PaginationNav(page=2, direction="next")
    data = cb.pack()
    unpacked = PaginationNav.unpack(data)
    assert unpacked.page == 2
    assert unpacked.direction == "next"


def test_hall_confirm_roundtrip():
    cb = HallConfirm(action="use_profile_hall")
    data = cb.pack()
    unpacked = HallConfirm.unpack(data)
    assert unpacked.action == "use_profile_hall"


def test_date_quick_pick_roundtrip():
    cb = DateQuickPick(choice="tomorrow")
    data = cb.pack()
    unpacked = DateQuickPick.unpack(data)
    assert unpacked.choice == "tomorrow"


def test_address_quick_pick_roundtrip():
    cb = AddressQuickPick(choice="frequent_1", address_index=0)
    data = cb.pack()
    unpacked = AddressQuickPick.unpack(data)
    assert unpacked.choice == "frequent_1"
    assert unpacked.address_index == 0


def test_review_field_edit_roundtrip():
    cb = ReviewFieldEdit(context="req_create", field="pickup_detail")
    data = cb.pack()
    unpacked = ReviewFieldEdit.unpack(data)
    assert unpacked.context == "req_create"
    assert unpacked.field == "pickup_detail"


def test_nav_home_roundtrip():
    cb = NavHome(action="home")
    data = cb.pack()
    unpacked = NavHome.unpack(data)
    assert unpacked.action == "home"


# --- pagination ---
def test_pagination_middle_page():
    items = list(range(1, 26))
    page = paginate(items, page=2, page_size=PAGE_SIZE)
    assert page.items == [6, 7, 8, 9, 10]
    assert page.total == 25
    assert page.page == 2
    assert page.has_prev is True
    assert page.has_next is True
    assert page.total_pages == 5


def test_pagination_first_page():
    items = list(range(1, 26))
    page = paginate(items, page=1, page_size=PAGE_SIZE)
    assert page.items == [1, 2, 3, 4, 5]
    assert page.has_prev is False
    assert page.has_next is True


def test_pagination_last_page():
    items = list(range(1, 26))
    page = paginate(items, page=5, page_size=PAGE_SIZE)
    assert page.items == [21, 22, 23, 24, 25]
    assert page.has_prev is True
    assert page.has_next is False


def test_pagination_empty():
    page = paginate([], page=1, page_size=PAGE_SIZE)
    assert page.items == []
    assert page.total == 0
    assert page.total_pages == 1
