"""Gateway rate limiter — per-caller token bucket rate limiting."""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from threading import RLock

from services.common.logging import get_logger

logger = get_logger("gateway.rate_limiter")


class RateLimiter:
    """In-memory token bucket rate limiter per caller."""

    def __init__(self, max_tokens: int = 100, refill_rate: float = 10.0, max_callers: int = 10_000):
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if isinstance(max_callers, bool) or not isinstance(max_callers, int) or max_callers <= 0:
            raise ValueError("max_callers must be a positive integer")
        if isinstance(refill_rate, bool) or not isinstance(refill_rate, (int, float)) or not math.isfinite(refill_rate) or refill_rate <= 0:
            raise ValueError("refill_rate must be finite and positive")
        self._lock = RLock()
        self._max_tokens = max_tokens
        self._refill_rate = refill_rate  # tokens per second
        self._max_callers = max_callers
        self._buckets: OrderedDict[str, dict] = OrderedDict()

    def _get_bucket(self, caller: str) -> dict:
        bucket = self._buckets.get(caller)
        if bucket is None:
            if len(self._buckets) >= self._max_callers:
                self._buckets.popitem(last=False)
            bucket = {"tokens": self._max_tokens, "last_refill": time.monotonic()}
            self._buckets[caller] = bucket
        else:
            self._buckets.move_to_end(caller)
        return bucket

    def check(self, caller: str, tokens_needed: int = 1) -> bool:
        """Check if caller has enough tokens. Consumes tokens if available."""
        self._validate_request(caller, tokens_needed)
        if tokens_needed > self._max_tokens:
            raise ValueError("tokens_needed exceeds bucket capacity")
        with self._lock:
            return self._check(caller, tokens_needed)

    @staticmethod
    def _validate_request(caller: str, tokens_needed: int) -> None:
        if not isinstance(caller, str) or not caller or len(caller) > 255:
            raise ValueError("caller must be a nonempty string of at most 255 characters")
        if isinstance(tokens_needed, bool) or not isinstance(tokens_needed, int) or tokens_needed <= 0:
            raise ValueError("tokens_needed must be a positive integer")

    def _check(self, caller: str, tokens_needed: int) -> bool:
        bucket = self._get_bucket(caller)
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

    def retry_after(self, caller: str, tokens_needed: int = 1) -> int:
        """Return whole seconds until the caller can obtain more tokens."""
        self._validate_request(caller, tokens_needed)
        if tokens_needed > self._max_tokens:
            raise ValueError("tokens_needed exceeds bucket capacity")
        with self._lock:
            return self._retry_after(caller, tokens_needed)

    def _retry_after(self, caller: str, tokens_needed: int) -> int:
        bucket = self._get_bucket(caller)
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        tokens = min(self._max_tokens, bucket["tokens"] + elapsed * self._refill_rate)
        missing = max(0.0, tokens_needed - tokens)
        return max(1, int((missing / self._refill_rate) + 0.999))

    def get_status(self, caller: str) -> dict:
        """Get rate limit status for a caller."""
        self._validate_request(caller, 1)
        with self._lock:
            return self._get_status(caller)

    def _get_status(self, caller: str) -> dict:
        bucket = self._get_bucket(caller)
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
        self._buckets.move_to_end(caller)
