"""Signal Ingestor — aggregates external signals from various sources,
classifies them, and links to threats."""

from __future__ import annotations

import hashlib
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
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def _content_hash(self, content: str, source: str) -> str:
        """Deterministic hash for dedup: lowercased content + source."""
        normalized = f"{source.lower().strip()}:{content.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _auto_classify(
        self, conn, location_id: Optional[str], content: str,
    ) -> Optional[str]:
        """Match signal content against threat names for auto-classification.

        Returns the best-matching threat_id or None.
        """
        if not location_id or not content:
            return None
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, name FROM threat
            WHERE location_id = %s AND status != 'archived'
            """,
            (location_id,),
        )
        threats = cur.fetchall()
        cur.close()

        content_lower = content.lower()
        best_threat_id = None
        best_score = 0
        for t in threats:
            name = (t["name"] or "").lower()
            if not name:
                continue
            # Simple keyword overlap scoring
            name_words = set(name.split())
            content_words = set(content_lower.split())
            overlap = len(name_words & content_words)
            if overlap > best_score:
                best_score = overlap
                best_threat_id = t["id"]

        return best_threat_id if best_score >= 2 else None

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
        location_id: Optional[str] = None,
        dedup_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """Ingest a new signal with dedup and optional auto-classification.

        Dedup: if a signal with the same content_hash and source exists within
        dedup_window_hours, returns the existing signal instead of inserting.
        Auto-classify: if no threat_id provided, attempts keyword matching.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = datetime.now(timezone.utc)
        content_hash = self._content_hash(content, signal_source)

        # Dedup check
        cur.execute(
            """
            SELECT id FROM threat_signal
            WHERE content_hash = %s AND signal_source = %s
              AND ingested_at > NOW() - INTERVAL '%s hours'
            LIMIT 1
            """,
            (content_hash, signal_source, dedup_window_hours),
        )
        existing = cur.fetchone()
        if existing:
            cur.close()
            logger.info("Dedup: signal %s matches existing %s", content_hash, existing["id"])
            return {"id": existing["id"], "dedup": True, "message": "Signal already ingested"}

        # Auto-classify if no threat_id
        classified = False
        classification_notes = None
        if not threat_id and location_id:
            auto_threat = self._auto_classify(conn, location_id, content)
            if auto_threat:
                threat_id = auto_threat
                classified = True
                classification_notes = "auto-classified by keyword matching"

        signal_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO threat_signal
                (id, threat_id, signal_source, source_reference, signal_type,
                 content, structured_data, confidence, relevance_score,
                 sentiment, signal_date, ingested_at, classified,
                 classification_notes, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                signal_id, threat_id, signal_source, source_reference, signal_type,
                content, psycopg2.extras.Json(structured_data or {}),
                confidence, relevance_score, sentiment,
                signal_date or now, now, classified, classification_notes, content_hash,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Ingested signal %s from %s (auto_classified=%s)", signal_id, signal_source, classified)
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
