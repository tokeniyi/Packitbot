import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    redis_url: str
    seed_admin_telegram_ids: str = ""
    max_request_lead_days: int = 7
    default_throttle_rate: float = 1.0
    log_level: str = "INFO"
    webhook_url: str = ""

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()


from urllib.parse import quote

# Define your primary support contact username (without @)
SUPPORT_USERNAME = "tokeniyi"  # Change to "Dayo_the_Great" or any other username whenever needed!

DEFAULT_SUPPORT_TEXT = "From Packit: Issue"

def get_support_url(
    username: str = SUPPORT_USERNAME, 
    text: str = DEFAULT_SUPPORT_TEXT
) -> str:
    """Generates a direct Telegram deep link with pre-filled text."""
    encoded_text = quote(text)
    # Using https://t.me/ username format with pre-filled text query
    return f"https://t.me/{username}?text={encoded_text}"