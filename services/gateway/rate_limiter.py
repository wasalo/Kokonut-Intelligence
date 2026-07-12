"""Gateway rate limiter — per-caller token bucket rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from services.common.logging import get_logger

logger = get_logger("gateway.rate_limiter")


class RateLimiter:
    """In-memory token bucket rate limiter per caller."""

    def __init__(self, max_tokens: int = 100, refill_rate: float = 10.0):
        self._max_tokens = max_tokens
        self._refill_rate = refill_rate  # tokens per second
        self._buckets: dict[str, dict] = defaultdict(lambda: {
            "tokens": max_tokens,
            "last_refill": time.monotonic(),
        })

    def check(self, caller: str, tokens_needed: int = 1) -> bool:
        """Check if caller has enough tokens. Consumes tokens if available."""
        bucket = self._buckets[caller]
        now = time.monotonic()

        # Refill tokens
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            self._max_tokens,
            bucket["tokens"] + elapsed * self._refill_rate,
        )
        bucket["last_refill"] = now

        # Check and consume
        if bucket["tokens"] >= tokens_needed:
            bucket["tokens"] -= tokens_needed
            return True

        logger.warning("Rate limit exceeded for caller: %s", caller)
        return False

    def get_status(self, caller: str) -> dict:
        """Get rate limit status for a caller."""
        bucket = self._buckets[caller]
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        tokens = min(self._max_tokens, bucket["tokens"] + elapsed * self._refill_rate)
        return {
            "caller": caller,
            "tokens_available": int(tokens),
            "max_tokens": self._max_tokens,
            "refill_rate": self._refill_rate,
        }

    def reset(self, caller: str) -> None:
        """Reset rate limit for a caller."""
        self._buckets[caller] = {
            "tokens": self._max_tokens,
            "last_refill": time.monotonic(),
        }
