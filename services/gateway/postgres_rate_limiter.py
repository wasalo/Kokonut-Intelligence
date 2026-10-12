"""Shared fixed-policy token buckets serialized by PostgreSQL row locks."""

import hashlib
import math

from .rate_limiter import RateLimiter


class PostgresRateLimiter:
    """100-token capacity, 10 tokens/second; PostgreSQL supplies the clock."""

    def _budget(self, caller: str, tokens_needed: int, *, consume: bool) -> tuple[bool, int]:
        RateLimiter._validate_request(caller, tokens_needed)
        if tokens_needed > 100:
            raise ValueError("tokens_needed exceeds bucket capacity")
        from services.common.cli import get_connection

        key = hashlib.sha256(caller.encode("utf-8")).hexdigest()
        with get_connection(connect_timeout=3) as conn:
            conn.execute("SET LOCAL lock_timeout = '2s'")
            conn.execute("SET LOCAL statement_timeout = '3s'")
            conn.execute(
                """INSERT INTO gateway_rate_bucket (caller_hash, tokens)
                   VALUES (:key, 100) ON CONFLICT (caller_hash) DO NOTHING""", {"key": key},
            )
            row = conn.execute(
                "SELECT tokens, updated_at FROM gateway_rate_bucket WHERE caller_hash = :key FOR UPDATE",
                {"key": key},
            ).first()
            now = conn.execute("SELECT clock_timestamp() AS now").first()["now"]
            elapsed = max(0, (now - row["updated_at"]).total_seconds())
            tokens = min(100.0, row["tokens"] + elapsed * 10)
            allowed = tokens >= tokens_needed
            if consume and allowed:
                tokens -= tokens_needed
            conn.execute(
                "UPDATE gateway_rate_bucket SET tokens = :tokens, updated_at = :now WHERE caller_hash = :key",
                {"tokens": tokens, "now": now, "key": key},
            )
        return allowed, max(1, math.ceil(max(0, tokens_needed - tokens) / 10))

    def check(self, caller: str, tokens_needed: int = 1) -> bool:
        return self._budget(caller, tokens_needed, consume=True)[0]

    def retry_after(self, caller: str, tokens_needed: int = 1) -> int:
        return self._budget(caller, tokens_needed, consume=False)[1]
