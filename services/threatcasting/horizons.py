"""Horizon Planner — multi-timeframe planning, threat linking, review cycles."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class HorizonPlanner:
    """Manages multi-horizon planning for threats."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def create_horizon(
        self,
        location_id: str,
        horizon_name: str,
        horizon_years: int,
        description: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        desirability_framework: str = "gnh_aligned",
        review_frequency_months: int = 12,
    ) -> Dict[str, Any]:
        """Create a new planning horizon."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        horizon_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        next_review = now + timedelta(days=review_frequency_months * 30)

        cur.execute(
            """
            INSERT INTO threat_horizon
                (id, location_id, horizon_name, horizon_years, description,
                 focus_areas, desirability_framework, review_frequency_months,
                 next_review_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                horizon_id, location_id, horizon_name, horizon_years, description,
                focus_areas or [], desirability_framework, review_frequency_months,
                next_review,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created horizon %s: %s (%d years)", horizon_id, horizon_name, horizon_years)
        return result

    def get_horizon(self, horizon_id: str) -> Optional[Dict[str, Any]]:
        """Get a single horizon."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT h.*, l.name AS location_name
            FROM threat_horizon h
            LEFT JOIN location l ON l.id = h.location_id
            WHERE h.id = %s
            """,
            (horizon_id,),
        )
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def get_horizons(
        self,
        location_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get horizons with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions: list = []
        params: list = []

        if location_id:
            conditions.append("h.location_id = %s")
            params.append(location_id)
        if active_only:
            conditions.append("h.is_active = TRUE")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        cur.execute(
            f"""
            SELECT h.*, l.name AS location_name,
                   (SELECT COUNT(*) FROM threat_horizon_threat ht WHERE ht.horizon_id = h.id) AS linked_threat_count
            FROM threat_horizon h
            LEFT JOIN location l ON l.id = h.location_id
            WHERE {where_clause}
            ORDER BY h.horizon_years
            """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def add_threat_to_horizon(
        self,
        horizon_id: str,
        threat_id: str,
        relevance_score: Optional[float] = None,
        time_to_impact_years: Optional[float] = None,
        priority_rank: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Link a threat to a horizon."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        link_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO threat_horizon_threat
                (id, horizon_id, threat_id, relevance_score,
                 time_to_impact_years, priority_rank, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (link_id, horizon_id, threat_id, relevance_score,
             time_to_impact_years, priority_rank, notes),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Linked threat %s to horizon %s", threat_id, horizon_id)
        return result

    def remove_threat_from_horizon(self, horizon_id: str, threat_id: str) -> bool:
        """Unlink a threat from a horizon."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM threat_horizon_threat WHERE horizon_id = %s AND threat_id = %s",
            (horizon_id, threat_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted

    def get_horizon_overview(self, horizon_id: str) -> Dict[str, Any]:
        """Get full overview of a horizon with linked threats and narratives."""
        horizon = self.get_horizon(horizon_id)
        if not horizon:
            return {"error": "Horizon not found"}

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get linked threats
        cur.execute(
            """
            SELECT ht.*, t.threat_name, t.threat_type, t.severity_potential,
                   t.probability, t.velocity, t.reversibility
            FROM threat_horizon_threat ht
            JOIN threat t ON t.id = ht.threat_id
            WHERE ht.horizon_id = %s
            ORDER BY ht.priority_rank NULLS LAST, ht.relevance_score DESC
            """,
            (horizon_id,),
        )
        threats = [dict(r) for r in cur.fetchall()]

        # Get narratives for linked threats
        threat_ids = [t["threat_id"] for t in threats]
        if threat_ids:
            placeholders = ",".join(["%s"] * len(threat_ids))
            cur.execute(
                f"""
                SELECT n.*, t.threat_name
                FROM threat_narrative n
                JOIN threat t ON t.id = n.threat_id
                WHERE n.threat_id IN ({placeholders})
                ORDER BY n.probability_estimate DESC NULLS LAST
                """,
                threat_ids,
            )
            narratives = [dict(r) for r in cur.fetchall()]
        else:
            narratives = []

        cur.close()

        return {
            "horizon": horizon,
            "threats": threats,
            "narratives": narratives,
            "summary": {
                "threat_count": len(threats),
                "narrative_count": len(narratives),
                "threat_types": list(set(t["threat_type"] for t in threats)),
                "avg_relevance": round(
                    sum(float(t.get("relevance_score") or 0) for t in threats) / len(threats), 4
                ) if threats else 0,
            },
        }

    def compare_horizons(
        self,
        horizon_ids: List[str],
    ) -> Dict[str, Any]:
        """Compare multiple horizons."""
        horizons = []
        for hid in horizon_ids:
            overview = self.get_horizon_overview(hid)
            if "error" not in overview:
                horizons.append(overview)

        if not horizons:
            return {"error": "No valid horizons found"}

        return {
            "horizon_count": len(horizons),
            "horizons": [
                {
                    "id": h["horizon"]["id"],
                    "name": h["horizon"]["horizon_name"],
                    "years": h["horizon"]["horizon_years"],
                    "threat_count": h["summary"]["threat_count"],
                    "narrative_count": h["summary"]["narrative_count"],
                    "avg_relevance": h["summary"]["avg_relevance"],
                }
                for h in horizons
            ],
            "total_threats": sum(h["summary"]["threat_count"] for h in horizons),
            "total_narratives": sum(h["summary"]["narrative_count"] for h in horizons),
        }

    def review_horizon(self, horizon_id: str) -> Dict[str, Any]:
        """Trigger a horizon review cycle."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            UPDATE threat_horizon
            SET last_reviewed_at = NOW(),
                next_review_at = NOW() + (review_frequency_months || ' months')::INTERVAL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (horizon_id,),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Reviewed horizon %s", horizon_id)
        return result

    def delete_horizon(self, horizon_id: str) -> bool:
        """Delete a horizon and its links."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_horizon WHERE id = %s", (horizon_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
