"""Situation Assessment — unified orientation for OODA loop.

Reads CRISP scores, metric values, anomaly counts, and analytics
outputs to produce a single SituationAssessment with a situation_grade
(critical/warning/stable/flourishing) per location.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


# Grade thresholds based on health score (0-100, higher = better).
GRADE_THRESHOLDS = {
    "flourishing": (80, 101),
    "stable": (60, 80),
    "warning": (30, 60),
    "critical": (0, 30),
}

# Grade from CRISP rating (lower risk = better grade)
CRISP_RATING_TO_GRADE = {
    "AAA": "flourishing",
    "AA": "flourishing",
    "A": "stable",
    "B": "warning",
    "C": "critical",
    "D": "critical",
}

DIMENSION_KEYS = [
    "carbon_yield",
    "climate",
    "policy",
    "financial",
    "implementation",
]


class SituationAssessor:
    """Synthesizes multi-source data into a unified situation assessment."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def assess(
        self,
        location_id: str,
        assessment_type: str = "full",
        assessed_by: str = "system",
    ) -> Dict[str, Any]:
        """Run a full situation assessment for a location.

        Args:
            location_id: UUID of the location to assess.
            assessment_type: 'full', 'quick', 'deep', or 'reassessment'.
            assessed_by: Who or what triggered the assessment.

        Returns:
            Dict with assessment_id, situation_grade, composite_score, etc.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        now = datetime.now(timezone.utc)
        period_start = now.isoformat()
        period_end = now.isoformat()

        # Gather signals from multiple sources
        signals = []
        signals.extend(self._gather_crisp_signals(cur, location_id))
        signals.extend(self._gather_metric_signals(cur, location_id))
        signals.extend(self._gather_anomaly_signals(cur, location_id))
        signals.extend(self._gather_recent_alerts(cur, location_id))

        # Compute dimension summaries
        dimensions = self._compute_dimensions(cur, location_id, signals)

        # Compute composite score (0-100, higher = better situation)
        composite_score = self._compute_composite_score(dimensions, signals)

        # Assign grade
        situation_grade = self._assign_grade(composite_score)

        # Compute confidence
        confidence_level = self._compute_confidence(dimensions, signals)

        # Evidence maturity from signals
        evidence_maturity = self._compute_evidence_maturity(signals)

        # CRISP data
        crisp_data = self._get_latest_crisp(cur, location_id)

        # Anomaly counts
        anomaly_counts = self._count_anomalies(cur, location_id)

        # Metric trend summary
        metric_trends = self._compute_metric_trends(cur, location_id)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            situation_grade, dimensions, signals, anomaly_counts
        )

        # Persist assessment
        assessment_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO situation_assessment (
                id, location_id, assessment_type, situation_grade,
                composite_score, confidence_level, evidence_maturity,
                crisp_rating, crisp_composite_score,
                anomaly_count, critical_anomaly_count,
                metric_trend_summary, dimension_summaries, recommendations,
                period_start, period_end, assessed_at, assessed_by,
                status, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                'draft', '{}'
            )
        """, (
            assessment_id, location_id, assessment_type, situation_grade,
            composite_score, confidence_level, evidence_maturity,
            crisp_data.get("rating"), crisp_data.get("composite_score"),
            anomaly_counts.get("total", 0), anomaly_counts.get("critical", 0),
            psycopg2.extras.Json(metric_trends),
            psycopg2.extras.Json({d["key"]: d for d in dimensions}),
            psycopg2.extras.Json(recommendations),
            period_start, period_end, now, assessed_by,
        ))

        # Persist signals
        for signal in signals:
            cur.execute("""
                INSERT INTO assessment_signal (
                    id, assessment_id, signal_type, signal_key,
                    signal_value, signal_text, signal_direction,
                    weight, source_table, source_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), assessment_id, signal["type"],
                signal["key"], signal.get("value"), signal.get("text"),
                signal.get("direction", "neutral"), signal.get("weight", 1.0),
                signal.get("source_table"), signal.get("source_id"),
            ))

        # Persist dimensions
        for dim in dimensions:
            cur.execute("""
                INSERT INTO assessment_dimension (
                    id, assessment_id, dimension_key, dimension_name,
                    risk_score, trend, trend_delta, signal_count,
                    confidence_level, evidence_summary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), assessment_id, dim["key"],
                dim["name"], dim["risk_score"], dim.get("trend", "stable"),
                dim.get("trend_delta"), dim.get("signal_count", 0),
                dim.get("confidence_level", "low"),
                dim.get("evidence_summary"),
            ))

        conn.commit()
        cur.close()

        return {
            "assessment_id": assessment_id,
            "location_id": location_id,
            "situation_grade": situation_grade,
            "composite_score": composite_score,
            "confidence_level": confidence_level,
            "evidence_maturity": evidence_maturity,
            "crisp_rating": crisp_data.get("rating"),
            "anomaly_count": anomaly_counts.get("total", 0),
            "critical_anomaly_count": anomaly_counts.get("critical", 0),
            "dimension_count": len(dimensions),
            "signal_count": len(signals),
            "recommendation_count": len(recommendations),
        }

    def get_latest(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent assessment for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM situation_assessment
            WHERE location_id = %s AND status != 'superseded'
            ORDER BY assessed_at DESC LIMIT 1
        """, (location_id,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(row)

    def _gather_crisp_signals(
        self, cur, location_id: str
    ) -> List[Dict[str, Any]]:
        """Gather signals from latest CRISP assessment."""
        cur.execute("""
            SELECT * FROM crisp_risk_assessment
            WHERE location_id = %s AND status = 'draft'
            ORDER BY score_computed_at DESC NULLS LAST LIMIT 1
        """, (location_id,))
        row = cur.fetchone()
        if row is None:
            return []

        row = dict(row)
        signals = []

        # CRISP is risk (higher is worse); OODA signals are health (higher is better).
        composite_health = 100.0 - float(row.get("composite_score") or 50)
        signals.append({
            "type": "crisp_dimension",
            "key": "crisp_composite",
            "value": composite_health,
            "text": f"CRISP rating: {row.get('rating', 'N/A')}",
            "direction": "positive" if composite_health > 60
                        else "negative" if composite_health < 40
                        else "neutral",
            "weight": 2.0,
            "source_table": "crisp_risk_assessment",
            "source_id": str(row.get("id")),
        })

        # Per-dimension signals
        for dim_key in DIMENSION_KEYS:
            score_col = f"{dim_key}_score"
            if score_col in row and row[score_col] is not None:
                score = 100.0 - float(row[score_col])
                signals.append({
                    "type": "crisp_dimension",
                    "key": f"crisp_{dim_key}",
                    "value": score,
                    "text": f"CRISP {dim_key} health: {score:.1f}",
                    "direction": "positive" if score > 60
                                else "negative" if score < 40
                                else "neutral",
                    "weight": 1.5,
                    "source_table": "crisp_risk_assessment",
                    "source_id": str(row.get("id")),
                })

        return signals

    def _gather_metric_signals(
        self, cur, location_id: str
    ) -> List[Dict[str, Any]]:
        """Gather signals from recent metric computations."""
        cur.execute("""
            SELECT mv.*, md.metric_key, md.display_name
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s
            AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC
            LIMIT 20
        """, (location_id,))
        rows = cur.fetchall()
        signals = []

        for row in rows:
            row = dict(row)
            value = float(row.get("value", 0))
            signals.append({
                "type": "metric_trend",
                "key": row.get("metric_key", "unknown"),
                "value": value,
                "text": f"{row.get('display_name', row.get('metric_key'))}: {value:.2f}",
                "direction": "positive" if value > 0
                            else "negative" if value < 0
                            else "neutral",
                "weight": 1.0,
                "source_table": "metric_value",
                "source_id": str(row.get("id")),
            })

        return signals

    def _gather_anomaly_signals(
        self, cur, location_id: str
    ) -> List[Dict[str, Any]]:
        """Gather signals from recent anomalies."""
        cur.execute("""
            SELECT sa.*
            FROM sensor_alert sa
            JOIN sensor_device sd ON sd.id = sa.sensor_device_id
            WHERE sd.location_id = %s
            AND sa.created_at > NOW() - INTERVAL '7 days'
            ORDER BY sa.created_at DESC
            LIMIT 20
        """, (location_id,))
        rows = cur.fetchall()
        signals = []

        for row in rows:
            row = dict(row)
            severity = row.get("severity", "info")
            signals.append({
                "type": "anomaly_cluster",
                "key": f"anomaly_{severity}",
                "value": 1.0,
                "text": f"Anomaly ({severity}): {row.get('alert_type', 'unknown')}",
                "direction": "negative" if severity in ("critical", "warning")
                            else "neutral",
                "weight": 2.0 if severity == "critical" else 1.0,
                "source_table": "sensor_alert",
                "source_id": str(row.get("id")),
            })

        return signals

    def _gather_recent_alerts(
        self, cur, location_id: str
    ) -> List[Dict[str, Any]]:
        """Gather signals from stream alerts."""
        cur.execute("""
            SELECT sa.*
            FROM stream_alert sa
            JOIN sensor_device sd ON sd.id = sa.sensor_device_id
            WHERE sd.location_id = %s
            AND sa.created_at > NOW() - INTERVAL '7 days'
            AND sa.acknowledged = FALSE
            ORDER BY sa.created_at DESC
            LIMIT 10
        """, (location_id,))
        rows = cur.fetchall()
        signals = []

        for row in rows:
            row = dict(row)
            signals.append({
                "type": "external_event",
                "key": f"stream_alert_{row.get('alert_type', 'unknown')}",
                "value": 1.0,
                "text": f"Unacknowledged stream alert: {row.get('metric', 'unknown')}",
                "direction": "negative",
                "weight": 1.5,
                "source_table": "stream_alert",
                "source_id": str(row.get("id")),
            })

        return signals

    def _compute_dimensions(
        self,
        cur,
        location_id: str,
        signals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compute dimension summaries from signals."""
        # Group signals by dimension
        dim_signals: Dict[str, List[Dict]] = {k: [] for k in DIMENSION_KEYS}
        other_signals = []

        for sig in signals:
            key = sig["key"]
            matched = False
            for dim_key in DIMENSION_KEYS:
                if dim_key in key:
                    dim_signals[dim_key].append(sig)
                    matched = True
                    break
            if not matched:
                other_signals.append(sig)

        dimensions = []
        for dim_key in DIMENSION_KEYS:
            sigs = dim_signals[dim_key]
            if not sigs:
                # No signals for this dimension — use neutral score
                dimensions.append({
                    "key": dim_key,
                    "name": dim_key.replace("_", " ").title(),
                    "risk_score": 50.0,
                    "trend": "stable",
                    "trend_delta": 0.0,
                    "signal_count": 0,
                    "confidence_level": "insufficient_evidence",
                    "evidence_summary": "No data available",
                })
                continue

            # Average the signal values (weighted)
            total_weight = sum(s.get("weight", 1.0) for s in sigs)
            weighted_sum = sum(
                s.get("value", 50.0) * s.get("weight", 1.0) for s in sigs
            )
            avg_score = weighted_sum / total_weight if total_weight > 0 else 50.0

            # Determine trend from signal directions
            directions = [s.get("direction", "neutral") for s in sigs]
            pos_count = directions.count("positive")
            neg_count = directions.count("negative")
            if neg_count > pos_count:
                trend = "declining"
            elif pos_count > neg_count:
                trend = "improving"
            else:
                trend = "stable"

            dimensions.append({
                "key": dim_key,
                "name": dim_key.replace("_", " ").title(),
                "risk_score": avg_score,
                "trend": trend,
                "trend_delta": 0.0,
                "signal_count": len(sigs),
                "confidence_level": "moderate" if len(sigs) >= 3 else "low",
                "evidence_summary": f"{len(sigs)} signals analyzed",
            })

        return dimensions

    def _compute_composite_score(
        self,
        dimensions: List[Dict[str, Any]],
        signals: List[Dict[str, Any]],
    ) -> float:
        """Compute composite situation score (0-100, higher = better)."""
        if not dimensions:
            return 50.0

        # Weight dimensions equally for now
        total = sum(d["risk_score"] for d in dimensions)
        return total / len(dimensions)

    def _assign_grade(self, composite_score: float) -> str:
        """Assign situation grade from composite score."""
        for grade, (low, high) in GRADE_THRESHOLDS.items():
            if low <= composite_score < high:
                return grade
        return "critical"

    def _compute_confidence(
        self,
        dimensions: List[Dict[str, Any]],
        signals: List[Dict[str, Any]],
    ) -> str:
        """Compute overall confidence level."""
        if not signals:
            return "insufficient_evidence"
        if len(signals) >= 10 and any(
            d["confidence_level"] == "moderate" for d in dimensions
        ):
            return "high"
        if len(signals) >= 5:
            return "moderate"
        return "low"

    def _compute_evidence_maturity(
        self, signals: List[Dict[str, Any]]
    ) -> int:
        """Estimate evidence maturity level (1-6)."""
        if not signals:
            return 1
        if len(signals) >= 15:
            return 4
        if len(signals) >= 10:
            return 3
        if len(signals) >= 5:
            return 2
        return 1

    def _get_latest_crisp(
        self, cur, location_id: str
    ) -> Dict[str, Any]:
        """Get latest CRISP assessment data."""
        cur.execute("""
            SELECT rating, composite_score
            FROM crisp_risk_assessment
            WHERE location_id = %s AND status = 'draft'
            ORDER BY score_computed_at DESC NULLS LAST LIMIT 1
        """, (location_id,))
        row = cur.fetchone()
        if row is None:
            return {"rating": None, "composite_score": None}
        return dict(row)

    def _count_anomalies(
        self, cur, location_id: str
    ) -> Dict[str, int]:
        """Count recent anomalies by severity."""
        cur.execute("""
            SELECT
                sa.severity,
                COUNT(*) as cnt
            FROM sensor_alert sa
            JOIN sensor_device sd ON sd.id = sa.sensor_device_id
            WHERE sd.location_id = %s
            AND sa.created_at > NOW() - INTERVAL '7 days'
            GROUP BY sa.severity
        """, (location_id,))
        rows = cur.fetchall()
        result = {"total": 0, "critical": 0, "warning": 0, "info": 0}
        for row in rows:
            row = dict(row)
            severity = row["severity"]
            count = row["cnt"]
            result[severity] = count
            result["total"] += count
        return result

    def _compute_metric_trends(
        self, cur, location_id: str
    ) -> Dict[str, Any]:
        """Compute recent metric trends."""
        cur.execute("""
            SELECT
                md.metric_key,
                mv.value,
                mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s
            AND mv.verified = TRUE
            ORDER BY mv.computed_at DESC
            LIMIT 30
        """, (location_id,))
        rows = cur.fetchall()

        trends = {}
        for row in rows:
            row = dict(row)
            key = row["metric_key"]
            if key not in trends:
                trends[key] = {"values": [], "latest": None}
            trends[key]["values"].append(float(row["value"]))
            if trends[key]["latest"] is None:
                trends[key]["latest"] = float(row["value"])

        # Compute simple trend direction
        for key, data in trends.items():
            vals = data["values"]
            if len(vals) >= 2:
                recent = vals[0]
                older = vals[-1]
                data["direction"] = (
                    "improving" if recent > older
                    else "declining" if recent < older
                    else "stable"
                )
                data["delta"] = recent - older
            else:
                data["direction"] = "stable"
                data["delta"] = 0.0
            del data["values"]  # Don't expose raw values in summary

        return trends

    def _generate_recommendations(
        self,
        situation_grade: str,
        dimensions: List[Dict[str, Any]],
        signals: List[Dict[str, Any]],
        anomaly_counts: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on assessment."""
        recommendations = []

        # Critical grade: immediate action needed
        if situation_grade == "critical":
            recommendations.append({
                "priority": "high",
                "type": "intervention",
                "description": "Situation is critical — review all dimensions and prioritize interventions",
                "dimension": None,
            })

        # Per-dimension recommendations
        for dim in dimensions:
            score = dim["risk_score"]
            if score < 30:
                recommendations.append({
                    "priority": "high",
                    "type": "dimension_action",
                    "description": f"{dim['name']} is severely degraded (score: {score:.1f})",
                    "dimension": dim["key"],
                })
            elif score < 50:
                recommendations.append({
                    "priority": "medium",
                    "type": "dimension_monitor",
                    "description": f"{dim['name']} needs attention (score: {score:.1f})",
                    "dimension": dim["key"],
                })

        # Anomaly-based recommendations
        if anomaly_counts.get("critical", 0) > 0:
            recommendations.append({
                "priority": "high",
                "type": "anomaly_response",
                "description": f"{anomaly_counts['critical']} critical anomalies in last 7 days",
                "dimension": None,
            })

        if anomaly_counts.get("total", 0) > 5:
            recommendations.append({
                "priority": "medium",
                "type": "anomaly_investigation",
                "description": f"{anomaly_counts['total']} total anomalies — investigate patterns",
                "dimension": None,
            })

        return recommendations
