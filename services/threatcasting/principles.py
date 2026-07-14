"""Principles — sustainability principles that define success, with milestone alignment.

Backcasting from principles (FSSD approach): define the desired future state via
sustainability principles, then work backward to identify milestones that move
the system toward principle satisfaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class PrincipleManager:
    """Manages sustainability principles and milestone alignment for backcasting."""

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

    def create_principle(
        self,
        narrative_id: str,
        location_id: str,
        principle_name: str,
        description: str,
        principle_type: str = "custom",
        metric_key: Optional[str] = None,
        comparison_operator: str = "gte",
        target_value: Optional[float] = None,
        target_value_upper: Optional[float] = None,
        invert_direction: bool = False,
        weight: float = 1.0,
        source_system: str = "manual",
        crisp_dimension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a sustainability principle for a narrative."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        principle_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO backcast_principle
                (id, narrative_id, location_id, principle_name, description,
                 principle_type, metric_key, comparison_operator, target_value,
                 target_value_upper, invert_direction, weight, source_system,
                 crisp_dimension)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                principle_id, narrative_id, location_id, principle_name,
                description, principle_type, metric_key, comparison_operator,
                target_value, target_value_upper, invert_direction, weight,
                source_system, crisp_dimension,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Created principle %s for narrative %s", principle_name, narrative_id)
        return result

    def get_principle(self, principle_id: str) -> Optional[Dict[str, Any]]:
        """Get a single principle."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM backcast_principle WHERE id = %s", (principle_id,))
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def list_principles(
        self,
        narrative_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List principles with optional filters."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["bp.is_active = TRUE"]
        params: list = []
        if narrative_id:
            conditions.append("bp.narrative_id = %s")
            params.append(narrative_id)
        if location_id:
            conditions.append("bp.location_id = %s")
            params.append(location_id)

        where = " AND ".join(conditions)
        cur.execute(
            f"""
            SELECT bp.*, nt.title AS narrative_title, t.threat_name
            FROM backcast_principle bp
            JOIN threat_narrative nt ON nt.id = bp.narrative_id
            JOIN threat t ON t.id = nt.threat_id
            WHERE {where}
            ORDER BY bp.created_at
            """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def delete_principle(self, principle_id: str) -> bool:
        """Soft-delete a principle by setting is_active = FALSE."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE backcast_principle SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
            (principle_id,),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted

    # ------------------------------------------------------------------
    # Alignment scoring
    # ------------------------------------------------------------------

    def _read_current_metric_value(
        self, metric_key: str, location_id: str
    ) -> Optional[float]:
        """On-demand read of the latest verified metric value."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mv.value
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND md.metric_key = %s
              AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC
            LIMIT 1
            """,
            (location_id, metric_key),
        )
        row = cur.fetchone()
        cur.close()
        return float(row[0]) if row else None

    def _read_current_crisp_score(
        self, dimension: str, location_id: str
    ) -> Optional[float]:
        """On-demand read of the latest CRISP dimension score."""
        columns = {
            "carbon_yield": "carbon_yield_score",
            "climate": "climate_score",
            "policy": "policy_score",
            "financial": "financial_score",
            "implementation": "implementation_score",
            "composite": "composite_score",
        }
        if dimension not in columns:
            raise ValueError(f"Unsupported CRISP dimension: {dimension}")

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {columns[dimension]}
            FROM crisp_risk_assessment
            WHERE location_id = %s
            ORDER BY score_computed_at DESC NULLS LAST
            LIMIT 1
            """,
            (location_id,),
        )
        row = cur.fetchone()
        cur.close()
        return float(row[0]) if row else None

    def _compute_alignment(
        self,
        current: Optional[float],
        target: Optional[float],
        target_upper: Optional[float],
        operator: str,
        invert: bool,
    ) -> float:
        """Compute alignment score from -1 (fully misaligned) to 1 (fully aligned).

        When invert=True, lower current values are better (e.g., cost, risk).
        """
        if current is None or target is None:
            return 0.0

        if operator == "between" and target_upper is not None:
            if target <= current <= target_upper:
                return 1.0
            distance = min(abs(current - target), abs(current - target_upper))
            max_distance = max(abs(target), abs(target_upper), 1.0)
            raw = 1.0 - (distance / max_distance)
        elif operator in ("gte", "gt", "lte", "lt", "eq", "neq"):
            if operator == "gte":
                raw = 1.0 if current >= target else max(0.0, 1.0 - (target - current) / max(abs(target), 1.0))
            elif operator == "gt":
                raw = 1.0 if current > target else max(0.0, 1.0 - (target - current) / max(abs(target), 1.0))
            elif operator == "lte":
                raw = 1.0 if current <= target else max(0.0, 1.0 - (current - target) / max(abs(target), 1.0))
            elif operator == "lt":
                raw = 1.0 if current < target else max(0.0, 1.0 - (current - target) / max(abs(target), 1.0))
            elif operator == "eq":
                raw = 1.0 if current == target else max(0.0, 1.0 - abs(current - target) / max(abs(target), 1.0))
            else:
                raw = 0.0
        else:
            raw = 0.0

        if invert:
            raw = -raw if raw > 0 else raw
        return round(max(-1.0, min(1.0, raw)), 4)

    def align_milestone(
        self,
        milestone_id: str,
        principle_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Compute alignment scores for a milestone against one or all principles.

        Reads current values on-demand from metric_value or crisp_risk_assessment.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        milestone = self._get_milestone(cur, milestone_id)
        if not milestone:
            cur.close()
            return []

        location_id = milestone["location_id"]

        if principle_id:
            principles = [self.get_principle(principle_id)]
            principles = [p for p in principles if p]
        else:
            principles = self._get_principles_for_narrative(cur, milestone["narrative_id"])

        results = []
        for p in principles:
            current = None
            if p["source_system"] == "metric" and p["metric_key"]:
                current = self._read_current_metric_value(p["metric_key"], location_id)
            elif p["source_system"] == "crisp" and p["crisp_dimension"]:
                current = self._read_current_crisp_score(p["crisp_dimension"], location_id)

            target = float(p["target_value"]) if p["target_value"] is not None else None
            target_upper = float(p["target_value_upper"]) if p["target_value_upper"] is not None else None

            alignment = self._compute_alignment(
                current, target, target_upper,
                p["comparison_operator"], p["invert_direction"],
            )

            gap = None
            if current is not None and target is not None:
                gap = round(current - target, 4)

            evidence = self._build_alignment_evidence(current, target, p["comparison_operator"])

            # Upsert alignment record
            cur.execute(
                """
                INSERT INTO backcast_principle_alignment
                    (milestone_id, principle_id, alignment_score, current_value,
                     target_value, gap, alignment_evidence, assessed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (milestone_id, principle_id)
                DO UPDATE SET
                    alignment_score = EXCLUDED.alignment_score,
                    current_value = EXCLUDED.current_value,
                    target_value = EXCLUDED.target_value,
                    gap = EXCLUDED.gap,
                    alignment_evidence = EXCLUDED.alignment_evidence,
                    assessed_at = NOW()
                RETURNING *
                """,
                (milestone_id, p["id"], alignment, current, target, gap, evidence),
            )
            row = dict(cur.fetchone())
            row["principle_name"] = p["principle_name"]
            row["principle_type"] = p["principle_type"]
            results.append(row)

        conn.commit()
        cur.close()
        return results

    def align_all_milestones(self, narrative_id: str) -> List[Dict[str, Any]]:
        """Batch-align all milestones in a narrative's backcast plan against all principles."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            "SELECT id FROM threat_backcast_plan WHERE narrative_id = %s ORDER BY milestone_order",
            (narrative_id,),
        )
        milestone_ids = [str(r["id"]) for r in cur.fetchall()]
        cur.close()

        all_results = []
        for mid in milestone_ids:
            results = self.align_milestone(mid)
            all_results.extend(results)

        return all_results

    def check_direction(self, plan_id: str) -> Dict[str, Any]:
        """Check whether milestones are moving toward or away from principle satisfaction.

        Aggregates alignment scores across all milestones in a plan.
        Returns overall direction: toward, away, mixed, or unknown.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            canonical_plan_id = self._resolve_plan_id(cur, plan_id)
        except ValueError as exc:
            cur.close()
            if "not found" in str(exc):
                return {"overall_direction": "unknown", "milestone_details": [], "confidence": 0.0}
            raise

        cur.execute(
            """
            SELECT pa.alignment_score, pa.current_value, pa.target_value, pa.gap,
                   bp.principle_name, bp.invert_direction, tbp.milestone_order, tbp.milestone_status
            FROM backcast_principle_alignment pa
            JOIN backcast_principle bp ON bp.id = pa.principle_id
            JOIN threat_backcast_plan tbp ON tbp.id = pa.milestone_id
            WHERE tbp.plan_id = %s
            ORDER BY tbp.milestone_order
            """,
            (canonical_plan_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not rows:
            return {"overall_direction": "unknown", "milestone_details": [], "confidence": 0.0}

        positive_count = sum(1 for r in rows if r["alignment_score"] > 0)
        negative_count = sum(1 for r in rows if r["alignment_score"] < 0)
        total = len(rows)

        if positive_count > total * 0.7:
            direction = "toward"
        elif negative_count > total * 0.7:
            direction = "away"
        else:
            direction = "mixed"

        confidence = max(positive_count, negative_count) / total if total > 0 else 0.0

        return {
            "overall_direction": direction,
            "confidence": round(confidence, 3),
            "milestone_details": rows,
        }

    # ------------------------------------------------------------------
    # Automated gap analysis
    # ------------------------------------------------------------------

    def automated_gap_analysis(self, plan_id: str) -> Dict[str, Any]:
        """Compute gap from current state to desired future using metrics + CRISP.

        Reads current metric values and CRISP scores on-demand, compares against
        all principles linked to the narrative.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            canonical_plan_id = self._resolve_plan_id(cur, plan_id)
        except ValueError as exc:
            cur.close()
            if "not found" in str(exc):
                return {"narrative_id": plan_id, "gaps": [], "summary": "No plan found"}
            raise

        cur.execute(
            "SELECT narrative_id, location_id FROM backcast_plan WHERE id = %s",
            (canonical_plan_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            return {"narrative_id": plan_id, "gaps": [], "summary": "No plan found"}

        narrative_id = row["narrative_id"]
        location_id = row["location_id"]

        # Get all principles for this narrative
        principles = self._get_principles_for_narrative(cur, narrative_id)
        cur.close()

        gaps = []
        for p in principles:
            current = None
            if p["source_system"] == "metric" and p["metric_key"]:
                current = self._read_current_metric_value(p["metric_key"], location_id)
            elif p["source_system"] == "crisp" and p["crisp_dimension"]:
                current = self._read_current_crisp_score(p["crisp_dimension"], location_id)

            target = float(p["target_value"]) if p["target_value"] is not None else None
            target_upper = float(p["target_value_upper"]) if p["target_value_upper"] is not None else None

            alignment = self._compute_alignment(
                current, target, target_upper,
                p["comparison_operator"], p["invert_direction"],
            )

            gap_value = None
            if current is not None and target is not None:
                gap_value = round(current - target, 4)

            # Priority based on weight and alignment distance
            priority = "medium"
            if abs(alignment) < 0.3:
                priority = "high"
            elif abs(alignment) > 0.8:
                priority = "low"

            gaps.append({
                "principle_id": p["id"],
                "principle_name": p["principle_name"],
                "principle_type": p["principle_type"],
                "metric_key": p.get("metric_key"),
                "crisp_dimension": p.get("crisp_dimension"),
                "current_value": current,
                "target_value": target,
                "target_value_upper": target_upper,
                "gap": gap_value,
                "alignment_score": alignment,
                "priority": priority,
                "source_system": p["source_system"],
            })

        high_priority = sum(1 for g in gaps if g["priority"] == "high")
        avg_alignment = (
            round(sum(g["alignment_score"] for g in gaps) / len(gaps), 4)
            if gaps else 0.0
        )

        return {
            "narrative_id": narrative_id,
            "location_id": location_id,
            "total_principles": len(gaps),
            "high_priority_gaps": high_priority,
            "average_alignment": avg_alignment,
            "gaps": gaps,
        }

    # ------------------------------------------------------------------
    # Effectiveness scoring
    # ------------------------------------------------------------------

    def effectiveness_score(self, plan_id: str) -> Dict[str, Any]:
        """Score milestone effectiveness using both delta and trend analysis.

        For completed milestones:
        1. Delta: compare metric value before vs after milestone completion
        2. Trend: use TrendEstimator to detect significant trends
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            canonical_plan_id = self._resolve_plan_id(cur, plan_id)
        except ValueError as exc:
            cur.close()
            if "not found" in str(exc):
                return {"plan_id": plan_id, "milestones_evaluated": 0, "results": []}
            raise

        # Get completed milestones with target dates
        cur.execute(
            """
            SELECT id, milestone_description, milestone_target_date, completion_evidence,
                   location_id, narrative_id
            FROM threat_backcast_plan
            WHERE plan_id = %s AND milestone_status = 'completed'
            ORDER BY milestone_order
            """,
            (canonical_plan_id,),
        )
        completed = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not completed:
            return {"plan_id": canonical_plan_id, "milestones_evaluated": 0, "results": []}

        # Get principles for this narrative
        narrative_id = completed[0]["narrative_id"] if completed else plan_id
        cur2 = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        principles = self._get_principles_for_narrative(cur2, narrative_id)
        cur2.close()

        results = []
        for m in completed:
            location_id = m["location_id"]
            milestone_result = {
                "milestone_id": m["id"],
                "description": m["milestone_description"],
                "target_date": str(m["milestone_target_date"]) if m["milestone_target_date"] else None,
                "principle_scores": [],
            }

            for p in principles:
                if p["source_system"] != "metric" or not p["metric_key"]:
                    continue

                metric_key = p["metric_key"]

                # Delta analysis
                delta_score = self._compute_effectiveness_delta(
                    metric_key, location_id, m["milestone_target_date"]
                )

                # Trend analysis
                trend_score = self._compute_effectiveness_trend(
                    metric_key, location_id
                )

                milestone_result["principle_scores"].append({
                    "principle_name": p["principle_name"],
                    "metric_key": metric_key,
                    "delta_score": delta_score,
                    "trend_score": trend_score,
                    "combined_score": round(
                        (delta_score * 0.5 + trend_score * 0.5), 4
                    ) if delta_score is not None and trend_score is not None else None,
                })

            results.append(milestone_result)

        avg_combined = None
        all_scores = [
            ps["combined_score"]
            for r in results
            for ps in r["principle_scores"]
            if ps["combined_score"] is not None
        ]
        if all_scores:
            avg_combined = round(sum(all_scores) / len(all_scores), 4)

        return {
            "plan_id": canonical_plan_id,
            "milestones_evaluated": len(completed),
            "average_effectiveness": avg_combined,
            "results": results,
        }

    def _compute_effectiveness_delta(
        self,
        metric_key: str,
        location_id: str,
        milestone_target_date,
    ) -> Optional[float]:
        """Compute before/after delta for a completed milestone."""
        if milestone_target_date is None:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        # Get metric value before milestone
        cur.execute(
            """
            SELECT mv.value
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND md.metric_key = %s
              AND mv.verified = TRUE
              AND mv.computed_at <= %s
            ORDER BY mv.computed_at DESC
            LIMIT 1
            """,
            (location_id, metric_key, milestone_target_date),
        )
        before = cur.fetchone()

        # Get metric value after milestone
        cur.execute(
            """
            SELECT mv.value
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND md.metric_key = %s
              AND mv.verified = TRUE
              AND mv.computed_at > %s
            ORDER BY mv.computed_at ASC
            LIMIT 1
            """,
            (location_id, metric_key, milestone_target_date),
        )
        after = cur.fetchone()
        cur.close()

        if before and after:
            before_val = float(before[0])
            after_val = float(after[0])
            if before_val != 0:
                return round((after_val - before_val) / abs(before_val), 4)
            return round(after_val - before_val, 4)

        return None

    def _compute_effectiveness_trend(
        self,
        metric_key: str,
        location_id: str,
    ) -> Optional[float]:
        """Compute trend-based effectiveness using TrendEstimator."""
        try:
            from services.trends.estimator import TrendEstimator

            estimator = TrendEstimator()
            trend = estimator.compute_trend_per_metric(
                metric_key, location_id, lookback_days=90
            )

            if trend.get("direction") == "insufficient_data":
                return None

            slope = trend.get("slope", 0.0)
            r_squared = trend.get("r_squared", 0.0)

            # Normalize: positive slope + high r_squared = high effectiveness
            direction_mult = 1.0 if slope > 0 else -1.0
            normalized = min(abs(slope) * 100, 1.0) * r_squared
            return round(direction_mult * normalized, 4)

        except Exception as e:
            logger.warning("Trend analysis failed for %s: %s", metric_key, e)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_plan_id(self, cur, identifier: str) -> str:
        """Resolve a canonical plan ID while preserving legacy single-plan inputs."""
        from services.threatcasting.backcasting import Backcaster

        return Backcaster(conn=self._get_conn())._resolve_plan_id(identifier, cur)

    def _get_milestone(self, cur, milestone_id: str) -> Optional[Dict[str, Any]]:
        """Get a milestone by ID."""
        cur.execute("SELECT * FROM threat_backcast_plan WHERE id = %s", (milestone_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def _get_principles_for_narrative(
        self, cur, narrative_id: str
    ) -> List[Dict[str, Any]]:
        """Get all active principles for a narrative."""
        cur.execute(
            """
            SELECT * FROM backcast_principle
            WHERE narrative_id = %s AND is_active = TRUE
            ORDER BY created_at
            """,
            (narrative_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def _build_alignment_evidence(
        self,
        current: Optional[float],
        target: Optional[float],
        operator: str,
    ) -> str:
        """Build human-readable alignment evidence."""
        if current is None:
            return "No current data available for comparison"
        if target is None:
            return "No target defined for comparison"

        op_map = {
            "gte": ">=",
            "gt": ">",
            "lte": "<=",
            "lt": "<",
            "eq": "==",
            "neq": "!=",
            "between": "between",
        }
        op_str = op_map.get(operator, operator)
        return f"Current {current} vs target {target} (operator: {op_str})"
