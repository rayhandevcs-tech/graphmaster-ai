"""Token-bucket rate limiting.

Backed by an in-process dictionary. This is correct for a single API instance,
which is the deployment this project targets; across several replicas each
holds its own counters, so the effective limit multiplies by the replica count.
That is an acceptable trade for not requiring Redis — the limits here exist to
blunt brute-force and XP farming, not to meter a paid API. The ``RateLimiter``
interface is the seam where a shared backend would attach.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitError


@dataclass(frozen=True)
class RateLimit:
    """``limit`` requests per ``window_seconds``."""

    limit: int
    window_seconds: int

    @property
    def description(self) -> str:
        return f"{self.limit} per {self.window_seconds}s"


# Limits from docs/architecture/04-api-design.md §5.3.
AUTH_LIMIT = RateLimit(limit=10, window_seconds=300)
PASSWORD_RESET_LIMIT = RateLimit(limit=3, window_seconds=3600)
UPLOAD_LIMIT = RateLimit(limit=30, window_seconds=3600)
ANALYZE_LIMIT = RateLimit(limit=60, window_seconds=3600)
DEFAULT_LIMIT = RateLimit(limit=300, window_seconds=300)


@dataclass
class _Bucket:
    hits: list[float] = field(default_factory=list)


class RateLimiter:
    """Sliding-window counter.

    A sliding window rather than a fixed one: a fixed window lets a caller
    spend the whole allowance at the end of one window and again at the start
    of the next, which is twice the intended rate at the boundary.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)

    def check(self, key: str, limit: RateLimit) -> None:
        """Record a hit, raising ``RateLimitError`` if the limit is exceeded."""
        now = time.monotonic()
        cutoff = now - limit.window_seconds
        bucket = self._buckets[key]

        # Drop hits that have aged out before counting.
        bucket.hits = [t for t in bucket.hits if t > cutoff]

        if len(bucket.hits) >= limit.limit:
            retry_after = max(1, int(bucket.hits[0] + limit.window_seconds - now) + 1)
            raise RateLimitError(
                retry_after=retry_after,
                message=(
                    f"Too many requests ({limit.description}). "
                    f"Try again in {retry_after} seconds."
                ),
            )

        bucket.hits.append(now)

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)

    def prune(self) -> int:
        """Drop empty buckets so the dictionary does not grow without bound."""
        now = time.monotonic()
        stale = [
            key
            for key, bucket in self._buckets.items()
            if not bucket.hits or now - bucket.hits[-1] > 3600
        ]
        for key in stale:
            del self._buckets[key]
        return len(stale)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """The caller's address, honouring a single trusted proxy hop.

    X-Forwarded-For is client-controlled and trivially spoofed, so this is only
    sound behind a proxy that overwrites it. Without a proxy the direct peer
    address is used.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, limit: RateLimit, *, key_suffix: str | None = None) -> None:
    """Apply ``limit`` to this request, keyed by user when authenticated."""
    if not get_settings().RATE_LIMIT_ENABLED:
        return

    user_id = getattr(request.state, "user_id", None)
    identity = f"user:{user_id}" if user_id else f"ip:{client_ip(request)}"
    scope = key_suffix or request.url.path
    limiter.check(f"{identity}:{scope}", limit)
