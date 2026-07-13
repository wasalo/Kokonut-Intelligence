"""Cross-Domain Insight Transfer Engine — propagates insights across domains.

When one domain discovers a pattern, automatically checks if it
applies to other domains. Pest management insights inform irrigation,
weather informs planting, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class InsightTransferEngine:
    """Propagates insights across domains using cross-domain rules."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def process_event(
        self,
        source_domain: str,
        event_type: str,
        event_data: Dict[str, Any],
        source_event_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Check if an event in one domain should trigger actions in other domains.

        Returns a list of insight transfers that were detected.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Find matching rules
        cur.execute("""
            SELECT * FROM cross_domain_rule
            WHERE source_domain = %s
              AND source_event_pattern = %s
              AND enabled = TRUE
        """, (source_domain, event_type))

        rules = [dict(r) for r in cur.fetchall()]

        transfers = []
        for rule in rules:
            transfer_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            cur.execute("""
                INSERT INTO insight_transfer (
                    id, source_domain, source_event_type, source_event_id,
                    target_domain, source_insight, target_applicability,
                    transfer_status, discovered_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'detected', %s, %s)
            """, (
                transfer_id, source_domain, event_type, source_event_id,
                rule["target_domain"],
                psycopg2.extras.Json(event_data),
                rule["confidence"],
                now, now,
            ))

            transfers.append({
                "transfer_id": transfer_id,
                "source_domain": source_domain,
                "event_type": event_type,
                "target_domain": rule["target_domain"],
                "action_template": rule["target_action_template"],
                "applicability": float(rule["confidence"]),
                "status": "detected",
            })

        conn.commit()
        cur.close()
        return transfers

    def add_rule(
        self,
        source_domain: str,
        target_domain: str,
        pattern: str,
        action_template: Dict[str, Any],
        confidence: float = 0.5,
        conditions: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Add a cross-domain insight transfer rule."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        rule_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO cross_domain_rule (
                id, source_domain, target_domain,
                source_event_pattern, target_action_template,
                applicability_conditions, confidence, enabled, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
        """, (
            rule_id, source_domain, target_domain,
            pattern, psycopg2.extras.Json(action_template),
            psycopg2.extras.Json(conditions or {}),
            confidence, now,
        ))

        conn.commit()
        cur.close()

        return {
            "id": rule_id,
            "source_domain": source_domain,
            "target_domain": target_domain,
            "pattern": pattern,
            "confidence": confidence,
        }

    def get_pending_transfers(
        self, target_domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get pending cross-domain transfers awaiting review."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["it.transfer_status IN ('detected', 'pending_review')"]
        params: list = []

        if target_domain:
            conditions.append("it.target_domain = %s")
            params.append(target_domain)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT it.*, cdr.target_action_template
            FROM insight_transfer it
            LEFT JOIN cross_domain_rule cdr ON
                cdr.source_domain = it.source_domain
                AND cdr.source_event_pattern = it.source_event_type
            WHERE {where_clause}
            ORDER BY it.discovered_at DESC
            LIMIT 50
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def resolve_transfer(
        self,
        transfer_id: str,
        outcome: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark a transfer as helpful/not_helpful for learning."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)

        cur.execute("""
            UPDATE insight_transfer
            SET outcome = %s,
                transfer_status = 'applied',
                resolved_at = %s,
                metadata = jsonb_set(
                    COALESCE(metadata, '{}'),
                    '{notes}',
                    %s::jsonb
                )
            WHERE id = %s
            RETURNING *
        """, (outcome, now, psycopg2.extras.Json(notes or ""), transfer_id))

        row = cur.fetchone()
        conn.commit()
        cur.close()

        if row:
            result = dict(row)
            # Update effectiveness of the source rule
            self._update_rule_effectiveness(
                cur if False else conn,  # Need fresh cursor
                result.get("source_domain"),
                result.get("source_event_type"),
                outcome,
            )
            return result

        return {"error": "transfer_not_found"}

    def get_transfer_stats(self) -> Dict[str, Any]:
        """Get cross-domain transfer effectiveness statistics."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                source_domain,
                target_domain,
                COUNT(*) as total_transfers,
                COUNT(*) FILTER (WHERE outcome = 'helpful') as helpful,
                COUNT(*) FILTER (WHERE outcome = 'not_helpful') as not_helpful,
                COUNT(*) FILTER (WHERE outcome = 'pending' OR outcome IS NULL) as pending,
                AVG(target_applicability) as avg_applicability
            FROM insight_transfer
            GROUP BY source_domain, target_domain
            ORDER BY total_transfers DESC
        """)

        stats = []
        for r in cur.fetchall():
            r = dict(r)
            total = r["total_transfers"]
            helpful = r["helpful"] or 0
            r["effectiveness_rate"] = round(
                (helpful / total * 100) if total > 0 else 0.0, 2
            )
            stats.append(r)

        cur.close()
        return {"domain_pairs": stats, "total_transfers": sum(s["total_transfers"] for s in stats)}

    def get_rules(
        self,
        source_domain: Optional[str] = None,
        target_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List active cross-domain rules."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["enabled = TRUE"]
        params: list = []

        if source_domain:
            conditions.append("source_domain = %s")
            params.append(source_domain)
        if target_domain:
            conditions.append("target_domain = %s")
            params.append(target_domain)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT * FROM cross_domain_rule
            WHERE {where_clause}
            ORDER BY source_domain, target_domain
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # --- Private helpers ---

    def _update_rule_effectiveness(
        self, conn, source_domain: str, event_type: str, outcome: str
    ) -> None:
        """Update rule effectiveness based on transfer outcome."""
        if not source_domain or not event_type:
            return

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Compute effectiveness from transfer outcomes
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE outcome = 'helpful') as helpful
            FROM insight_transfer
            WHERE source_domain = %s
              AND source_event_type = %s
              AND outcome IS NOT NULL
        """, (source_domain, event_type))

        row = cur.fetchone()
        if row and row.get("total", 0) > 0:
            effectiveness = round(
                ((row.get("helpful") or 0) / row["total"]) * 100, 2
            )

            cur.execute("""
                UPDATE cross_domain_rule
                SET confidence = GREATEST(0.1, LEAST(0.95, %s::numeric / 100))
                WHERE source_domain = %s
                  AND source_event_pattern = %s
                  AND enabled = TRUE
            """, (effectiveness, source_domain, event_type))

        conn.commit()
        cur.close()
