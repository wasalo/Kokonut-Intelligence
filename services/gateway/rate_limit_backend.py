"""Replaceable rate-limit boundary; local state is not authorization state."""

import os
from typing import Protocol


class RateLimitBackend(Protocol):
    def check(self, caller: str, tokens_needed: int = 1) -> bool:
        """Atomically decide and consume tokens for the bounded caller identity."""
        ...

    def retry_after(self, caller: str, tokens_needed: int = 1) -> int:
        """Return nonnegative whole seconds until tokens may be available."""
        ...


def get_rate_limiter(provider: str | None = None) -> RateLimitBackend:
    """Select only implemented providers; never silently downgrade shared limits."""
    provider = os.environ.get("KOKONUT_RATE_LIMIT_PROVIDER", "local") if provider is None else provider
    if provider == "postgres":
        from .postgres_rate_limiter import PostgresRateLimiter

        return PostgresRateLimiter()
    if provider != "local":
        raise ValueError("KOKONUT_RATE_LIMIT_PROVIDER must be local or postgres")
    from .rate_limiter import RateLimiter

    return RateLimiter()
