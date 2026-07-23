"""Path Comparison — compare multiple backcasting routes to the same desirable future.

Supports auto-scoring from metrics/CRISP/desirability data and manual user overrides.
The hybrid approach combines system-computed scores with human judgment.
"""

from __future__ import annotations

import uuid
import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)

SCORING_VERSION = "v2"

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
            from services.common.database import get_db
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
        if len(set(narrative_ids)) != len(narrative_ids):
            raise ValueError("Narrative IDs must be unique")

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        effective_criteria = self._validate_criteria(criteria or deepcopy(DEFAULT_CRITERIA))
        cur.execute(
            """
            SELECT tn.id
            FROM threat_narrative tn
            JOIN threat t ON t.id = tn.threat_id
            WHERE tn.id = ANY(%s) AND t.location_id = %s
            """,
            (narrative_ids, location_id),
        )
        found = {str(row["id"]) for row in cur.fetchall()}
        missing = set(narrative_ids) - found
        if missing:
            cur.close()
            raise ValueError("All narratives must exist and belong to the comparison location")

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

    def _validate_criteria(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Validate supported criteria and finite positive weights."""
        if not criteria:
            raise ValueError("At least one comparison criterion is required")
        unknown = set(criteria) - set(DEFAULT_CRITERIA)
        if unknown:
            raise ValueError(f"Unsupported comparison criteria: {', '.join(sorted(unknown))}")
        total = 0.0
        for name, config in criteria.items():
            weight = config.get("weight") if isinstance(config, dict) else config
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(f"Criterion {name} requires a numeric weight")
            weight = float(weight)
            if not math.isfinite(weight) or weight <= 0:
                raise ValueError(f"Criterion {name} weight must be finite and positive")
            total += weight
        if total <= 0:
            raise ValueError("Comparison criterion weights must total more than zero")
        return deepcopy(criteria)

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

        scores: Dict[str, Dict[str, Optional[float]]] = {}

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

        # Compute weighted final scores
        final_scores = self._compute_final_scores(scores, criteria)
        completeness = self._compute_completeness(scores, criteria)
        premortem = self._premortem_completeness(cur, comparison_id, narrative_ids)
        cur.close()

        evaluation_status, winner_id, winner_score = self._select_winner(
            final_scores, completeness, premortem
        )

        # Build rationale
        rationale = self._build_rationale(narrative_ids, scores, final_scores, winner_id)

        # Update comparison record
        self._update_comparison(
            comparison_id, scores, final_scores, completeness, evaluation_status,
            winner_id, winner_score, rationale
        )

        return {
            "comparison_id": comparison_id,
            "comparison_name": comparison["comparison_name"],
            "auto_scores": scores,
            "final_scores": final_scores,
            "score_completeness": completeness,
            "premortem_completeness": premortem,
            "evaluation_status": evaluation_status,
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

        criteria = self._validate_criteria(comparison["comparison_criteria"] or deepcopy(DEFAULT_CRITERIA))
        auto_scores = comparison["auto_scores"] or {}
        narrative_ids = comparison["narrative_ids"]
        self._validate_manual_scores(user_scores, narrative_ids, criteria)

        # Merge: 50/50 weight between auto and manual
        merged_scores: Dict[str, Dict[str, Optional[float]]] = {}
        for nid in narrative_ids:
            merged_scores[nid] = {}
            for criterion in criteria:
                auto_val = auto_scores.get(nid, {}).get(criterion)
                manual_val = user_scores.get(nid, {}).get(criterion)
                if manual_val is None:
                    merged = auto_val
                elif auto_val is None:
                    merged = manual_val
                else:
                    merged = (auto_val * 0.5) + (manual_val * 0.5)
                merged_scores[nid][criterion] = round(merged, 4) if merged is not None else None

        # Compute final scores
        final_scores = self._compute_final_scores(merged_scores, criteria)

        completeness = self._compute_completeness(merged_scores, criteria)
        conn = self._get_conn()
        cur = conn.cursor()
        premortem = self._premortem_completeness(cur, comparison_id, narrative_ids)
        evaluation_status, winner_id, winner_score = self._select_winner(
            final_scores, completeness, premortem
        )

        rationale = self._build_rationale(narrative_ids, merged_scores, final_scores, winner_id)

        # Update with manual scores
        cur.execute(
            """
            UPDATE backcast_path_comparison
            SET manual_scores = %s, final_scores = %s,
                score_completeness = %s, evaluation_status = %s,
                winner_narrative_id = %s, winner_score = %s, rationale = %s,
                scoring_version = %s, evaluated_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (
                psycopg2.extras.Json(user_scores),
                psycopg2.extras.Json(final_scores),
                psycopg2.extras.Json(completeness), evaluation_status,
                winner_id, winner_score, rationale, SCORING_VERSION, comparison_id,
            ),
        )
        conn.commit()
        cur.close()

        return {
            "comparison_id": comparison_id,
            "manual_scores": user_scores,
            "merged_scores": merged_scores,
            "final_scores": final_scores,
            "score_completeness": completeness,
            "premortem_completeness": premortem,
            "evaluation_status": evaluation_status,
            "winner_narrative_id": winner_id,
            "winner_score": winner_score,
            "rationale": rationale,
        }

    def _validate_manual_scores(self, user_scores, narrative_ids, criteria) -> None:
        unknown_paths = set(user_scores) - set(narrative_ids)
        if unknown_paths:
            raise ValueError("Manual scores include narratives outside the comparison")
        for narrative_id, values in user_scores.items():
            if not isinstance(values, dict):
                raise ValueError(f"Manual scores for {narrative_id} must be an object")
            unknown_criteria = set(values) - set(criteria)
            if unknown_criteria:
                raise ValueError("Manual scores include unsupported criteria")
            for value in values.values():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("Manual scores must be numeric")
                if not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
                    raise ValueError("Manual scores must be finite values from 0 to 1")

    # ------------------------------------------------------------------
    # Premortem governance
    # ------------------------------------------------------------------

    def upsert_premortem(
        self, comparison_id: str, narrative_id: str, failure_modes: List[Dict[str, Any]],
        assumptions: Optional[List[Dict[str, Any]]] = None,
        early_warning_signals: Optional[List[Dict[str, Any]]] = None,
        mitigations: Optional[List[Dict[str, Any]]] = None,
        residual_risk_notes: Optional[str] = None,
        evidence_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        comparison = self.get_comparison(comparison_id)
        if not comparison or narrative_id not in comparison["narrative_ids"]:
            raise ValueError("Narrative must belong to the path comparison")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO backcast_path_premortem (
                comparison_id, narrative_id, failure_modes, assumptions,
                early_warning_signals, mitigations, residual_risk_notes, evidence_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (comparison_id, narrative_id) DO UPDATE SET
                failure_modes = EXCLUDED.failure_modes,
                assumptions = EXCLUDED.assumptions,
                early_warning_signals = EXCLUDED.early_warning_signals,
                mitigations = EXCLUDED.mitigations,
                residual_risk_notes = EXCLUDED.residual_risk_notes,
                evidence_notes = EXCLUDED.evidence_notes,
                status = 'draft', submitted_by = NULL, submitted_at = NULL,
                verified_by = NULL, verified_at = NULL, verification_notes = NULL,
                updated_at = NOW()
            WHERE backcast_path_premortem.status IN ('draft', 'rejected')
            RETURNING *
            """,
            (
                comparison_id, narrative_id, psycopg2.extras.Json(failure_modes),
                psycopg2.extras.Json(assumptions or []),
                psycopg2.extras.Json(early_warning_signals or []),
                psycopg2.extras.Json(mitigations or []), residual_risk_notes, evidence_notes,
            ),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            raise ValueError("Submitted or verified premortems cannot be edited")
        conn.commit()
        cur.close()
        return dict(row)

    def submit_premortem(self, premortem_id: str, submitted_by: str) -> Dict[str, Any]:
        if not submitted_by.strip():
            raise ValueError("submitted_by is required")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            UPDATE backcast_path_premortem
            SET status = 'submitted', submitted_by = %s, submitted_at = NOW(), updated_at = NOW()
            WHERE id = %s AND status IN ('draft', 'rejected')
              AND jsonb_array_length(failure_modes) > 0
              AND NOT EXISTS (
                  SELECT 1 FROM jsonb_array_elements(failure_modes) mode
                  WHERE NULLIF(BTRIM(mode->>'description'), '') IS NULL
              )
            RETURNING *
            """,
            (submitted_by, premortem_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            raise ValueError("Premortem must be editable and include described failure modes")
        conn.commit()
        cur.close()
        return dict(row)

    def review_premortem(
        self, premortem_id: str, result: str, reviewer_id: str, notes: str
    ) -> Dict[str, Any]:
        if result not in {"verified", "rejected"}:
            raise ValueError("Premortem review result must be verified or rejected")
        try:
            uuid.UUID(reviewer_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("reviewer_id must be a UUID") from exc
        if not notes.strip():
            raise ValueError("verification notes are required")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            UPDATE backcast_path_premortem
            SET status = %s, verified_by = %s,
                verified_at = CASE WHEN %s = 'verified' THEN NOW() ELSE NULL END,
                verification_notes = %s, updated_at = NOW()
            WHERE id = %s AND status = 'submitted'
            RETURNING *
            """,
            (result, reviewer_id, result, notes, premortem_id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            raise ValueError("Only submitted premortems can be reviewed")
        conn.commit()
        cur.close()
        return dict(row)

    def list_premortems(self, comparison_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        params = [comparison_id]
        status_clause = ""
        if status:
            if status not in {"draft", "submitted", "verified", "rejected"}:
                raise ValueError("Invalid premortem status")
            status_clause = " AND status = %s"
            params.append(status)
        cur.execute(
            f"SELECT * FROM backcast_path_premortem WHERE comparison_id = %s{status_clause} ORDER BY created_at",
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
        return rows

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _score_cost(self, cur, narrative_id: str) -> Optional[float]:
        """Score cost: fewer resource requirements = higher score (0-1)."""
        plan_id = self._resolve_narrative_plan_id(cur, narrative_id)
        if plan_id is None:
            return None
        cur.execute(
            """
            SELECT resource_requirements
            FROM threat_backcast_plan
            WHERE plan_id = %s AND resource_requirements IS NOT NULL
            """,
            (plan_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return None

        # Simple heuristic: count non-empty resource fields
        resource_count = sum(
            1 for r in rows
            if r.get("resource_requirements") and r["resource_requirements"].strip()
        )
        total = len(rows) if rows else 1

        # Fewer resources = higher score
        return round(max(0.0, 1.0 - (resource_count / max(total, 1))), 4)

    def _score_time(self, cur, narrative_id: str) -> Optional[float]:
        """Score time: earlier completion = higher score (0-1)."""
        plan_id = self._resolve_narrative_plan_id(cur, narrative_id)
        if plan_id is None:
            return None
        cur.execute(
            """
            SELECT milestone_target_date
            FROM threat_backcast_plan
            WHERE plan_id = %s AND milestone_target_date IS NOT NULL
            ORDER BY milestone_target_date DESC
            LIMIT 1
            """,
            (plan_id,),
        )
        row = cur.fetchone()
        if not row or not row.get("milestone_target_date"):
            return None

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

    def _resolve_narrative_plan_id(self, cur, narrative_id: str) -> Optional[str]:
        """Return the sole plan for a narrative; ambiguous paths remain unscored."""
        cur.execute(
            "SELECT id FROM backcast_plan WHERE narrative_id = %s ORDER BY created_at",
            (narrative_id,),
        )
        plan_ids = list(dict.fromkeys(str(row["id"]) for row in cur.fetchall()))
        if len(plan_ids) != 1:
            if len(plan_ids) > 1:
                logger.warning(
                    "Narrative %s has multiple backcast plans; cost/time scores are unknown",
                    narrative_id,
                )
            return None
        return plan_ids[0]

    def _score_risk(self, cur, narrative_id: str, location_id: str) -> Optional[float]:
        """Score risk: lower linked threat severity = higher score (0-1)."""
        cur.execute(
            """
            SELECT t.severity_potential, t.probability
            FROM threat t
            JOIN threat_narrative tn ON tn.threat_id = t.id
            WHERE tn.id = %s AND t.location_id = %s
            """,
            (narrative_id, location_id),
        )
        row = cur.fetchone()
        if not row:
            return None

        severity_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        severity = severity_map.get(row.get("severity_potential"))
        if severity is None or row.get("probability") is None:
            return None
        probability = float(row["probability"])

        risk = severity * probability
        return round(max(0.0, 1.0 - risk), 4)

    def _score_desirability(self, cur, narrative_id: str) -> Optional[float]:
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
            return None

        score = float(row["desirability_score"])
        # desirability_score is -1 to 1, normalize to 0-1
        return round((score + 1.0) / 2.0, 4)

    def _score_principle_alignment(self, cur, narrative_id: str) -> Optional[float]:
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
            return None

        avg = float(row["avg_alignment"])
        # alignment_score is -1 to 1, normalize to 0-1
        return round((avg + 1.0) / 2.0, 4)

    def _compute_final_scores(
        self,
        scores: Dict[str, Dict[str, Optional[float]]],
        criteria: Dict[str, Any],
    ) -> Dict[str, Optional[float]]:
        """Compute weighted final scores for each narrative."""
        final = {}
        for nid, criterion_scores in scores.items():
            weighted_sum = 0.0
            total_weight = 0.0
            for criterion, weight_info in criteria.items():
                weight = weight_info.get("weight", 0.2) if isinstance(weight_info, dict) else weight_info
                value = criterion_scores.get(criterion)
                if value is None:
                    continue
                weighted_sum += value * weight
                total_weight += weight

            if total_weight > 0:
                final[nid] = round(weighted_sum / total_weight, 4)
            else:
                final[nid] = None

        return final

    def _compute_completeness(self, scores, criteria) -> Dict[str, Any]:
        total_weight = sum(
            float(config.get("weight", 0.0) if isinstance(config, dict) else config)
            for config in criteria.values()
        )
        paths = {}
        for narrative_id, values in scores.items():
            known = [name for name in criteria if values.get(name) is not None]
            unknown = [name for name in criteria if values.get(name) is None]
            known_weight = sum(
                float(criteria[name].get("weight", 0.0) if isinstance(criteria[name], dict) else criteria[name])
                for name in known
            )
            paths[narrative_id] = {
                "known_criteria": known,
                "unknown_criteria": unknown,
                "known_weight": round(known_weight, 4),
                "total_weight": round(total_weight, 4),
                "ratio": round(known_weight / total_weight, 4) if total_weight else 0.0,
            }
        return {
            "paths": paths,
            "all_paths_complete": bool(paths) and all(not p["unknown_criteria"] for p in paths.values()),
        }

    def _premortem_completeness(self, cur, comparison_id, narrative_ids) -> Dict[str, Any]:
        cur.execute(
            """
            SELECT narrative_id, status
            FROM backcast_path_premortem
            WHERE comparison_id = %s
            """,
            (comparison_id,),
        )
        statuses = {str(row["narrative_id"]): row["status"] for row in cur.fetchall()}
        missing = [nid for nid in narrative_ids if statuses.get(nid) != "verified"]
        return {
            "verified_paths": [nid for nid in narrative_ids if statuses.get(nid) == "verified"],
            "missing_or_unverified_paths": missing,
            "all_paths_verified": not missing,
        }

    def _select_winner(self, final_scores, completeness, premortem):
        if not completeness["all_paths_complete"] or not premortem["all_paths_verified"]:
            return "incomplete", None, None
        ranked = [(nid, score) for nid, score in final_scores.items() if score is not None]
        if len(ranked) != len(final_scores) or not ranked:
            return "incomplete", None, None
        ranked.sort(key=lambda item: item[1], reverse=True)
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            return "indeterminate", None, None
        return "complete", ranked[0][0], ranked[0][1]

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
        auto_scores: Dict[str, Dict[str, Optional[float]]],
        final_scores: Dict[str, Optional[float]],
        completeness: Dict[str, Any],
        evaluation_status: str,
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
                score_completeness = %s, evaluation_status = %s,
                winner_narrative_id = %s, winner_score = %s, rationale = %s,
                scoring_version = %s, evaluated_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (
                psycopg2.extras.Json(auto_scores),
                psycopg2.extras.Json(final_scores),
                psycopg2.extras.Json(completeness), evaluation_status,
                winner_id, winner_score, rationale, SCORING_VERSION, comparison_id,
            ),
        )
        conn.commit()
        cur.close()
