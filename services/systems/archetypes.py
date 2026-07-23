"""System Archetype Detector — identifies common systemic traps in farm data.

Detects patterns like "fixes that fail", "shifting the burden", and
"tragedy of the commons" from operational data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .config import ARCHETYPES


class ArchetypeDetector:
    """Detects system archetypes from farm operational data."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def detect(self, location_id: str) -> List[Dict[str, Any]]:
        """Run all archetype detectors for a location.

        Returns list of detected archetypes with evidence and confidence.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        detected = []

        detectors = [
            self._detect_fixes_that_fail,
            self._detect_shifting_the_burden,
            self._detect_erosion_of_goals,
            self._detect_escalation,
            self._detect_success_to_successful,
            self._detect_tragedy_of_commons,
        ]

        for detector in detectors:
            result = detector(cur, location_id)
            if result is not None and result["confidence"] > 0.3:
                detected.append(result)

                # Persist detection
                cur.execute("""
                    INSERT INTO system_archetype (
                        id, archetype_name, location_id, confidence,
                        evidence, active_variables, suggested_intervention, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                """, (
                    str(uuid.uuid4()), result["archetype_name"],
                    location_id, result["confidence"],
                    psycopg2.extras.Json(result["evidence"]),
                    psycopg2.extras.Json(result["active_variables"]),
                    result["suggested_intervention"],
                ))

        conn.commit()
        cur.close()

        detected.sort(key=lambda x: x["confidence"], reverse=True)
        return detected

    def list_active(self, location_id: str) -> List[Dict[str, Any]]:
        """List active archetypes for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM system_archetype
            WHERE location_id = %s AND status = 'active'
            ORDER BY detected_at DESC
        """, (location_id,))

        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def dismiss(self, archetype_id: str) -> bool:
        """Dismiss a detected archetype."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            UPDATE system_archetype SET status = 'dismissed'
            WHERE id = %s AND status = 'active'
        """, (archetype_id,))
        changed = cur.rowcount > 0
        conn.commit()
        cur.close()
        return changed

    def resolve(self, archetype_id: str) -> bool:
        """Mark an archetype as resolved."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            UPDATE system_archetype
            SET status = 'resolved', resolved_at = NOW()
            WHERE id = %s AND status = 'active'
        """, (archetype_id,))
        changed = cur.rowcount > 0
        conn.commit()
        cur.close()
        return changed

    # --- Detection methods ---

    def _detect_fixes_that_fail(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'fixes that fail': intervention → short-term gain → long-term decline."""
        # Look for practice events followed by declining outcomes
        cur.execute("""
            SELECT
                pe.practice_type,
                pe.practice_date,
                he.yield_kg
            FROM practice_event pe
            LEFT JOIN harvest_event he ON he.location_id = pe.location_id
                AND he.harvest_date > pe.practice_date
                AND he.harvest_date < pe.practice_date + INTERVAL '1 year'
            WHERE pe.location_id = %s
            ORDER BY pe.practice_date DESC
            LIMIT 10
        """, (location_id,))
        rows = [dict(r) for r in cur.fetchall()]

        if len(rows) < 3:
            return None

        # Check for repeating same practice with declining yields
        practice_types = [r["practice_type"] for r in rows if r["practice_type"]]
        if not practice_types:
            return None

        most_common = max(set(practice_types), key=practice_types.count)
        same_practice = [r for r in rows if r["practice_type"] == most_common]

        if len(same_practice) < 2:
            return None

        yields = [r["yield_kg"] for r in same_practice if r["yield_kg"] is not None]
        if len(yields) < 2:
            return None

        # Check if yields are declining despite repeated intervention
        if yields[0] < yields[-1] * 0.9:  # 10% decline
            confidence = min(0.5 + (len(same_practice) - 2) * 0.1, 0.9)
            return {
                "archetype_name": "Fixes That Fail",
                "confidence": round(confidence, 3),
                "evidence": {
                    "practice": most_common,
                    "repeat_count": len(same_practice),
                    "yield_trend": "declining",
                    "yields": yields,
                },
                "active_variables": [most_common, "yield_kg"],
                "suggested_intervention": f"Consider alternative approaches to {most_common} — repeated application shows declining effectiveness.",
            }

        return None

    def _detect_shifting_the_burden(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'shifting the burden': symptom treatment replacing fundamental solution."""
        # Check for increasing fertilizer/chemical use without improving soil health
        cur.execute("""
            SELECT
                expense_category,
                SUM(amount_usd) as total,
                EXTRACT(MONTH FROM expense_date) as month
            FROM expense_event
            WHERE location_id = %s
            AND expense_date > NOW() - INTERVAL '2 years'
            AND expense_category IN ('fertilizer', 'pesticide', 'inputs')
            GROUP BY expense_category, EXTRACT(MONTH FROM expense_date)
            ORDER BY month
        """, (location_id,))
        input_costs = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT mv.value, mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s AND md.metric_key = 'soil_carbon_delta'
            AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC LIMIT 5
        """, (location_id,))
        soil_trend = [dict(r)["value"] for r in cur.fetchall()]

        if input_costs and soil_trend:
            total_input = sum(r["total"] for r in input_costs)
            avg_soil = sum(soil_trend) / len(soil_trend) if soil_trend else 0

            # Rising inputs + declining soil = shifting the burden
            if total_input > 1000 and avg_soil < 0:
                return {
                    "archetype_name": "Shifting the Burden",
                    "confidence": 0.6,
                    "evidence": {
                        "total_input_cost": total_input,
                        "avg_soil_carbon_delta": avg_soil,
                        "pattern": "increasing_inputs_declining_soil",
                    },
                    "active_variables": ["fertilizer", "soil_carbon"],
                    "suggested_intervention": "Invest in soil-building practices to reduce dependence on external inputs.",
                }

        return None

    def _detect_erosion_of_goals(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'erosion of goals': declining standards over time."""
        cur.execute("""
            SELECT
                rating,
                composite_score,
                assessed_at
            FROM crisp_risk_assessment
            WHERE location_id = %s
            ORDER BY assessed_at DESC
            LIMIT 10
        """, (location_id,))
        ratings = [dict(r) for r in cur.fetchall()]

        if len(ratings) < 3:
            return None

        # Check if CRISP ratings are declining (worse risk over time)
        scores = [r["composite_score"] for r in ratings if r["composite_score"]]
        if len(scores) < 3:
            return None

        # In CRISP, lower score = worse (more risk)
        if scores[0] < scores[-1] * 0.95:  # 5% decline
            return {
                "archetype_name": "Erosion of Goals",
                "confidence": 0.5,
                "evidence": {
                    "score_trend": "declining",
                    "latest_score": scores[0],
                    "earliest_score": scores[-1],
                    "assessment_count": len(ratings),
                },
                "active_variables": ["crisp_composite_score"],
                "suggested_intervention": "Re-examine and potentially raise performance goals — declining scores may indicate acceptance of lower standards.",
            }

        return None

    def _detect_escalation(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'escalation': competing dynamics worsening over time."""
        cur.execute("""
            SELECT
                md.metric_key,
                mv.value,
                mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC
            LIMIT 30
        """, (location_id,))
        metrics = [dict(r) for r in cur.fetchall()]

        # Look for opposing metrics both increasing (escalation)
        if len(metrics) < 10:
            return None

        # Group by metric key
        by_key = {}
        for m in metrics:
            key = m["metric_key"]
            if key not in by_key:
                by_key[key] = []
            by_key[key].append(float(m["value"]))

        # Check for cost increase + quality decrease (or similar)
        cost_keys = [k for k in by_key if "cost" in k.lower()]
        quality_keys = [k for k in by_key if any(q in k.lower() for q in ["quality", "yield", "revenue"])]

        if cost_keys and quality_keys:
            cost_trend = by_key[cost_keys[0]]
            quality_trend = by_key[quality_keys[0]]

            if len(cost_trend) >= 2 and len(quality_trend) >= 2:
                if cost_trend[0] > cost_trend[-1] and quality_trend[0] < quality_trend[-1]:
                    return {
                        "archetype_name": "Escalation",
                        "confidence": 0.45,
                        "evidence": {
                            "cost_increasing": True,
                            "quality_decreasing": True,
                            "cost_metric": cost_keys[0],
                            "quality_metric": quality_keys[0],
                        },
                        "active_variables": cost_keys + quality_keys,
                        "suggested_intervention": "Break the escalation cycle by addressing root causes rather than symptoms.",
                    }

        return None

    def _detect_success_to_successful(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'success to the successful': resource concentration."""
        cur.execute("""
            SELECT
                crop_type,
                SUM(revenue_usd) as total_revenue
            FROM revenue_event
            WHERE location_id = %s
            GROUP BY crop_type
            ORDER BY total_revenue DESC
        """, (location_id,))
        crops = [dict(r) for r in cur.fetchall()]

        if len(crops) < 3:
            return None

        total = sum(c["total_revenue"] for c in crops)
        if total <= 0:
            return None

        top_crop_share = crops[0]["total_revenue"] / total

        if top_crop_share > 0.7:  # One crop dominates
            return {
                "archetype_name": "Success to the Successful",
                "confidence": 0.5 + (top_crop_share - 0.7),
                "evidence": {
                    "dominant_crop": crops[0]["crop_type"],
                    "market_share": round(top_crop_share, 3),
                    "crop_count": len(crops),
                },
                "active_variables": [c["crop_type"] for c in crops],
                "suggested_intervention": f"Diversify beyond {crops[0]['crop_type']} — over-concentration creates systemic fragility.",
            }

        return None

    def _detect_tragedy_of_commons(
        self, cur, location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Detect 'tragedy of the commons': shared resource depletion."""
        # Check for declining water levels or shared resource metrics
        cur.execute("""
            SELECT
                mv.value,
                mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_definition_id
            WHERE mv.location_id = %s
            AND md.metric_key IN ('water_access', 'biodiversity_delta', 'soil_carbon_delta')
            AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC
            LIMIT 10
        """, (location_id,))
        resources = [dict(r) for r in cur.fetchall()]

        if len(resources) < 3:
            return None

        values = [float(r["value"]) for r in resources]
        if values[0] < values[-1] * 0.85:  # 15% decline in shared resource
            return {
                "archetype_name": "Tragedy of the Commons",
                "confidence": 0.55,
                "evidence": {
                    "resource_trend": "declining",
                    "latest_value": values[0],
                    "earliest_value": values[-1],
                    "decline_pct": round((values[-1] - values[0]) / values[-1] * 100, 1),
                },
                "active_variables": ["shared_resource"],
                "suggested_intervention": "Establish governance mechanisms to manage shared resource use sustainably.",
            }

        return None
