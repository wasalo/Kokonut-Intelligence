"""Signal Ingestor — aggregates external signals from various sources,
classifies them, and links to threats."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class SignalIngestor:
    """Ingests, classifies, and manages threat signals."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def ingest_signal(
        self,
        signal_source: str,
        content: str,
        signal_type: str = "text",
        threat_id: Optional[str] = None,
        source_reference: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        relevance_score: Optional[float] = None,
        sentiment: Optional[float] = None,
        signal_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Ingest a new signal."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        signal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute(
            """
            INSERT INTO threat_signal
                (id, threat_id, signal_source, source_reference, signal_type,
                 content, structured_data, confidence, relevance_score,
                 sentiment, signal_date, ingested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                signal_id, threat_id, signal_source, source_reference, signal_type,
                content, psycopg2.extras.Json(structured_data or {}),
                confidence, relevance_score, sentiment,
                signal_date or now, now,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Ingested signal %s from %s", signal_id, signal_source)
        return result

    def classify_signal(
        self,
        signal_id: str,
        threat_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a signal and link to a threat."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            UPDATE threat_signal
            SET threat_id = %s, classified = TRUE, classification_notes = %s
            WHERE id = %s
            RETURNING *
            """,
            (threat_id, notes, signal_id),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Classified signal %s → threat %s", signal_id, threat_id)
        return result

    def get_signals(
        self,
        location_id: Optional[str] = None,
        threat_id: Optional[str] = None,
        signal_source: Optional[str] = None,
        classified: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get signals with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions: list = []
        params: list = []

        if threat_id:
            conditions.append("s.threat_id = %s")
            params.append(threat_id)
        if signal_source:
            conditions.append("s.signal_source = %s")
            params.append(signal_source)
        if classified is not None:
            conditions.append("s.classified = %s")
            params.append(classified)
        if location_id:
            conditions.append("t.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Add join for location filter
        join_clause = "LEFT JOIN threat t ON t.id = s.threat_id" if location_id else ""

        cur.execute(
            f"""
            SELECT s.*
            FROM threat_signal s
            {join_clause}
            WHERE {where_clause}
            ORDER BY s.signal_date DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def get_unclassified_signals(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get unclassified signals for manual review."""
        return self.get_signals(classified=False, limit=limit)

    def aggregate_signals_by_threat(
        self,
        threat_id: str,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Aggregate signals for a threat over a time period."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT
                signal_source,
                signal_type,
                COUNT(*) AS count,
                AVG(confidence) AS avg_confidence,
                AVG(sentiment) AS avg_sentiment,
                MIN(signal_date) AS earliest,
                MAX(signal_date) AS latest
            FROM threat_signal
            WHERE threat_id = %s
              AND signal_date > NOW() - INTERVAL '%s days'
            GROUP BY signal_source, signal_type
            ORDER BY count DESC
            """,
            (threat_id, days),
        )
        aggregates = [dict(r) for r in cur.fetchall()]

        # Get total count
        cur.execute(
            """
            SELECT COUNT(*) AS total, AVG(confidence) AS avg_confidence, AVG(sentiment) AS avg_sentiment
            FROM threat_signal
            WHERE threat_id = %s AND signal_date > NOW() - INTERVAL '%s days'
            """,
            (threat_id, days),
        )
        totals = dict(cur.fetchone())

        # Get timeline
        cur.execute(
            """
            SELECT
                DATE(signal_date) AS day,
                COUNT(*) AS count
            FROM threat_signal
            WHERE threat_id = %s AND signal_date > NOW() - INTERVAL '%s days'
            GROUP BY DATE(signal_date)
            ORDER BY day
            """,
            (threat_id, days),
        )
        timeline = [dict(r) for r in cur.fetchall()]
        cur.close()

        return {
            "threat_id": threat_id,
            "period_days": days,
            "total_signals": totals["total"],
            "avg_confidence": round(float(totals["avg_confidence"] or 0), 4),
            "avg_sentiment": round(float(totals["avg_sentiment"] or 0), 4),
            "by_source_and_type": aggregates,
            "daily_timeline": timeline,
        }

    def get_signal_summary(self, location_id: str) -> Dict[str, Any]:
        """Get signal summary for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT
                s.signal_source,
                s.classified,
                COUNT(*) AS count
            FROM threat_signal s
            LEFT JOIN threat t ON t.id = s.threat_id
            WHERE t.location_id = %s OR s.threat_id IS NULL
            GROUP BY s.signal_source, s.classified
            ORDER BY count DESC
            """,
            (location_id,),
        )
        by_source = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE classified = FALSE) AS unclassified
            FROM threat_signal s
            LEFT JOIN threat t ON t.id = s.threat_id
            WHERE t.location_id = %s OR s.threat_id IS NULL
            """,
            (location_id,),
        )
        totals = dict(cur.fetchone())
        cur.close()

        return {
            "location_id": location_id,
            "total_signals": totals["total"],
            "unclassified": totals["unclassified"],
            "by_source": by_source,
        }

    def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_signal WHERE id = %s", (signal_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
