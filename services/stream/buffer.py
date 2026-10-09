"""Stream buffer — manages backpressure for high-throughput sensor ingestion."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from services.common.logging import get_logger

logger = get_logger("stream.buffer")


class StreamBuffer:
    """Manages buffer cleanup and backpressure for the stream processor."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def cleanup(self, max_age_minutes: int = 60, batch_size: int = 1000) -> int:
        """Delete old ingested buffer entries. Returns count deleted."""
        conn = self._get_conn()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM stream_buffer
                    WHERE ingested = TRUE AND created_at < %s
                    LIMIT %s
                    """,
                    (cutoff, batch_size),
                )
                count = cur.rowcount
            conn.commit()
            logger.info("Cleaned up %d old buffer entries", count)
            return count
        except Exception:
            conn.rollback()
            logger.exception("Buffer cleanup failed")
            return 0

    def pending_count(self) -> int:
        """Get count of unprocessed buffer entries."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM stream_buffer WHERE NOT ingested")
                return cur.fetchone()[0]
        except Exception:
            logger.exception("Failed to get pending count")
            return 0

    def oldest_pending(self) -> Optional[datetime]:
        """Get timestamp of oldest unprocessed entry."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MIN(timestamp) FROM stream_buffer WHERE NOT ingested"
                )
                row = cur.fetchone()
                return row[0] if row and row[0] else None
        except Exception:
            logger.exception("Failed to get oldest pending")
            return None

    def pressure_ratio(self) -> float:
        """Calculate backpressure ratio (0.0 = no pressure, 1.0 = full)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE NOT ingested) as pending,
                        COUNT(*) as total
                    FROM stream_buffer
                    """
                )
                row = cur.fetchone()
                if not row or row[1] == 0:
                    return 0.0
                return min(row[0] / max(row[1], 1), 1.0)
        except Exception:
            logger.exception("Failed to calculate pressure ratio")
            return 0.0
