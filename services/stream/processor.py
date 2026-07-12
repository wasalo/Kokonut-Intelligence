"""Stream processor — ingests, aggregates, and detects anomalies in real-time sensor data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("stream.processor")


class StreamProcessor:
    """Lightweight stream processor for real-time sensor data."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.ingestion.base import get_db
            self._conn = get_db()
        return self._conn

    def ingest(
        self,
        sensor_device_id: str,
        metric: str,
        value: float,
        unit: str = "",
        quality: int = 100,
        timestamp: datetime | None = None,
    ) -> str:
        """Ingest a single reading into the stream buffer. Returns buffer entry ID."""
        import uuid

        ts = timestamp or datetime.now(timezone.utc)
        entry_id = str(uuid.uuid4())
        conn = self._get_conn()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stream_buffer
                        (id, sensor_device_id, metric, value, unit, quality, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (entry_id, sensor_device_id, metric, value, unit, quality, ts),
                )
            conn.commit()
            logger.debug("Ingested stream entry: %s %s=%f", sensor_device_id[:8], metric, value)
            return entry_id
        except Exception:
            conn.rollback()
            logger.exception("Stream ingest failed")
            raise

    def ingest_batch(self, readings: list[dict]) -> int:
        """Ingest multiple readings. Returns count successfully ingested."""
        conn = self._get_conn()
        count = 0

        try:
            with conn.cursor() as cur:
                for r in readings:
                    try:
                        cur.execute(
                            """
                            INSERT INTO stream_buffer
                                (sensor_device_id, metric, value, unit, quality, timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                r["sensor_device_id"],
                                r["metric"],
                                r["value"],
                                r.get("unit", ""),
                                r.get("quality", 100),
                                r.get("timestamp", datetime.now(timezone.utc)),
                            ),
                        )
                        count += 1
                    except Exception as e:
                        logger.warning("Failed to ingest reading: %s", e)
            conn.commit()
            logger.info("Batch ingested %d/%d readings", count, len(readings))
            return count
        except Exception:
            conn.rollback()
            logger.exception("Batch ingest failed")
            return count

    def process_buffer(self, batch_size: int = 500) -> dict[str, int]:
        """Process pending buffer entries into windowed aggregations."""
        from services.stream.windows import WindowAggregator

        conn = self._get_conn()
        aggregator = WindowAggregator(conn)
        stats = {"processed": 0, "aggregated": 0, "errors": 0}

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, sensor_device_id, metric, value, unit, quality, timestamp
                    FROM stream_buffer
                    WHERE NOT ingested
                    ORDER BY timestamp ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()

            if not rows:
                return stats

            for row_id, device_id, metric, value, unit, quality, ts in rows:
                try:
                    # Aggregate into windows
                    aggregator.ingest(device_id, metric, value, ts)
                    stats["aggregated"] += 1

                    # Mark as ingested
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE stream_buffer SET ingested = TRUE WHERE id = %s",
                            (row_id,),
                        )
                    stats["processed"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.warning("Failed to process buffer entry %s: %s", row_id, e)

            conn.commit()
            logger.info(
                "Buffer processed: %d aggregated, %d errors",
                stats["aggregated"], stats["errors"],
            )
            return stats
        except Exception:
            conn.rollback()
            logger.exception("Buffer processing failed")
            return stats

    def get_recent(self, sensor_device_id: str, metric: str, limit: int = 100) -> list[dict]:
        """Get recent buffer entries for a sensor/metric."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value, unit, quality, timestamp
                    FROM stream_buffer
                    WHERE sensor_device_id = %s AND metric = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (sensor_device_id, metric, limit),
                )
                return [
                    {"value": r[0], "unit": r[1], "quality": r[2], "timestamp": r[3].isoformat()}
                    for r in cur.fetchall()
                ]
        except Exception:
            logger.exception("Failed to get recent readings")
            return []

    def stats(self) -> dict:
        """Get stream processor statistics."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_buffered,
                        COUNT(*) FILTER (WHERE NOT ingested) as pending,
                        COUNT(*) FILTER (WHERE ingested) as processed,
                        MIN(timestamp) as oldest,
                        MAX(timestamp) as newest
                    FROM stream_buffer
                    """
                )
                row = cur.fetchone()

                cur.execute(
                    """
                    SELECT COUNT(*) FILTER (WHERE NOT acknowledged) as unacked,
                           COUNT(*) as total
                    FROM stream_alert
                    """
                )
                alert_row = cur.fetchone()

            return {
                "buffer": {
                    "total": row[0],
                    "pending": row[1],
                    "processed": row[2],
                    "oldest": row[3].isoformat() if row[3] else None,
                    "newest": row[4].isoformat() if row[4] else None,
                },
                "alerts": {
                    "unacknowledged": alert_row[0],
                    "total": alert_row[1],
                },
            }
        except Exception:
            logger.exception("Stream stats failed")
            return {}
