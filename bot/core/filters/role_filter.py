from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineQuery, PollAnswer, Poll, ShippingQuery, PreCheckoutQuery


class RoleFilter(BaseFilter):
    def __init__(self, required_role: str):
        self.required_role = required_role

    async def __call__(self, event, data: dict) -> bool:
        user = data.get("user")
        if not user:
            return False
        return user.role == self.required_role


class IsStudent(RoleFilter):
    def __init__(self):
        super().__init__("student")


class IsDriver(RoleFilter):
    def __init__(self):
        super().__init__("driver")


class IsAdmin(RoleFilter):
    def __init__(self):
        super().__init__("admin")