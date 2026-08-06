"""Application-wide constant limits and thresholds.

This module defines numeric constants used for
validation, pagination, and feature configuration
throughout the Packitbot application.

Constants:
    - MAX_LUGGAGE_COUNT: Maximum number of luggage items allowed.
    - MIN_LUGGAGE_COUNT: Minimum number of luggage items required.
    - RATING_MIN: Minimum rating value.
    - RATING_MAX: Maximum rating value.
    - PAGE_SIZE: Default number of items per page.
    - FREQUENT_ADDRESS_MIN_USES: Minimum uses before an address is suggested.
    - FREQUENT_ADDRESS_SUGGESTION_COUNT: Number of suggestions to show.
    - MAX_BROADCAST_LENGTH: Maximum length of a broadcast message.
"""

MAX_LUGGAGE_COUNT = 10
MIN_LUGGAGE_COUNT = 1
RATING_MIN = 1
RATING_MAX = 5
PAGE_SIZE = 5
FREQUENT_ADDRESS_MIN_USES = 3
FREQUENT_ADDRESS_SUGGESTION_COUNT = 2
MAX_BROADCAST_LENGTH = 4096
