"""Narrative Engine — constructs threat scenario stories, evaluates
desirability, and compares narratives."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class NarrativeEngine:
    """Creates, evaluates, and manages threat narratives."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def create_narrative(
        self,
        threat_id: str,
        narrative_type: str,
        title: str,
        summary: str,
        detailed_story: str,
        timeline_years: int,
        probability_estimate: Optional[float] = None,
        impact_severity: Optional[str] = None,
        key_indicators: Optional[List[str]] = None,
        recommended_preparedness: Optional[str] = None,
        recommended_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new threat narrative."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        narrative_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO threat_narrative
                (id, threat_id, narrative_type, title, summary, detailed_story,
                 timeline_years, probability_estimate, impact_severity,
                 key_indicators, recommended_preparedness, recommended_response)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                narrative_id, threat_id, narrative_type, title, summary, detailed_story,
                timeline_years, probability_estimate, impact_severity,
                key_indicators or [], recommended_preparedness, recommended_response,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created narrative %s: %s (%s)", narrative_id, title, narrative_type)
        return result

    def get_narrative(self, narrative_id: str) -> Optional[Dict[str, Any]]:
        """Get a single narrative."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT n.*, t.threat_name, t.threat_type
            FROM threat_narrative n
            JOIN threat t ON t.id = n.threat_id
            WHERE n.id = %s
            """,
            (narrative_id,),
        )
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def get_narratives(
        self,
        threat_id: Optional[str] = None,
        narrative_type: Optional[str] = None,
        location_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get narratives with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions: list = []
        params: list = []

        if threat_id:
            conditions.append("n.threat_id = %s")
            params.append(threat_id)
        if narrative_type:
            conditions.append("n.narrative_type = %s")
            params.append(narrative_type)
        if location_id:
            conditions.append("t.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        cur.execute(
            f"""
            SELECT n.*, t.threat_name, t.threat_type
            FROM threat_narrative n
            JOIN threat t ON t.id = n.threat_id
            WHERE {where_clause}
            ORDER BY n.created_at DESC
            LIMIT %s
            """,
            params + [limit],
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def update_narrative(
        self,
        narrative_id: str,
        **updates: Any,
    ) -> Dict[str, Any]:
        """Update narrative fields."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        allowed_fields = {
            "title", "summary", "detailed_story", "probability_estimate",
            "desirability_score", "impact_severity", "key_indicators",
            "cascading_effects", "recommended_preparedness", "recommended_response",
            "is_primary", "metadata",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered:
            cur.close()
            return {"error": "No valid fields to update"}

        set_parts = []
        set_values = []
        for field, value in filtered.items():
            set_parts.append(f"{field} = %s")
            set_values.append(psycopg2.extras.Json(value) if isinstance(value, dict) else value)

        set_parts.append("updated_at = NOW()")

        cur.execute(
            f"""
            UPDATE threat_narrative
            SET {', '.join(set_parts)}
            WHERE id = %s
            RETURNING *
            """,
            set_values + [narrative_id],
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result

    def compare_narratives(
        self,
        narrative_ids: List[str],
    ) -> Dict[str, Any]:
        """Compare multiple narratives side-by-side."""
        if len(narrative_ids) < 2:
            return {"error": "Need at least 2 narratives to compare"}

        narratives = []
        for nid in narrative_ids:
            n = self.get_narrative(nid)
            if n:
                narratives.append(n)

        if not narratives:
            return {"error": "No narratives found"}

        # Build comparison
        types = [n["narrative_type"] for n in narratives]
        probabilities = [float(n.get("probability_estimate") or 0) for n in narratives]
        desirability = [float(n.get("desirability_score") or 0) for n in narratives]

        return {
            "narrative_count": len(narratives),
            "narratives": narratives,
            "type_distribution": {t: types.count(t) for t in set(types)},
            "avg_probability": round(sum(probabilities) / len(probabilities), 4) if probabilities else 0,
            "avg_desirability": round(sum(desirability) / len(desirability), 4) if desirability else 0,
            "most_probable": max(narratives, key=lambda n: float(n.get("probability_estimate") or 0))["id"],
            "most_desirable": max(narratives, key=lambda n: float(n.get("desirability_score") or 0))["id"],
        }

    def get_narrative_by_horizon(
        self,
        horizon_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all narratives for threats linked to a horizon."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT n.*, t.threat_name, t.threat_type
            FROM threat_narrative n
            JOIN threat t ON t.id = n.threat_id
            JOIN threat_horizon_threat ht ON ht.threat_id = t.id
            WHERE ht.horizon_id = %s
            ORDER BY n.probability_estimate DESC NULLS LAST
            """,
            (horizon_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def delete_narrative(self, narrative_id: str) -> bool:
        """Delete a narrative."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_narrative WHERE id = %s", (narrative_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
