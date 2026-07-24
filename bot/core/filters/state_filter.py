from aiogram.filters import BaseFilter


class HasActiveRequestFilter(BaseFilter):
    async def __call__(self, event, data: dict) -> bool:
        # Placeholder: actual logic depends on request service/repository
        return True