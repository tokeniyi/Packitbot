from aiogram.filters.callback_data import CallbackData


class RequestAction(CallbackData, prefix="req_action"):
    action: str


class RequestEditField(CallbackData, prefix="req_edit"):
    field: str


class DriverStatusUpdate(CallbackData, prefix="driver_status"):
    status: str


class AdminAssign(CallbackData, prefix="admin_assign"):
    request_id: int
    driver_id: int


class AdminDriverApproval(CallbackData, prefix="admin_driver"):
    action: str
    driver_id: int


class AdminUserAction(CallbackData, prefix="admin_user"):
    action: str
    user_id: int


class ConfirmChoice(CallbackData, prefix="confirm"):
    choice: str


class SelectOption(CallbackData, prefix="select"):
    option: str
    value: str


class PaginationNav(CallbackData, prefix="nav"):
    page: int
    direction: str


class HallConfirm(CallbackData, prefix="hall_confirm"):
    action: str


class DateQuickPick(CallbackData, prefix="date_pick"):
    choice: str


class AddressQuickPick(CallbackData, prefix="addr_pick"):
    choice: str
    address_index: int | None = None


class ReviewFieldEdit(CallbackData, prefix="review_edit"):
    context: str
    field: str


class NavHome(CallbackData, prefix="nav"):
    action: str
