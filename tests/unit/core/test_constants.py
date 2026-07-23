from bot.core.constants import enums, features, halls, lagos_lgas, limits, messages, quick_replies


def test_enums_importable():
    assert enums.UserRole.STUDENT == "student"
    assert enums.AccountStatus.ACTIVE == "active"
    assert enums.DriverStatus.PENDING_APPROVAL == "pending_approval"
    assert enums.DriverAvailability.AVAILABLE == "available"
    assert enums.VerificationStatus.UNVERIFIED == "unverified"
    assert enums.LuggageSize.SMALL == "small"
    assert enums.RequestStatus.PENDING == "pending"
    assert enums.CancelledBy.STUDENT == "student"
    assert enums.AdminActionType.APPROVE_DRIVER == "approve_driver"
    assert enums.NotificationType.REQUEST_SUBMITTED == "request_submitted"


def test_halls_not_empty():
    assert isinstance(halls.CU_HALLS, list)
    assert len(halls.CU_HALLS) > 0


def test_lagos_lgas_not_empty():
    assert isinstance(lagos_lgas.LAGOS_LGAS, list)
    assert len(lagos_lgas.LAGOS_LGAS) > 0


def test_limits_values():
    assert limits.MAX_LUGGAGE_COUNT == 10
    assert limits.MIN_LUGGAGE_COUNT == 1
    assert limits.RATING_MIN == 1
    assert limits.RATING_MAX == 5
    assert limits.PAGE_SIZE == 5
    assert limits.FREQUENT_ADDRESS_MIN_USES == 3
    assert limits.FREQUENT_ADDRESS_SUGGESTION_COUNT == 2


def test_features_defaults():
    assert features.ENABLE_FEEDBACK is True
    assert features.ENABLE_ANALYTICS is True
    assert features.ENABLE_PAYMENTS is False


def test_quick_replies_values():
    assert quick_replies.BTN_HOME == "🏠 Home"
    assert quick_replies.BTN_BACK == "⬅ Back"
    assert quick_replies.BTN_CANCEL == "❌ Cancel"
    assert quick_replies.BTN_YES == "✅ Yes"
    assert quick_replies.BTN_NO == "❌ No"
    assert quick_replies.DATE_QUICK_PICK_TODAY == "📅 Today"
    assert quick_replies.DATE_QUICK_PICK_TOMORROW == "📅 Tomorrow"
    assert quick_replies.DATE_QUICK_PICK_ANOTHER == "📅 Choose Another Date"


def test_messages_non_empty_strings():
    assert isinstance(messages.MSG_START_ROLE_SELECTION, str)
    assert len(messages.MSG_START_ROLE_SELECTION) > 0
    assert isinstance(messages.MSG_HELP, str)
    assert len(messages.MSG_HELP) > 0
    assert isinstance(messages.MSG_ABOUT, str)
    assert len(messages.MSG_ABOUT) > 0
    assert isinstance(messages.MSG_REG_ENTER_FULL_NAME, str)
    assert len(messages.MSG_REG_ENTER_FULL_NAME) > 0
    assert isinstance(messages.MSG_REQ_ENTER_PICKUP_DETAIL, str)
    assert len(messages.MSG_REQ_ENTER_PICKUP_DETAIL) > 0
    assert isinstance(messages.MSG_STATUS_PENDING, str)
    assert len(messages.MSG_STATUS_PENDING) > 0
    assert isinstance(messages.MSG_BANNED, str)
    assert len(messages.MSG_BANNED) > 0
