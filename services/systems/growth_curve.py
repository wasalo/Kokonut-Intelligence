"""Growth Curve Analyzer — detects exponential growth, S-curves, and tipping points.

Analyzes metric time-series to identify growth patterns (exponential,
linear, logarithmic, S-curve, declining, oscillating) and detect
tipping points, saturation, and trajectory projections.
"""

from __future__ import annotations

import uuid
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class GrowthCurveAnalyzer:
    """Analyzes growth curves and detects tipping points in metric time-series."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def analyze_metric(
        self,
        location_id: Optional[str],
        metric_name: str,
        data_points: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Analyze a metric time-series for growth curve type and parameters.

        If data_points is None, loads from improvement_rate table.
        Returns curve type, parameters, and confidence.
        """
        if data_points is None:
            data_points = self._load_metric_data(cur=None, location_id=location_id, metric_name=metric_name)

        if len(data_points) < 4:
            return {
                "metric_name": metric_name,
                "curve_type": "insufficient_data",
                "data_points_used": len(data_points),
                "confidence": 0.0,
            }

        values = [d["value"] for d in data_points if d.get("value") is not None]

        if len(values) < 4:
            return {
                "metric_name": metric_name,
                "curve_type": "insufficient_data",
                "data_points_used": len(values),
                "confidence": 0.0,
            }

        # Detect curve type
        curve_type, fit_quality, params = self._fit_curve(values)

        # Compute velocity and acceleration
        velocity = self._compute_velocity(values)
        acceleration = self._compute_acceleration(values)

        # Detect tipping points
        tipping_risk, tipping_metric = self._detect_tipping_point(values, curve_type)

        # For S-curves, compute position
        position_pct = None
        inflection_point = None
        if curve_type == "s_curve":
            position_pct = self._compute_s_curve_position(values)
            inflection_point = self._estimate_inflection(values)

        result = {
            "metric_name": metric_name,
            "curve_type": curve_type,
            "data_points_used": len(values),
            "fit_quality": round(fit_quality, 3),
            "current_velocity": velocity,
            "acceleration": acceleration,
            "tipping_point_risk": tipping_risk,
            "tipping_point_metric": tipping_metric,
            "current_position_pct": position_pct,
            "inflection_point": inflection_point,
        }

        # Persist analysis
        self._persist_analysis(location_id, result)

        return result

    def detect_tipping_points(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect metrics approaching tipping points across all domains."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["gca.tipping_point_risk > 0.5"]
        params: list = []

        if location_id:
            conditions.append("gca.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT DISTINCT ON (gca.metric_name)
                gca.metric_name, gca.curve_type,
                gca.tipping_point_risk, gca.tipping_point_metric,
                gca.days_to_tipping_point, gca.analyzed_at
            FROM growth_curve_analysis gca
            WHERE {where_clause}
            ORDER BY gca.metric_name, gca.analyzed_at DESC
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def detect_exponential_growth(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect metrics showing exponential growth patterns."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["gca.curve_type = 'exponential'"]
        params: list = []

        if location_id:
            conditions.append("gca.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT DISTINCT ON (gca.metric_name)
                gca.metric_name, gca.growth_rate, gca.current_velocity,
                gca.acceleration, gca.fit_quality, gca.analyzed_at
            FROM growth_curve_analysis gca
            WHERE {where_clause}
            ORDER BY gca.metric_name, gca.analyzed_at DESC
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def detect_saturation(
        self, location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect metrics that have reached plateau/saturation."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["gca.curve_type IN ('logarithmic', 's_curve')"]
        params: list = []

        if location_id:
            conditions.append("gca.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT DISTINCT ON (gca.metric_name)
                gca.metric_name, gca.curve_type,
                gca.current_position_pct, gca.carrying_capacity,
                gca.current_velocity, gca.analyzed_at
            FROM growth_curve_analysis gca
            WHERE {where_clause}
            ORDER BY gca.metric_name, gca.analyzed_at DESC
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def get_curve_report(
        self, location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive growth curve report for all metrics."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["1=1"]
        params: list = []

        if location_id:
            conditions.append("gca.location_id = %s")
            params.append(location_id)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT DISTINCT ON (gca.metric_name)
                gca.metric_name, gca.curve_type, gca.fit_quality,
                gca.current_velocity, gca.acceleration,
                gca.tipping_point_risk, gca.current_position_pct,
                gca.analyzed_at
            FROM growth_curve_analysis gca
            WHERE {where_clause}
            ORDER BY gca.metric_name, gca.analyzed_at DESC
        """, params)

        metrics = [dict(r) for r in cur.fetchall()]
        cur.close()

        exponential = sum(1 for m in metrics if m.get("curve_type") == "exponential")
        s_curve = sum(1 for m in metrics if m.get("curve_type") == "s_curve")
        logarithmic = sum(1 for m in metrics if m.get("curve_type") == "logarithmic")
        declining = sum(1 for m in metrics if m.get("curve_type") == "declining")
        linear = sum(1 for m in metrics if m.get("curve_type") == "linear")
        tipping = sum(1 for m in metrics if (m.get("tipping_point_risk") or 0) > 0.5)

        return {
            "total_metrics": len(metrics),
            "exponential": exponential,
            "s_curve": s_curve,
            "logarithmic": logarithmic,
            "declining": declining,
            "linear": linear,
            "tipping_points_detected": tipping,
            "metrics": metrics,
        }

    def predict_trajectory(
        self,
        location_id: Optional[str],
        metric_name: str,
        periods_ahead: int = 5,
    ) -> Dict[str, Any]:
        """Project metric trajectory based on detected curve type."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get latest analysis
        cur.execute("""
            SELECT * FROM growth_curve_analysis
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
            ORDER BY analyzed_at DESC
            LIMIT 1
        """, (location_id, location_id, metric_name))

        row = cur.fetchone()
        cur.close()

        if not row:
            return {
                "metric_name": metric_name,
                "projections": [],
                "curve_type": "unknown",
            }

        analysis = dict(row)
        curve_type = analysis.get("curve_type", "linear")
        velocity = float(analysis.get("current_velocity") or 0)
        acceleration = float(analysis.get("acceleration") or 0)

        projections = []
        for i in range(1, periods_ahead + 1):
            if curve_type == "exponential":
                # Exponential: value grows by velocity * acceleration^period
                projected_velocity = velocity * (1 + acceleration) ** i
                projected_change = velocity * (1 + acceleration) ** i
            elif curve_type == "linear":
                projected_change = velocity * i
            elif curve_type == "logarithmic":
                # Logarithmic: growth slows over time
                projected_change = velocity * (1 / (1 + i * 0.2))
            elif curve_type == "s_curve":
                # S-curve: growth accelerates then decelerates
                position = float(analysis.get("current_position_pct") or 50) / 100
                phase_factor = 1.0 - abs(position - 0.5) * 2  # Peaks at inflection
                projected_change = velocity * phase_factor * i
            elif curve_type == "declining":
                projected_change = -velocity * i
            else:
                projected_change = velocity * i

            projections.append({
                "period": i,
                "projected_change": round(projected_change, 4),
            })

        return {
            "metric_name": metric_name,
            "curve_type": curve_type,
            "current_velocity": velocity,
            "acceleration": acceleration,
            "projections": projections,
        }

    # --- Private helpers ---

    def _load_metric_data(
        self, cur, location_id: Optional[str], metric_name: str
    ) -> List[Dict]:
        """Load metric time-series from improvement_rate table."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT current_value as value, created_at as date
            FROM improvement_rate
            WHERE (%s IS NULL OR location_id = %s)
              AND metric_name = %s
              AND current_value IS NOT NULL
            ORDER BY created_at ASC
        """, (location_id, location_id, metric_name))

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def _fit_curve(self, values: List[float]) -> tuple:
        """Fit curve types and return best fit with quality score."""
        n = len(values)

        # Compute simple metrics for classification
        first_half = values[: n // 2]
        second_half = values[n // 2:]

        first_mean = statistics.mean(first_half) if first_half else 0
        second_mean = statistics.mean(second_half) if second_half else 0

        # Rate of change
        if first_mean != 0:
            growth_ratio = second_mean / first_mean
        else:
            growth_ratio = 1.0

        # Variance of differences
        diffs = [values[i + 1] - values[i] for i in range(n - 1)]
        if len(diffs) > 1:
            diff_variance = statistics.stdev(diffs) if len(diffs) > 1 else 0
            diff_mean = abs(statistics.mean(diffs)) if diffs else 1
        else:
            diff_variance = 0
            diff_mean = 1

        # Coefficient of variation of differences
        cv_diff = (diff_variance / diff_mean) if diff_mean > 0 else 0

        # Overall trend
        total_change = values[-1] - values[0]
        avg_change = total_change / (n - 1) if n > 1 else 0

        # Detect oscillation
        sign_changes = sum(
            1 for i in range(len(diffs) - 1)
            if diffs[i] * diffs[i + 1] < 0
        )
        oscillation_ratio = sign_changes / max(len(diffs) - 1, 1)

        # Classification
        if oscillation_ratio > 0.6:
            return ("oscillating", 0.7, {"oscillation_ratio": oscillation_ratio})

        if total_change < 0 and abs(total_change) > abs(values[0]) * 0.2:
            fit_quality = min(0.9, abs(total_change) / abs(values[0]))
            return ("declining", fit_quality, {"decline_rate": avg_change})

        if growth_ratio > 1.3 and cv_diff > 0.5:
            # Accelerating growth = exponential
            fit_quality = min(0.9, growth_ratio / 2)
            return ("exponential", fit_quality, {"growth_ratio": growth_ratio})

        if growth_ratio > 1.0 and growth_ratio < 1.3:
            # Steady growth
            if cv_diff < 0.3:
                fit_quality = 0.8
                return ("linear", fit_quality, {"slope": avg_change})

        if growth_ratio < 1.0 and growth_ratio > 0.7:
            # Decelerating growth = logarithmic or S-curve
            if growth_ratio > 0.85:
                # Near plateau
                fit_quality = 0.75
                return ("logarithmic", fit_quality, {"growth_ratio": growth_ratio})
            else:
                # S-curve approaching plateau
                fit_quality = 0.7
                return ("s_curve", fit_quality, {"growth_ratio": growth_ratio})

        # Default to linear
        return ("linear", 0.5, {"slope": avg_change})

    def _compute_velocity(self, values: List[float]) -> float:
        """Compute current velocity (rate of change)."""
        if len(values) < 2:
            return 0.0
        # Use last 3 points for recent velocity
        recent = values[-3:] if len(values) >= 3 else values
        if len(recent) < 2:
            return 0.0
        return round((recent[-1] - recent[0]) / len(recent), 4)

    def _compute_acceleration(self, values: List[float]) -> float:
        """Compute acceleration (second derivative)."""
        if len(values) < 3:
            return 0.0
        # Compare velocity of recent half vs older half
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        v1 = self._compute_velocity(first_half) if len(first_half) >= 2 else 0
        v2 = self._compute_velocity(second_half) if len(second_half) >= 2 else 0

        return round(v2 - v1, 4)

    def _detect_tipping_point(
        self, values: List[float], curve_type: str
    ) -> tuple:
        """Detect if the metric is near a tipping point."""
        if len(values) < 3:
            return (0.0, None)

        # Check for rapid acceleration (potential tipping point)
        recent = values[-3:]
        diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]

        if len(diffs) >= 2:
            acceleration = diffs[-1] - diffs[0]
            avg_value = abs(statistics.mean(values[-3:])) or 1.0

            # Normalized acceleration
            norm_accel = abs(acceleration) / avg_value

            if norm_accel > 2.0:
                return (min(0.95, norm_accel / 5), "rapid_acceleration")
            if norm_accel > 1.0:
                return (min(0.7, norm_accel / 5), "moderate_acceleration")

        # For S-curves, tipping point is inflection
        if curve_type == "s_curve":
            return (0.6, "s_curve_inflection")

        return (0.0, None)

    def _compute_s_curve_position(self, values: List[float]) -> float:
        """Compute where we are on the S-curve (0-100%)."""
        if len(values) < 2:
            return 50.0

        min_val = min(values)
        max_val = max(values)
        current = values[-1]

        if max_val == min_val:
            return 50.0

        position = ((current - min_val) / (max_val - min_val)) * 100
        return round(min(100, max(0, position)), 2)

    def _estimate_inflection(self, values: List[float]) -> Optional[float]:
        """Estimate the inflection point value."""
        if len(values) < 4:
            return None

        # Simple: inflection is where acceleration changes sign
        diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        accelerations = [diffs[i + 1] - diffs[i] for i in range(len(diffs) - 1)]

        for i, acc in enumerate(accelerations):
            if i > 0 and accelerations[i - 1] > 0 and acc <= 0:
                return round(values[i + 1], 4)

        return None

    def _persist_analysis(
        self, location_id: Optional[str], result: Dict[str, Any]
    ) -> None:
        """Persist growth curve analysis to database."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        analysis_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO growth_curve_analysis (
                id, location_id, metric_name, curve_type,
                current_velocity, acceleration,
                tipping_point_risk, tipping_point_metric,
                current_position_pct, inflection_point,
                data_points_used, fit_quality,
                analyzed_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}')
        """, (
            analysis_id, location_id, result["metric_name"],
            result["curve_type"],
            result.get("current_velocity"),
            result.get("acceleration"),
            result.get("tipping_point_risk"),
            result.get("tipping_point_metric"),
            result.get("current_position_pct"),
            result.get("inflection_point"),
            result.get("data_points_used"),
            result.get("fit_quality"),
            now,
        ))

        conn.commit()
        cur.close()
