"""Shared fixed-policy token buckets serialized by PostgreSQL row locks."""

import hashlib

from .rate_limiter import RateLimiter


class PostgresRateLimiter:
    """100-token capacity, 10 tokens/second; PostgreSQL supplies the clock."""

    def _budget(self, caller: str, tokens_needed: int, *, consume: bool) -> tuple[bool, int]:
        RateLimiter._validate_request(caller, tokens_needed)
        if tokens_needed > 100:
            raise ValueError("tokens_needed exceeds bucket capacity")
        if not isinstance(consume, bool):
            raise ValueError("consume must be a boolean")
        from services.common.cli import get_connection

        key = hashlib.sha256(caller.encode("utf-8")).hexdigest()
        with get_connection(connect_timeout=3) as conn:
            conn.execute("SET LOCAL lock_timeout = '2s'")
            conn.execute("SET LOCAL statement_timeout = '3s'")
            row = conn.execute(
                """SELECT allowed, retry_after_seconds
                     FROM kokonut_security.consume_gateway_rate_bucket(
                         :caller_hash, :tokens_needed, :consume
                     )""",
                {
                    "caller_hash": key,
                    "tokens_needed": tokens_needed,
                    "consume": consume,
                },
            ).first()
            if row is None:
                raise RuntimeError("PostgreSQL rate limiter returned no decision")
            allowed = row.get("allowed")
            retry_after_seconds = row.get("retry_after_seconds")
            if type(allowed) is not bool:
                raise RuntimeError("PostgreSQL rate limiter returned an invalid decision")
            if (
                isinstance(retry_after_seconds, bool)
                or not isinstance(retry_after_seconds, int)
                or retry_after_seconds < 1
            ):
                raise RuntimeError("PostgreSQL rate limiter returned an invalid retry interval")
        return allowed, retry_after_seconds

    def check(self, caller: str, tokens_needed: int = 1) -> bool:
        return self._budget(caller, tokens_needed, consume=True)[0]

    def retry_after(self, caller: str, tokens_needed: int = 1) -> int:
        return self._budget(caller, tokens_needed, consume=False)[1]
