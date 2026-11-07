"""Regression tests for P1 #19: the throttling middleware is a usable token bucket.

The old code used ``int(elapsed * rate)`` with a single starting token, so at the
default rate of 1 update per second a user could send one update, then had to wait
a full second for each next one. Tapping through a keyboard was blocked. The
bucket now starts at ``THROTTLE_BURST``, keeps fractional refill, and drops idle
buckets.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.middlewares import throttling
from bot.core.middlewares.throttling import (
    IDLE_EVICT_SECONDS,
    THROTTLE_BURST,
    ThrottlingMiddleware,
)


def _settings(rate: float) -> MagicMock:
    settings = MagicMock()
    settings.default_throttle_rate = rate
    return settings


def _update(user_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.answer = AsyncMock()
    update.callback_query = None
    update.inline_query = None
    update.poll_answer = None
    update.poll = None
    update.shipping_query = None
    update.pre_checkout_query = None
    return update


async def _handler(event, data):
    return "ok"


class _Clock:
    """Stand-in for the ``time`` module so tests control ``time.time()``."""

    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def time(self) -> float:
        return self.now


async def _send(middleware, update) -> object:
    return await middleware(_handler, update, {})


async def test_burst_allows_back_to_back_updates():
    middleware = ThrottlingMiddleware(_settings(1.0))
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        results = [await _send(middleware, _update()) for _ in range(THROTTLE_BURST)]

    assert results == ["ok"] * THROTTLE_BURST


async def test_sixth_immediate_update_is_denied_at_default_rate():
    middleware = ThrottlingMiddleware(_settings(1.0))
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        for _ in range(THROTTLE_BURST):
            await _send(middleware, _update())
        denied = await _send(middleware, _update())

    assert denied is None


async def test_fractional_refill_accumulates_between_updates():
    # At 1 token/s, half a second refills only half a token, so the next update
    # is denied; a further half second makes a whole token and it is allowed.
    middleware = ThrottlingMiddleware(_settings(1.0))
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        for _ in range(THROTTLE_BURST):
            await _send(middleware, _update())

        clock.now += 0.5
        assert await _send(middleware, _update()) is None

        clock.now += 0.5
        assert await _send(middleware, _update()) == "ok"


async def test_refill_is_capped_at_burst():
    middleware = ThrottlingMiddleware(_settings(1.0))
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        await _send(middleware, _update())
        clock.now += 10_000  # long idle, far past a full refill

        results = [await _send(middleware, _update()) for _ in range(THROTTLE_BURST + 1)]

    assert results[:THROTTLE_BURST] == ["ok"] * THROTTLE_BURST
    assert results[THROTTLE_BURST] is None


async def test_users_have_independent_buckets():
    middleware = ThrottlingMiddleware(_settings(0))
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        for _ in range(THROTTLE_BURST):
            await _send(middleware, _update(user_id=1))
        assert await _send(middleware, _update(user_id=1)) is None
        assert await _send(middleware, _update(user_id=2)) == "ok"


async def test_idle_buckets_are_evicted():
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        middleware = ThrottlingMiddleware(_settings(1.0))
        await _send(middleware, _update(user_id=1))
        assert 1 in middleware.tokens

        clock.now += IDLE_EVICT_SECONDS + 1
        await _send(middleware, _update(user_id=2))

    assert 1 not in middleware.tokens
    assert 2 in middleware.tokens


async def test_recent_buckets_are_kept_by_sweep():
    clock = _Clock()
    with patch.object(throttling, "time", clock):
        middleware = ThrottlingMiddleware(_settings(1.0))
        await _send(middleware, _update(user_id=1))
        clock.now += 120  # sweep runs, but user 1 is not idle long enough
        await _send(middleware, _update(user_id=2))

    assert 1 in middleware.tokens
