"""Rate-limiting middleware for the Packitbot Telegram bot.

This middleware implements a token-bucket throttling algorithm
to prevent users from sending too many updates in rapid
succession. It tracks token counts per user in an in-memory
dictionary and replenishes tokens based on a configurable
rate.

Each user's bucket starts full at ``THROTTLE_BURST`` tokens, so a short burst of
taps (for example, moving through a keyboard) is allowed. Tokens refill at
``default_throttle_rate`` per second. Fractional refill is kept, so a slow rate
such as 1 token per second still refills correctly between updates. Buckets
that have been idle for ``IDLE_EVICT_SECONDS`` are dropped to bound memory use
(P1 #19).

Classes:
    - ThrottlingMiddleware: aiogram BaseMiddleware subclass for rate limiting.

Function Calls:
    - __call__(handler, event, data) -> Any
    - _evict_idle(now) -> None

Cross-References:
    - Depends on: aiogram BaseMiddleware, bot.core.config.Settings,
        bot.core.constants.messages.MSG_SLOW_DOWN,
        bot.core.keyboards.common_kb.HomeButton
    - Imported by: bot/main.py
"""

import logging
import time
from typing import Any, Callable, TypeVar

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.core.config import Settings
from bot.core.constants.messages import MSG_SLOW_DOWN
from bot.core.keyboards.common_kb import HomeButton

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Maximum tokens a bucket holds, i.e. how many updates can arrive back to back.
THROTTLE_BURST = 5
# A bucket idle for longer than this is dropped. It has refilled to full by then
# at any sensible rate, so dropping it does not change what the user is allowed.
IDLE_EVICT_SECONDS = 3600
# How often the idle-bucket sweep runs, in seconds.
EVICT_SWEEP_INTERVAL = 60


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware that rate-limits user updates using a token bucket algorithm.

    Tracks a bucket per Telegram user. Each update costs one token. Tokens
    refill continuously at ``throttle_rate`` per second up to ``burst``. When a
    bucket holds less than one token the user receives a slow-down message and
    the handler is not invoked.

    Attributes:
        settings: Application settings providing the throttle rate.
        throttle_rate: Tokens refilled per second.
        burst: Maximum tokens a bucket can hold.
        tokens: In-memory dict mapping user Telegram IDs to
            ``{"tokens": float, "timestamp": float}``.
    """

    def __init__(self, settings: Settings):
        """Initialize the throttling middleware with application settings.

        Args:
            settings: The application Settings object providing
                default_throttle_rate.
        """
        self.settings = settings
        self.throttle_rate = self.settings.default_throttle_rate
        self.burst = THROTTLE_BURST
        self.tokens: dict[int, dict] = {}
        self._last_sweep = time.time()

    def _evict_idle(self, now: float) -> None:
        """Drop buckets idle for longer than ``IDLE_EVICT_SECONDS``.

        Runs at most once per ``EVICT_SWEEP_INTERVAL`` so the cost stays small.

        Args:
            now: The current time in seconds since the epoch.
        """
        if now - self._last_sweep < EVICT_SWEEP_INTERVAL:
            return
        self._last_sweep = now
        cutoff = now - IDLE_EVICT_SECONDS
        idle = [uid for uid, state in self.tokens.items() if state["timestamp"] < cutoff]
        for uid in idle:
            del self.tokens[uid]

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Any],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """Check the user's token balance before invoking the handler.

        Extracts the Telegram user ID from the update, refills the user's bucket
        for the time elapsed since the last update (capped at the burst size),
        denies the request if less than one token remains, or spends a token and
        forwards to the handler.

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
        self._evict_idle(now)

        state = self.tokens.get(user_telegram_id)
        if state is None:
            # A new user starts with a full bucket.
            state = {"tokens": float(self.burst), "timestamp": now}
            self.tokens[user_telegram_id] = state
        else:
            elapsed = max(0.0, now - state["timestamp"])
            state["tokens"] = min(float(self.burst), state["tokens"] + elapsed * self.throttle_rate)
            state["timestamp"] = now

        if state["tokens"] < 1:
            logger.warning(f"Throttling denied for user {user_telegram_id}")
            reply = MSG_SLOW_DOWN
            markup = HomeButton()
            if event.message:
                await event.message.answer(reply, reply_markup=markup)
            elif event.callback_query:
                await event.callback_query.answer(reply, show_alert=True)
            return

        state["tokens"] -= 1
        return await handler(event, data)
