import os
import tempfile

import pytest
from pydantic_settings import SettingsConfigDict

from bot.core.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SEED_ADMIN_TELEGRAM_IDS", "1,2")
    monkeypatch.setenv("MAX_REQUEST_LEAD_DAYS", "14")
    monkeypatch.setenv("DEFAULT_THROTTLE_RATE", "2")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")

    s = Settings()
    assert s.bot_token == "123:ABC"
    assert s.database_url == "postgresql+asyncpg://u:p@h/db"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.seed_admin_telegram_ids == "1,2"
    assert s.max_request_lead_days == 14
    assert s.default_throttle_rate == 2.0
    assert s.log_level == "DEBUG"
    assert s.webhook_url == "https://example.com/webhook"


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("SEED_ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.delenv("MAX_REQUEST_LEAD_DAYS", raising=False)
    monkeypatch.delenv("DEFAULT_THROTTLE_RATE", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    with pytest.raises(Exception):
        Settings()
