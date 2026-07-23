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
