"""
Configuration module for the Packit bot.

This module defines the Pydantic Settings model used to load the bot's
configuration from environment variables and a .env file. It also provides
a utility function to generate Telegram support deep links.
"""

import os
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Pydantic Settings model for the Packit bot configuration.

    All fields are populated from environment variables (or from a .env file
    specified via ``model_config``). Fields with default values will fall back
    to those defaults if the corresponding environment variable is not set.

    Attributes:
        bot_token (str): The Telegram Bot API token.
        database_url (str): The asynchronous database connection URL.
        redis_url (str): The Redis connection URL used for caching / rate limiting.
        seed_admin_telegram_ids (str): Comma-separated Telegram user IDs for
            initial admin seeding. Defaults to an empty string.
        max_request_lead_days (int): Maximum number of days in advance a ride
            request may be made. Defaults to 7.
        default_throttle_rate (float): Default throttle rate (requests per
            second) applied to external API calls. Defaults to 1.0.
        log_level (str): Logging verbosity level. Defaults to "INFO".
        webhook_url (str): Public HTTPS URL for receiving Telegram webhook
            updates. Defaults to an empty string (polling mode).
    """
    bot_token: str
    database_url: str
    redis_url: str
    seed_admin_telegram_ids: str = ""
    max_request_lead_days: int = 7
    default_throttle_rate: float = 1.0
    log_level: str = "INFO"
    webhook_url: str = ""

    # Configure Pydantic Settings behavior:
    # - env_file: Load variables from this file in addition to the process env.
    # - extra="ignore": Silently discard unknown environment variables instead
    #   of raising a validation error.
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


def get_settings() -> Settings:
    """
    Instantiate and return the application Settings object.

    This function is used as a simple factory so that other modules can import
    and call it rather than constructing ``Settings`` directly. The returned
    object is a singleton in practice because the configuration does not change
    at runtime.

    Returns:
        Settings: A fully populated Settings instance.

    Cross-References:
        - Called in ``bot/core/db/session.py`` (line ~3) to obtain
          ``database_url`` for SQLAlchemy engine creation.
        - Called in ``alembic/env.py`` during database migration configuration.
    """
    return Settings()


SUPPORT_USERNAME = "tokeniyi"
DEFAULT_SUPPORT_TEXT = "From Packit: Issue"


def get_support_url(
    username: str = SUPPORT_USERNAME,
    text: str = DEFAULT_SUPPORT_TEXT
) -> str:
    """
    Generate a Telegram deep-link URL for contacting support.

    The deep link opens a chat with the specified user (or channel) and
    pre-fills the message input field with the provided text.

    Args:
        username (str): The Telegram username (without '@') to address.
            Defaults to ``SUPPORT_USERNAME`` ("tokeniyi").
        text (str): The pre-filled message text. Defaults to
            ``DEFAULT_SUPPORT_TEXT`` ("From Packit: Issue").

    Returns:
        str: A URL-safe ``t.me`` deep link, e.g.
            ``https://t.me/tokeniyi?text=From+Packit%3A+Issue``.

    Function Calls:
        - ``urllib.parse.quote``: Percent-encodes the text so that spaces and
          special characters are safe inside a URL query string.
    """
    encoded_text = quote(text)
    return f"https://t.me/{username}?text={encoded_text}"
