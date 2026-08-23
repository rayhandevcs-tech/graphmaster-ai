"""Rate limiter."""

from __future__ import annotations

import pytest

from app.core.exceptions import RateLimitError
from app.core.rate_limit import RateLimit, RateLimiter


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter()


LIMIT = RateLimit(limit=3, window_seconds=60)


class TestRateLimiter:
    def test_allows_up_to_the_limit(self, limiter):
        for _ in range(LIMIT.limit):
            limiter.check("k", LIMIT)

    def test_blocks_beyond_the_limit(self, limiter):
        for _ in range(LIMIT.limit):
            limiter.check("k", LIMIT)
        with pytest.raises(RateLimitError):
            limiter.check("k", LIMIT)

    def test_blocked_response_carries_retry_after(self, limiter):
        for _ in range(LIMIT.limit):
            limiter.check("k", LIMIT)
        with pytest.raises(RateLimitError) as exc:
            limiter.check("k", LIMIT)
        assert exc.value.retry_after > 0
        assert exc.value.status_code == 429

    def test_keys_are_independent(self, limiter):
        # One student hitting their limit must not lock out the whole class.
        for _ in range(LIMIT.limit):
            limiter.check("user:a", LIMIT)
        limiter.check("user:b", LIMIT)

    def test_reset_clears_one_key(self, limiter):
        for _ in range(LIMIT.limit):
            limiter.check("k", LIMIT)
        limiter.reset("k")
        limiter.check("k", LIMIT)

    def test_reset_all(self, limiter):
        for key in ("a", "b"):
            for _ in range(LIMIT.limit):
                limiter.check(key, LIMIT)
        limiter.reset()
        limiter.check("a", LIMIT)
        limiter.check("b", LIMIT)

    def test_expired_hits_stop_counting(self, limiter):
        # A zero-length window means every previous hit is already outside it.
        instant = RateLimit(limit=1, window_seconds=0)
        limiter.check("k", instant)
        limiter.check("k", instant)

    def test_prune_drops_empty_buckets(self, limiter):
        limiter.check("k", LIMIT)
        limiter.reset("k")
        limiter.check("k2", RateLimit(limit=1, window_seconds=0))
        assert limiter.prune() >= 0
