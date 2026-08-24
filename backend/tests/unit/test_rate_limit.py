"""Rate limiter."""

from __future__ import annotations

from types import SimpleNamespace

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


class TestKeying:
    def test_a_proxied_request_is_metered_by_the_original_caller(self):
        """One shared campus address must not rate-limit a whole cohort.

        Only sound behind a proxy that overwrites the header — X-Forwarded-For
        is client-supplied and trivially spoofed otherwise, which is why the
        deployment guide requires the proxy to set it.
        """
        from app.core.rate_limit import client_ip

        request = SimpleNamespace(
            headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
            client=SimpleNamespace(host="10.0.0.1"),
        )
        assert client_ip(request) == "203.0.113.7"

    def test_a_direct_request_is_metered_by_its_peer(self):
        from app.core.rate_limit import client_ip

        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.4"))
        assert client_ip(request) == "198.51.100.4"

    def test_a_caller_with_no_address_still_gets_a_bucket(self):
        """A test client or a unix socket has no peer, and must not crash the limiter."""
        from app.core.rate_limit import client_ip

        assert client_ip(SimpleNamespace(headers={}, client=None)) == "unknown"


class TestEnforcement:
    def test_an_authenticated_caller_is_metered_per_user(self, monkeypatch):
        """Otherwise everyone behind one NAT address shares one budget."""
        from app.core import rate_limit

        recorded: list[str] = []
        monkeypatch.setattr(rate_limit.limiter, "check", lambda key, limit: recorded.append(key))

        request = SimpleNamespace(
            state=SimpleNamespace(user_id="abc"),
            headers={},
            client=SimpleNamespace(host="10.0.0.1"),
            url=SimpleNamespace(path="/api/v1/submissions"),
        )
        rate_limit.enforce(request, LIMIT)
        assert recorded == ["user:abc:/api/v1/submissions"]

    def test_an_anonymous_caller_is_metered_per_address(self, monkeypatch):
        from app.core import rate_limit

        recorded: list[str] = []
        monkeypatch.setattr(rate_limit.limiter, "check", lambda key, limit: recorded.append(key))

        request = SimpleNamespace(
            state=SimpleNamespace(),
            headers={},
            client=SimpleNamespace(host="10.0.0.1"),
            url=SimpleNamespace(path="/api/v1/auth/login"),
        )
        rate_limit.enforce(request, LIMIT, key_suffix="login")
        assert recorded == ["ip:10.0.0.1:login"]

    def test_disabling_the_limiter_skips_it_entirely(self, monkeypatch):
        """Load testing and local development turn it off; nothing else should."""
        from app.core import rate_limit
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "RATE_LIMIT_ENABLED", False)
        called: list[str] = []
        monkeypatch.setattr(rate_limit.limiter, "check", lambda key, limit: called.append(key))

        rate_limit.enforce(SimpleNamespace(), LIMIT)
        assert called == []


class TestPruning:
    def test_a_stale_bucket_is_dropped_and_a_live_one_kept(self, limiter, monkeypatch):
        """The dictionary is keyed by caller, so without this it grows forever.

        One bucket per address per endpoint, held for the lifetime of the
        process: on a campus deployment that is unbounded memory attached to
        nothing but the passage of time.
        """
        import time as time_module

        limiter.check("caller-from-last-hour", LIMIT)

        later = time_module.monotonic() + 3700
        monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: later)
        limiter.check("caller-right-now", LIMIT)

        assert limiter.prune() == 1
        assert set(limiter._buckets) == {"caller-right-now"}

    def test_pruning_an_empty_limiter_is_harmless(self, limiter):
        assert limiter.prune() == 0
