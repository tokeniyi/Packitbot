from dataclasses import dataclass

from bot.core.constants.limits import PAGE_SIZE


@dataclass
class Page:
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


def paginate(items: list, page: int, page_size: int = PAGE_SIZE) -> Page:
    if page < 1:
        page = 1
    start = (page - 1) * page_size
    end = start + page_size
    return Page(
        items=items[start:end],
        total=len(items),
        page=page,
        page_size=page_size,
    )
