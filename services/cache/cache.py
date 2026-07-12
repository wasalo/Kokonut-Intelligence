"""Computation cache — stores and retrieves pre-computed results.

Uses PostgreSQL for storage with TTL-based expiration and
event-driven invalidation via the event bus.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("cache.computation")


class ComputationCache:
    """PostgreSQL-backed computation result cache."""

    def __init__(self, conn=None, default_ttl_seconds: int = 3600):
        self._conn = conn
        self._default_ttl = default_ttl_seconds

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def _make_key(self, computation_type: str, location_id: str | None, parameters: dict) -> str:
        """Generate a deterministic cache key."""
        param_str = json.dumps(parameters, sort_keys=True, default=str)
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
        loc_part = location_id or "global"
        return f"{computation_type}:{loc_part}:{param_hash}"

    def get(
        self,
        computation_type: str,
        location_id: str | None = None,
        parameters: dict | None = None,
    ) -> Optional[dict]:
        """Retrieve a cached result. Returns None if miss or expired."""
        key = self._make_key(computation_type, location_id, parameters or {})
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, result, computed_at, expires_at, hit_count
                    FROM cache_entry
                    WHERE cache_key = %s AND is_valid = TRUE
                    """,
                    (key,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                entry_id, result, computed_at, expires_at, hit_count = row

                # Check expiration
                if expires_at and expires_at < datetime.now(timezone.utc):
                    cur.execute(
                        "UPDATE cache_entry SET is_valid = FALSE, invalidation_reason = 'expired' WHERE id = %s",
                        (entry_id,),
                    )
                    conn.commit()
                    logger.debug("Cache expired: %s", key)
                    return None

                # Update hit stats
                cur.execute(
                    """
                    UPDATE cache_entry
                    SET hit_count = %s, last_hit_at = NOW()
                    WHERE id = %s
                    """,
                    (hit_count + 1, entry_id),
                )
                conn.commit()

                logger.debug("Cache hit: %s (hits=%d)", key, hit_count + 1)
                return {
                    "result": result,
                    "computed_at": computed_at.isoformat() if computed_at else None,
                    "hits": hit_count + 1,
                }
        except Exception:
            conn.rollback()
            logger.exception("Cache get failed for key=%s", key)
            return None

    def set(
        self,
        computation_type: str,
        result: dict,
        location_id: str | None = None,
        parameters: dict | None = None,
        ttl_seconds: int | None = None,
        computed_by: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Store a computation result. Returns the cache key."""
        key = self._make_key(computation_type, location_id, parameters or {})
        ttl = ttl_seconds or self._default_ttl
        conn = self._get_conn()

        result_json = json.dumps(result, default=str)
        result_hash = hashlib.sha256(result_json.encode()).hexdigest()[:32]
        size_bytes = len(result_json.encode())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache_entry
                        (cache_key, computation_type, location_id, parameters,
                         result, result_hash, computed_by, expires_at, size_bytes, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        result = EXCLUDED.result,
                        result_hash = EXCLUDED.result_hash,
                        computed_at = NOW(),
                        expires_at = EXCLUDED.expires_at,
                        hit_count = 0,
                        is_valid = TRUE,
                        size_bytes = EXCLUDED.size_bytes,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        key,
                        computation_type,
                        location_id,
                        json.dumps(parameters or {}, default=str),
                        result_json,
                        result_hash,
                        computed_by,
                        expires_at,
                        size_bytes,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
            conn.commit()
            logger.debug("Cache set: %s (expires=%s)", key, expires_at)
            return key
        except Exception:
            conn.rollback()
            logger.exception("Cache set failed for key=%s", key)
            raise

    def invalidate(
        self,
        computation_type: str | None = None,
        location_id: str | None = None,
        reason: str = "manual",
    ) -> int:
        """Invalidate cache entries. Returns count invalidated."""
        conn = self._get_conn()
        conditions = ["is_valid = TRUE"]
        params = []

        if computation_type:
            conditions.append("computation_type = %s")
            params.append(computation_type)
        if location_id:
            conditions.append("location_id = %s")
            params.append(location_id)

        where = " AND ".join(conditions)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE cache_entry
                    SET is_valid = FALSE,
                        invalidation_reason = %s,
                        invalidated_at = NOW()
                    WHERE {where}
                    """,
                    [reason] + params,
                )
                count = cur.rowcount
            conn.commit()
            logger.info("Invalidated %d cache entries (reason=%s)", count, reason)
            return count
        except Exception:
            conn.rollback()
            logger.exception("Cache invalidation failed")
            return 0

    def cleanup_expired(self) -> int:
        """Delete expired and invalid cache entries. Returns count deleted."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM cache_entry
                    WHERE is_valid = FALSE
                       OR expires_at < NOW() - INTERVAL '7 days'
                    """
                )
                count = cur.rowcount
            conn.commit()
            logger.info("Cleaned up %d expired cache entries", count)
            return count
        except Exception:
            conn.rollback()
            logger.exception("Cache cleanup failed")
            return 0

    def stats(self) -> dict:
        """Get cache statistics."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_entries,
                        COUNT(*) FILTER (WHERE is_valid = TRUE) as valid_entries,
                        COUNT(*) FILTER (WHERE is_valid = FALSE) as invalid_entries,
                        COALESCE(SUM(hit_count), 0) as total_hits,
                        COALESCE(AVG(hit_count), 0) as avg_hits,
                        COALESCE(SUM(size_bytes), 0) as total_size_bytes,
                        COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries
                    FROM cache_entry
                    """
                )
                row = cur.fetchone()

                cur.execute(
                    """
                    SELECT computation_type, COUNT(*), COALESCE(SUM(hit_count), 0)
                    FROM cache_entry
                    WHERE is_valid = TRUE
                    GROUP BY computation_type
                    ORDER BY COUNT(*) DESC
                    """
                )
                by_type = [
                    {"type": r[0], "entries": r[1], "hits": r[2]}
                    for r in cur.fetchall()
                ]

            return {
                "total_entries": row[0],
                "valid_entries": row[1],
                "invalid_entries": row[2],
                "total_hits": row[3],
                "avg_hits": float(row[4]) if row[4] else 0,
                "total_size_bytes": row[5],
                "expired_entries": row[6],
                "by_type": by_type,
            }
        except Exception:
            logger.exception("Cache stats failed")
            return {}
