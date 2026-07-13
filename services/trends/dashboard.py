"""Trend Dashboard — precomputed trend metrics for dashboards and reporting.

Computes and caches trend summary metrics for efficient dashboard rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from .estimator import TrendEstimator
from .significance import TrendSignificance
from .smoothing import TimeSeriesSmoothing
from .change_points import ChangePointDetector


class TrendDashboard:
    """Computes precomputed trend metrics for dashboards."""

    def __init__(self, conn=None):
        self._conn = conn
        self._estimator = TrendEstimator(conn)
        self._significance = TrendSignificance()
        self._smoothing = TimeSeriesSmoothing(conn)
        self._change_points = ChangePointDetector(conn)

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def compute_trend_metrics(
        self,
        metric_key: str,
        location_id: str,
        lookback_days: int = 365,
    ) -> Dict[str, Any]:
        """Compute full trend metrics for a single metric.

        Returns comprehensive trend summary including slope, significance,
        smoothing, change points, and forecast.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch data
        cur.execute("""
            SELECT mv.value, mv.computed_at
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND md.metric_key = %s
            AND mv.verified = TRUE
            AND mv.computed_at > NOW() - INTERVAL '%s days'
            ORDER BY mv.computed_at ASC
        """, (location_id, metric_key, lookback_days))

        rows = cur.fetchall()
        cur.close()

        if len(rows) < 3:
            return {
                "metric_key": metric_key,
                "location_id": location_id,
                "trend_direction": "insufficient_data",
                "data_points": len(rows),
            }

        values = [float(r["value"]) for r in rows]
        timestamps = [
            (r["computed_at"] - rows[0]["computed_at"]).total_seconds() / 86400
            for r in rows
        ]

        # Compute trend
        trend = self._estimator.compute_trend(values, timestamps)

        # Mann-Kendall test
        mk_result = self._significance.mann_kendall_test(values)

        # Confidence interval on slope
        ci = self._significance.compute_confidence_interval(
            trend["slope"],
            trend["standard_error"],
            max(1, len(values) - 2),
        )

        # Smoothing
        smoothed = self._smoothing.exponential_smoothing(values, alpha=0.3)

        # Change points
        cp_result = self._change_points.cusum_detect(values)

        # Noise level (residual std from trend)
        residuals = [
            values[i] - (trend["slope"] * timestamps[i] + trend["intercept"])
            for i in range(len(values))
        ]
        noise_level = (
            (sum(r ** 2 for r in residuals) / len(residuals)) ** 0.5
            if residuals else 0.0
        )

        result = {
            "metric_key": metric_key,
            "location_id": location_id,
            "current_value": values[-1] if values else None,
            "trend_slope": trend["slope"],
            "trend_direction": trend["direction"],
            "trend_r_squared": trend["r_squared"],
            "trend_significance": mk_result["trend"],
            "p_value": mk_result["p_value"],
            "confidence_interval": ci,
            "seasonal_strength": None,
            "noise_level": round(noise_level, 4),
            "change_point_count": len(cp_result["change_points"]),
            "last_change_point_at": None,
            "smoothed_latest": smoothed[-1] if smoothed else None,
            "data_points": len(values),
            "period_start": rows[0]["computed_at"].isoformat(),
            "period_end": rows[-1]["computed_at"].isoformat(),
        }

        if cp_result["change_points"]:
            last_cp = cp_result["change_points"][-1]
            if "timestamp" in last_cp:
                result["last_change_point_at"] = last_cp["timestamp"]

        return result

    def compute_trend_summary(
        self, location_id: str
    ) -> List[Dict[str, Any]]:
        """Compute trend summary for all tracked metrics at a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT DISTINCT md.metric_key
            FROM metric_value mv
            JOIN metric_definition md ON md.id = mv.metric_id
            WHERE mv.location_id = %s AND mv.verified = TRUE
        """, (location_id,))

        metric_keys = [r["metric_key"] for r in cur.fetchall()]
        cur.close()

        summaries = []
        for key in metric_keys:
            summary = self.compute_trend_metrics(key, location_id)
            summaries.append(summary)

        # Persist to dashboard table
        self._persist_dashboard_metrics(summaries)

        return summaries

    def get_trend_alerts(
        self, location_id: str
    ) -> List[Dict[str, Any]]:
        """Get active trend-based alerts."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT * FROM trend_dashboard_metric
            WHERE location_id = %s
            AND computed_at > NOW() - INTERVAL '24 hours'
            AND (
                trend_direction = 'declining'
                OR trend_significance LIKE '%significant%'
                OR change_point_count > 0
            )
            ORDER BY computed_at DESC
        """, (location_id,))

        rows = cur.fetchall()
        cur.close()

        alerts = []
        for row in rows:
            row = dict(row)
            if row["trend_direction"] == "declining":
                alerts.append({
                    "type": "declining_trend",
                    "metric": row["metric_key"],
                    "severity": "warning",
                    "message": f"{row['metric_key']} is declining (slope: {row['trend_slope']})",
                })
            if "significant" in (row.get("trend_significance") or ""):
                alerts.append({
                    "type": "significant_trend",
                    "metric": row["metric_key"],
                    "severity": "info",
                    "message": f"Significant trend detected in {row['metric_key']}",
                })
            if row.get("change_point_count", 0) > 0:
                alerts.append({
                    "type": "change_point",
                    "metric": row["metric_key"],
                    "severity": "warning",
                    "message": f"{row['change_point_count']} regime shift(s) detected in {row['metric_key']}",
                })

        return alerts

    def get_trend_report(
        self, location_id: str
    ) -> Dict[str, Any]:
        """Generate formatted trend report for a location."""
        summaries = self.compute_trend_summary(location_id)

        improving = [s for s in summaries if s.get("trend_direction") == "improving"]
        declining = [s for s in summaries if s.get("trend_direction") == "declining"]
        stable = [s for s in summaries if s.get("trend_direction") == "stable"]
        change_points = [s for s in summaries if s.get("change_point_count", 0) > 0]

        return {
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_metrics": len(summaries),
            "improving_count": len(improving),
            "declining_count": len(declining),
            "stable_count": len(stable),
            "change_point_count": len(change_points),
            "improving_metrics": [s["metric_key"] for s in improving],
            "declining_metrics": [s["metric_key"] for s in declining],
            "summaries": summaries,
        }

    def _persist_dashboard_metrics(self, summaries: List[Dict]) -> None:
        """Persist computed trend metrics to the dashboard table."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for s in summaries:
            if "error" in s or s.get("trend_direction") == "insufficient_data":
                continue

            cur.execute("""
                INSERT INTO trend_dashboard_metric (
                    id, metric_key, location_id, current_value,
                    trend_slope, trend_direction, trend_r_squared,
                    trend_significance, seasonal_strength, noise_level,
                    change_point_count, last_change_point_at,
                    computed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), s["metric_key"], s["location_id"],
                s.get("current_value"),
                s.get("trend_slope"),
                s.get("trend_direction"),
                s.get("trend_r_squared"),
                s.get("trend_significance"),
                s.get("seasonal_strength"),
                s.get("noise_level"),
                s.get("change_point_count", 0),
                s.get("last_change_point_at"),
                datetime.now(timezone.utc),
            ))

        conn.commit()
        cur.close()
