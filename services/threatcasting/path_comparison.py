"""Path Comparison — compare multiple backcasting routes to the same desirable future.

Supports auto-scoring from metrics/CRISP/desirability data and manual user overrides.
The hybrid approach combines system-computed scores with human judgment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)

# Default criteria and their weights
DEFAULT_CRITERIA = {
    "cost": {"weight": 0.25, "description": "Estimated resource cost to implement"},
    "time": {"weight": 0.20, "description": "Time to complete all milestones"},
    "risk": {"weight": 0.25, "description": "Risk of failure or adverse outcomes"},
    "desirability": {"weight": 0.15, "description": "Alignment with desired future"},
    "principle_alignment": {"weight": 0.15, "description": "Average principle alignment score"},
}


class PathComparator:
    """Compares multiple backcasting routes to the same desirable future."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_comparison(
        self,
        location_id: str,
        comparison_name: str,
        narrative_ids: List[str],
        criteria: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a path comparison with criteria weights.

        criteria: {"cost": {"weight": 0.3}, "time": {"weight": 0.2}, ...}
        If not provided, uses DEFAULT_CRITERIA.
        """
        if not narrative_ids or len(narrative_ids) < 2:
            raise ValueError("At least two narrative IDs are required for comparison")

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        effective_criteria = criteria or DEFAULT_CRITERIA

        comparison_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO backcast_path_comparison
                (id, location_id, comparison_name, narrative_ids, comparison_criteria)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (comparison_id, location_id, comparison_name, narrative_ids,
             psycopg2.extras.Json(effective_criteria)),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created path comparison %s with %d paths", comparison_name, len(narrative_ids))
        return result

    def get_comparison(self, comparison_id: str) -> Optional[Dict[str, Any]]:
        """Get a single path comparison."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM backcast_path_comparison WHERE id = %s", (comparison_id,))
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def list_comparisons(self, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List path comparisons with optional location filter."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if location_id:
            cur.execute(
                """
                SELECT bpc.*, nt.title AS winner_title
                FROM backcast_path_comparison bpc
                LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id
                WHERE bpc.location_id = %s
                ORDER BY bpc.created_at DESC
                """,
                (location_id,),
            )
        else:
            cur.execute(
                """
                SELECT bpc.*, nt.title AS winner_title
                FROM backcast_path_comparison bpc
                LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id
                ORDER BY bpc.created_at DESC
                """
            )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def delete_comparison(self, comparison_id: str) -> bool:
        """Delete a path comparison."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM backcast_path_comparison WHERE id = %s", (comparison_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted

    # ------------------------------------------------------------------
    # Auto-scoring
    # ------------------------------------------------------------------

    def evaluate_paths(self, comparison_id: str) -> Dict[str, Any]:
        """Auto-score all paths and rank them.

        Scoring logic per criterion:
        - cost: fewer resource requirements = higher score
        - time: earlier completion = higher score
        - risk: lower linked threat severity = higher score
        - desirability: higher narrative desirability_score = higher score
        - principle_alignment: higher average alignment = higher score
        """
        comparison = self.get_comparison(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison {comparison_id} not found")

        narrative_ids = comparison["narrative_ids"]
        location_id = comparison["location_id"]
        criteria = comparison["comparison_criteria"] or DEFAULT_CRITERIA

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        scores: Dict[str, Dict[str, float]] = {}

        for nid in narrative_ids:
            path_scores = {}

            # Cost scoring
            path_scores["cost"] = self._score_cost(cur, nid)

            # Time scoring
            path_scores["time"] = self._score_time(cur, nid)

            # Risk scoring
            path_scores["risk"] = self._score_risk(cur, nid, location_id)

            # Desirability scoring
            path_scores["desirability"] = self._score_desirability(cur, nid)

            # Principle alignment scoring
            path_scores["principle_alignment"] = self._score_principle_alignment(cur, nid)

            scores[nid] = path_scores

        cur.close()

        # Compute weighted final scores
        final_scores = self._compute_final_scores(scores, criteria)

        # Determine winner
        winner_id = None
        winner_score = None
        if final_scores:
            winner_id = max(final_scores, key=final_scores.get)
            winner_score = final_scores[winner_id]

        # Build rationale
        rationale = self._build_rationale(narrative_ids, scores, final_scores, winner_id)

        # Update comparison record
        self._update_comparison(
            comparison_id, scores, final_scores, winner_id, winner_score, rationale
        )

        return {
            "comparison_id": comparison_id,
            "comparison_name": comparison["comparison_name"],
            "auto_scores": scores,
            "final_scores": final_scores,
            "winner_narrative_id": winner_id,
            "winner_score": winner_score,
            "rationale": rationale,
        }

    # ------------------------------------------------------------------
    # Manual scoring
    # ------------------------------------------------------------------

    def manual_compare(
        self,
        comparison_id: str,
        user_scores: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Apply manual user scores and merge with auto scores.

        user_scores: {narrative_id: {criterion: score}}
        Scores are 0.0 to 1.0 per criterion.
        """
        comparison = self.get_comparison(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison {comparison_id} not found")

        criteria = comparison["comparison_criteria"] or DEFAULT_CRITERIA
        auto_scores = comparison["auto_scores"] or {}
        narrative_ids = comparison["narrative_ids"]

        # Merge: 50/50 weight between auto and manual
        merged_scores: Dict[str, Dict[str, float]] = {}
        for nid in narrative_ids:
            merged_scores[nid] = {}
            for criterion in criteria:
                auto_val = auto_scores.get(nid, {}).get(criterion, 0.0)
                manual_val = user_scores.get(nid, {}).get(criterion, 0.0)
                merged_scores[nid][criterion] = round((auto_val * 0.5 + manual_val * 0.5), 4)

        # Compute final scores
        final_scores = self._compute_final_scores(merged_scores, criteria)

        # Determine winner
        winner_id = None
        winner_score = None
        if final_scores:
            winner_id = max(final_scores, key=final_scores.get)
            winner_score = final_scores[winner_id]

        rationale = self._build_rationale(narrative_ids, merged_scores, final_scores, winner_id)

        # Update with manual scores
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE backcast_path_comparison
            SET manual_scores = %s, final_scores = %s,
                winner_narrative_id = %s, winner_score = %s, rationale = %s
            WHERE id = %s
            """,
            (
                psycopg2.extras.Json(user_scores),
                psycopg2.extras.Json(final_scores),
                winner_id, winner_score, rationale, comparison_id,
            ),
        )
        conn.commit()
        cur.close()

        return {
            "comparison_id": comparison_id,
            "manual_scores": user_scores,
            "merged_scores": merged_scores,
            "final_scores": final_scores,
            "winner_narrative_id": winner_id,
            "winner_score": winner_score,
            "rationale": rationale,
        }

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _score_cost(self, cur, narrative_id: str) -> float:
        """Score cost: fewer resource requirements = higher score (0-1)."""
        cur.execute(
            """
            SELECT resource_requirements
            FROM threat_backcast_plan
            WHERE narrative_id = %s AND resource_requirements IS NOT NULL
            """,
            (narrative_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return 0.5

        # Simple heuristic: count non-empty resource fields
        resource_count = sum(
            1 for r in rows
            if r.get("resource_requirements") and r["resource_requirements"].strip()
        )
        total = len(rows) if rows else 1

        # Fewer resources = higher score
        return round(max(0.0, 1.0 - (resource_count / max(total, 1))), 4)

    def _score_time(self, cur, narrative_id: str) -> float:
        """Score time: earlier completion = higher score (0-1)."""
        cur.execute(
            """
            SELECT milestone_target_date
            FROM threat_backcast_plan
            WHERE narrative_id = %s AND milestone_target_date IS NOT NULL
            ORDER BY milestone_target_date DESC
            LIMIT 1
            """,
            (narrative_id,),
        )
        row = cur.fetchone()
        if not row or not row.get("milestone_target_date"):
            return 0.5

        from datetime import date
        target = row["milestone_target_date"]
        if isinstance(target, str):
            target = date.fromisoformat(target)

        today = date.today()
        days_remaining = (target - today).days

        # Score: 1 year = 1.0, 5+ years = 0.0
        if days_remaining <= 0:
            return 1.0
        years = days_remaining / 365.25
        return round(max(0.0, 1.0 - (years / 5.0)), 4)

    def _score_risk(self, cur, narrative_id: str, location_id: str) -> float:
        """Score risk: lower linked threat severity = higher score (0-1)."""
        cur.execute(
            """
            SELECT t.severity_potential, t.probability
            FROM threat t
            JOIN threat_narrative tn ON tn.threat_id = t.id
            WHERE tn.id = %s
            """,
            (narrative_id,),
        )
        row = cur.fetchone()
        if not row:
            return 0.5

        severity_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        severity = severity_map.get(row.get("severity_potential", "medium"), 0.5)
        probability = float(row.get("probability", 0.5) or 0.5)

        risk = severity * probability
        return round(max(0.0, 1.0 - risk), 4)

    def _score_desirability(self, cur, narrative_id: str) -> float:
        """Score desirability: higher narrative desirability_score = higher score."""
        cur.execute(
            """
            SELECT desirability_score
            FROM threat_narrative
            WHERE id = %s
            """,
            (narrative_id,),
        )
        row = cur.fetchone()
        if not row or row.get("desirability_score") is None:
            return 0.5

        score = float(row["desirability_score"])
        # desirability_score is -1 to 1, normalize to 0-1
        return round((score + 1.0) / 2.0, 4)

    def _score_principle_alignment(self, cur, narrative_id: str) -> float:
        """Score principle alignment: higher average alignment = higher score."""
        cur.execute(
            """
            SELECT AVG(pa.alignment_score) AS avg_alignment
            FROM backcast_principle_alignment pa
            JOIN backcast_principle bp ON bp.id = pa.principle_id
            WHERE bp.narrative_id = %s
            """,
            (narrative_id,),
        )
        row = cur.fetchone()
        if not row or row.get("avg_alignment") is None:
            return 0.5

        avg = float(row["avg_alignment"])
        # alignment_score is -1 to 1, normalize to 0-1
        return round((avg + 1.0) / 2.0, 4)

    def _compute_final_scores(
        self,
        scores: Dict[str, Dict[str, float]],
        criteria: Dict[str, Any],
    ) -> Dict[str, float]:
        """Compute weighted final scores for each narrative."""
        final = {}
        for nid, criterion_scores in scores.items():
            weighted_sum = 0.0
            total_weight = 0.0
            for criterion, weight_info in criteria.items():
                weight = weight_info.get("weight", 0.2) if isinstance(weight_info, dict) else weight_info
                value = criterion_scores.get(criterion, 0.5)
                weighted_sum += value * weight
                total_weight += weight

            if total_weight > 0:
                final[nid] = round(weighted_sum / total_weight, 4)
            else:
                final[nid] = 0.5

        return final

    def _build_rationale(
        self,
        narrative_ids: List[str],
        scores: Dict[str, Dict[str, float]],
        final_scores: Dict[str, float],
        winner_id: Optional[str],
    ) -> str:
        """Build human-readable rationale for the comparison."""
        if not winner_id:
            return "No clear winner determined"

        parts = [f"Winner: {winner_id} (score: {final_scores.get(winner_id, 0):.4f})"]

        # Find strongest and weakest criteria for winner
        winner_scores = scores.get(winner_id, {})
        if winner_scores:
            strongest = max(winner_scores, key=winner_scores.get)
            weakest = min(winner_scores, key=winner_scores.get)
            parts.append(f"Strongest criterion: {strongest} ({winner_scores[strongest]:.4f})")
            parts.append(f"Weakest criterion: {weakest} ({winner_scores[weakest]:.4f})")

        # Compare with other paths
        for nid in narrative_ids:
            if nid != winner_id:
                diff = final_scores.get(winner_id, 0) - final_scores.get(nid, 0)
                parts.append(f"vs {nid}: +{diff:.4f}")

        return "; ".join(parts)

    def _update_comparison(
        self,
        comparison_id: str,
        auto_scores: Dict[str, Dict[str, float]],
        final_scores: Dict[str, float],
        winner_id: Optional[str],
        winner_score: Optional[float],
        rationale: str,
    ) -> None:
        """Update comparison record with scoring results."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE backcast_path_comparison
            SET auto_scores = %s, final_scores = %s,
                winner_narrative_id = %s, winner_score = %s, rationale = %s
            WHERE id = %s
            """,
            (
                psycopg2.extras.Json(auto_scores),
                psycopg2.extras.Json(final_scores),
                winner_id, winner_score, rationale, comparison_id,
            ),
        )
        conn.commit()
        cur.close()
