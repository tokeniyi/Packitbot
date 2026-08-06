"""Pagination utilities for the Packitbot Telegram bot.

This module provides a Page dataclass and a paginate
function for splitting lists into pages with
navigation metadata.

Function Calls:
    - paginate(items, page, page_size) -> Page

Cross-References:
    - Depends on: bot.core.constants.limits.PAGE_SIZE
    - Imported by: bot/student/handler.py, bot/student/handler_requests.py
"""

from dataclasses import dataclass

from bot.core.constants.limits import PAGE_SIZE


@dataclass
class Page:
    """A paginated slice of a list with navigation metadata.

    Attributes:
        items: The items on the current page.
        total: The total number of items across all pages.
        page: The current page number (1-indexed).
        page_size: The number of items per page.
    """
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate the total number of pages.

        Returns:
            The total number of pages, at least 1.
        """
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_next(self) -> bool:
        """Check whether there is a next page.

        Returns:
            True if the current page is less than the total pages.
        """
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check whether there is a previous page.

        Returns:
            True if the current page is greater than 1.
        """
        return self.page > 1


def paginate(items: list, page: int, page_size: int = PAGE_SIZE) -> Page:
    """Split a list into a paginated Page object.

    Clamps the page number to at least 1 and slices
    the items list accordingly.

    Args:
        items: The full list of items to paginate.
        page: The requested page number (1-indexed).
        page_size: The number of items per page. Defaults to PAGE_SIZE.

    Returns:
        A Page object containing the sliced items and metadata.
    """
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
