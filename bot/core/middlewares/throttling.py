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
    def __init__(self, settings: Settings):
        self.settings = settings
        self.throttle_rate = self.settings.default_throttle_rate
        self.tokens: dict[int, dict] = {}

    async def _get_redis(self) -> Redis:
        return Redis.from_url(self.settings.redis_url)

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Any],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
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