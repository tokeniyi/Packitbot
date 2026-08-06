"""Rate-limiting middleware for the Packitbot Telegram bot.

This middleware implements a token-bucket throttling algorithm
to prevent users from sending too many updates in rapid
succession. It tracks token counts per user in an in-memory
dictionary and replenishes tokens based on a configurable
rate.

Classes:
    - ThrottlingMiddleware: aiogram BaseMiddleware subclass for rate limiting.

Function Calls:
    - __call__(handler, event, data) -> Any
    - _get_redis() -> Redis

Cross-References:
    - Depends on: aiogram BaseMiddleware, redis.asyncio.Redis,
        bot.core.config.Settings, bot.core.constants.messages.MSG_SLOW_DOWN,
        bot.core.keyboards.common_kb.HomeButton
    - Imported by: bot/main.py
"""

import asyncio
import logging
import time
from typing import Any, Callable, TypeVar

from aiogram import BaseMiddleware
from aiogram.types import Update
from redis.asyncio import Redis

from bot.core.config import Settings
from bot.core.constants.messages import MSG_SLOW_DOWN
from bot.core.keyboards.common_kb import HomeButton

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware that rate-limits user updates using a token bucket algorithm.

    Tracks a token count per Telegram user. Tokens regenerate
    over time based on ``throttle_rate``. When tokens are
    exhausted the user receives a slow-down message and the
    handler is not invoked.

    Attributes:
        settings: Application settings providing throttle rate and Redis URL.
        throttle_rate: The rate at which tokens regenerate per second.
        tokens: In-memory dict mapping user Telegram IDs to token state.
    """

    def __init__(self, settings: Settings):
        """Initialize the throttling middleware with application settings.

        Args:
            settings: The application Settings object providing
                default_throttle_rate and redis_url.
        """
        self.settings = settings
        self.throttle_rate = self.settings.default_throttle_rate
        self.tokens: dict[int, dict] = {}

    async def _get_redis(self) -> Redis:
        """Create and return a Redis client from the configured URL.

        Returns:
            A connected Redis async client.
        """
        return Redis.from_url(self.settings.redis_url)

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Any],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """Check the user's token balance before invoking the handler.

        Extracts the Telegram user ID from the update, computes
        token regeneration since the last check, denies the request
        if no tokens remain, or decrements a token and forwards
        to the handler.

        Args:
            handler: The next handler in the middleware chain.
            event: The incoming aiogram Update object.
            data: The handler data dict to pass along.

        Returns:
            The result of the downstream handler, or None if
            the request was throttled.
        """
        user_telegram_id = None
        if event.message:
            user_telegram_id = event.message.from_user.id
        elif event.callback_query:
            user_telegram_id = event.callback_query.from_user.id
        elif event.inline_query:
            user_telegram_id = event.inline_query.from_user.id
        elif event.poll_answer:
            user_telegram_id = event.poll_answer.user.id
        elif event.poll:
            user_telegram_id = event.poll.user.id
        elif event.shipping_query:
            user_telegram_id = event.shipping_query.from_user.id
        elif event.pre_checkout_query:
            user_telegram_id = event.pre_checkout_query.from_user.id

        if user_telegram_id is None:
            return await handler(event, data)

        now = time.time()
        tokens = self.tokens.get(user_telegram_id, {})

        if user_telegram_id not in self.tokens:
            self.tokens[user_telegram_id] = {"tokens": 1, "timestamp": now}
        else:
            elapsed = now - tokens["timestamp"]
            regenerated = int(elapsed * self.throttle_rate)
            tokens["tokens"] = min(10, tokens["tokens"] + regenerated)
            tokens["timestamp"] = now

        if self.tokens[user_telegram_id]["tokens"] < 1:
            logger.warning(f"Throttling denied for user {user_telegram_id}")
            reply = MSG_SLOW_DOWN
            markup = HomeButton()
            if event.message:
                await event.message.answer(reply, reply_markup=markup)
            elif event.callback_query:
                await event.callback_query.answer(reply, show_alert=True)
            return

        self.tokens[user_telegram_id]["tokens"] -= 1
        return await handler(event, data)