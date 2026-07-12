"""Mental Model Elicitor — captures and compares stakeholder worldviews.

Provides structured elicitation of mental models along predefined
worldview dimensions, enabling alignment and dialogue between stakeholders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import WORLDVIEW_DIMENSIONS


class MentalModelElicitor:
    """Captures and compares stakeholder mental models."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def list_dimensions(self) -> List[Dict[str, Any]]:
        """List all worldview dimensions."""
        return WORLDVIEW_DIMENSIONS

    def elicit_worldview(
        self,
        stakeholder_id: str,
        stakeholder_type: str,
        dimension: str,
        position: float,
        position_label: Optional[str] = None,
        rationale: Optional[str] = None,
        captured_by: str = "system",
    ) -> str:
        """Capture a stakeholder's position on a worldview dimension.

        Args:
            stakeholder_id: UUID of the stakeholder.
            stakeholder_type: Type of stakeholder (farmer, investor, community, etc.).
            dimension: Worldview dimension key.
            position: Float 0.0-1.0 (0=low end, 1=high end).
            position_label: Human-readable label for this position.
            rationale: Why they hold this position.
            captured_by: Who captured this.

        Returns:
            The mental model record ID.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        model_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Auto-generate label if not provided
        if position_label is None:
            dim_config = next(
                (d for d in WORLDVIEW_DIMENSIONS if d["dimension"] == dimension),
                None,
            )
            if dim_config:
                if position < 0.3:
                    position_label = dim_config["label_low"]
                elif position > 0.7:
                    position_label = dim_config["label_high"]
                else:
                    position_label = "Moderate"

        cur.execute("""
            INSERT INTO mental_model (
                id, stakeholder_id, stakeholder_type, worldview_dimension,
                position, position_label, rationale, captured_at, captured_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            model_id, stakeholder_id, stakeholder_type, dimension,
            position, position_label, rationale, now, captured_by,
        ))

        conn.commit()
        cur.close()
        return model_id

    def compare_worldviews(
        self, stakeholder_ids: List[str]
    ) -> Dict[str, Any]:
        """Compare worldviews across multiple stakeholders.

        Returns alignment scores and divergence points.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        placeholders = ", ".join(["%s"] * len(stakeholder_ids))
        cur.execute(f"""
            SELECT
                stakeholder_id,
                stakeholder_type,
                worldview_dimension,
                position,
                position_label
            FROM mental_model
            WHERE stakeholder_id IN ({placeholders})
            ORDER BY worldview_dimension, stakeholder_id
        """, stakeholder_ids)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not rows:
            return {"stakeholders": stakeholder_ids, "dimension_count": 0, "dimensions": [], "alignment_scores": {}, "overall_alignment": 0.0, "divergence_points": []}

        # Group by dimension
        by_dimension = {}
        for row in rows:
            dim = row["worldview_dimension"]
            if dim not in by_dimension:
                by_dimension[dim] = []
            by_dimension[dim].append(row)

        # Compute alignment per dimension
        dimensions = []
        alignment_scores = {}

        for dim, entries in by_dimension.items():
            positions = [e["position"] for e in entries]
            avg = sum(positions) / len(positions)
            spread = max(positions) - min(positions)
            alignment = max(0, 1.0 - spread)  # 1=perfect alignment, 0=max divergence

            alignment_scores[dim] = round(alignment, 3)
            dimensions.append({
                "dimension": dim,
                "positions": [
                    {
                        "stakeholder_id": e["stakeholder_id"],
                        "stakeholder_type": e["stakeholder_type"],
                        "position": e["position"],
                        "position_label": e["position_label"],
                    }
                    for e in entries
                ],
                "average_position": round(avg, 3),
                "spread": round(spread, 3),
                "alignment": round(alignment, 3),
            })

        overall_alignment = (
            sum(alignment_scores.values()) / len(alignment_scores)
            if alignment_scores else 0.0
        )

        return {
            "stakeholders": stakeholder_ids,
            "dimension_count": len(dimensions),
            "dimensions": dimensions,
            "alignment_scores": alignment_scores,
            "overall_alignment": round(overall_alignment, 3),
            "divergence_points": [
                dim for dim, score in alignment_scores.items() if score < 0.5
            ],
        }

    def suggest_dialogue(
        self, comparison: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Suggest dialogue topics based on worldview comparison.

        Focuses on areas of high divergence that need alignment.
        """
        suggestions = []

        for dim in comparison.get("dimensions", []):
            if dim["alignment"] < 0.5:
                positions = dim["positions"]
                if len(positions) >= 2:
                    suggestions.append({
                        "dimension": dim["dimension"],
                        "priority": "high" if dim["alignment"] < 0.3 else "medium",
                        "topic": f"Align on {dim['dimension'].replace('_', ' ')}",
                        "context": f"Spread: {dim['spread']:.2f} (alignment: {dim['alignment']:.2f})",
                        "participants": [p["stakeholder_id"] for p in positions],
                        "suggested_question": self._get_dialogue_question(dim["dimension"]),
                    })

        suggestions.sort(key=lambda x: x["priority"] == "high", reverse=True)
        return suggestions

    def get_stakeholder_worldview(
        self, stakeholder_id: str
    ) -> List[Dict[str, Any]]:
        """Get all worldview positions for a stakeholder."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM mental_model
            WHERE stakeholder_id = %s
            ORDER BY worldview_dimension
        """, (stakeholder_id,))

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def _get_dialogue_question(self, dimension: str) -> str:
        """Generate a dialogue question for a worldview dimension."""
        questions = {
            "regenerative_vs_industrial": "What practices do we believe will best sustain long-term productivity?",
            "short_term_vs_long_term": "What time horizon should our decisions prioritize?",
            "individual_vs_collective": "How do we balance individual farm needs with community wellbeing?",
            "risk_aversion_vs_taking": "What level of risk is acceptable for potential breakthrough outcomes?",
            "technology_adoption": "Which technologies should we adopt and at what pace?",
            "market_orientation": "Should we focus on subsistence or market-oriented production?",
            "data_trust": "How much should we rely on data vs. intuition in decision-making?",
            "governance_preference": "How should decisions be made — centrally or distributed?",
        }
        return questions.get(dimension, f"How do we align on {dimension}?")
