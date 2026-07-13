"""Change-Point Detector — regime shift detection using CUSUM and PELT.

Identifies when the underlying pattern of a time series changes.
"""

from __future__ import annotations

import uuid
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from .config import CUSUM_THRESHOLD, CUSUM_DRIFT, PELT_PENALTY


class ChangePointDetector:
    """Detects change points and regime shifts in time series data."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def cusum_detect(
        self,
        series: List[float],
        threshold: float = CUSUM_THRESHOLD,
        drift: float = CUSUM_DRIFT,
    ) -> Dict[str, Any]:
        """CUSUM (Cumulative Sum) change-point detection.

        Detects shifts in the mean of the process.

        Args:
            series: List of numeric values.
            threshold: Detection threshold for cumulative sum.
            drift: Allowable drift before reset.

        Returns:
            Dict with change points, statistics, and segment info.
        """
        n = len(series)
        if n < 5:
            return {"change_points": [], "segments": [], "data_points": n}

        # Compute mean and std
        mean = sum(series) / n
        std = (sum((x - mean) ** 2 for x in series) / n) ** 0.5
        if std == 0:
            return {"change_points": [], "segments": [], "data_points": n}

        # Normalize
        normalized = [(x - mean) / std for x in series]

        # CUSUM algorithm
        s_pos = [0.0]
        s_neg = [0.0]
        change_points = []

        for i in range(1, n):
            s_pos_new = max(0, s_pos[-1] + normalized[i] - drift)
            s_neg_new = max(0, s_neg[-1] - normalized[i] - drift)

            s_pos.append(s_pos_new)
            s_neg.append(s_neg_new)

            if s_pos_new > threshold or s_neg_new > threshold:
                direction = "increase" if s_pos_new > threshold else "decrease"
                change_points.append({
                    "index": i,
                    "direction": direction,
                    "magnitude": round(max(s_pos_new, s_neg_new), 4),
                })
                s_pos[-1] = 0.0
                s_neg[-1] = 0.0

        # Build segments
        segments = self._build_segments(series, [cp["index"] for cp in change_points])

        return {
            "change_points": change_points,
            "segments": segments,
            "cusum_positive": [round(s, 4) for s in s_pos],
            "cusum_negative": [round(s, 4) for s in s_neg],
            "data_points": n,
            "threshold": threshold,
        }

    def pelt_detect(
        self,
        series: List[float],
        penalty: float = PELT_PENALTY,
    ) -> Dict[str, Any]:
        """PELT (Pruned Exact Linear Time) change-point detection.

        Detects multiple change points by minimizing a cost function.

        Args:
            series: List of numeric values.
            penalty: Penalty for adding a change point (higher = fewer change points).

        Returns:
            Dict with change points and segments.
        """
        n = len(series)
        if n < 5:
            return {"change_points": [], "segments": [], "data_points": n}

        # Simple PELT implementation using dynamic programming
        change_indices = self._pelt_algorithm(series, penalty)

        change_points = []
        for idx in change_indices:
            if 0 < idx < n:
                # Compute magnitude of change
                pre = series[max(0, idx - 5):idx]
                post = series[idx:min(n, idx + 5)]
                if pre and post:
                    pre_mean = sum(pre) / len(pre)
                    post_mean = sum(post) / len(post)
                    direction = "increase" if post_mean > pre_mean else "decrease"
                    change_points.append({
                        "index": idx,
                        "direction": direction,
                        "magnitude": round(abs(post_mean - pre_mean), 4),
                    })

        segments = self._build_segments(series, [cp["index"] for cp in change_points])

        return {
            "change_points": change_points,
            "segments": segments,
            "data_points": n,
            "penalty": penalty,
        }

    def detect_regime_shifts(
        self,
        metric_key: str,
        location_id: str,
        lookback_days: int = 365,
    ) -> Dict[str, Any]:
        """Auto-detect regime shifts for a metric.

        Args:
            metric_key: The metric to analyze.
            location_id: Location UUID.
            lookback_days: How many days of data to use.

        Returns:
            Detected change points with context.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

        if len(rows) < 10:
            return {
                "metric_key": metric_key,
                "location_id": location_id,
                "change_points": [],
                "data_points": len(rows),
            }

        values = [float(r["value"]) for r in rows]
        timestamps = [r["computed_at"].isoformat() for r in rows]

        # Run both detection methods
        cusum_result = self.cusum_detect(values)
        pelt_result = self.pelt_detect(values)

        # Merge and deduplicate change points
        all_points = cusum_result["change_points"] + pelt_result["change_points"]
        merged = self._merge_change_points(all_points)

        # Add timestamps
        for cp in merged:
            idx = cp["index"]
            if 0 <= idx < len(timestamps):
                cp["timestamp"] = timestamps[idx]

        # Persist results
        conn2 = self._get_conn()
        cur2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        for cp in merged:
            cur2.execute("""
                INSERT INTO change_point (
                    id, metric_key, location_id, detection_method,
                    change_point_index, change_point_timestamp,
                    magnitude, direction, confidence,
                    status, detected_at
                ) VALUES (%s, %s, %s, 'cusum', %s, %s, %s, %s, %s, 'detected', %s)
            """, (
                str(uuid.uuid4()), metric_key, location_id,
                cp["index"], cp.get("timestamp"),
                cp["magnitude"], cp["direction"], min(cp.get("confidence", 0.5), 1.0),
                datetime.now(timezone.utc),
            ))

        conn2.commit()
        cur2.close()

        return {
            "metric_key": metric_key,
            "location_id": location_id,
            "change_points": merged,
            "cusum_points": len(cusum_result["change_points"]),
            "pelt_points": len(pelt_result["change_points"]),
            "data_points": len(values),
        }

    def classify_change(
        self, old_segment: List[float], new_segment: List[float]
    ) -> str:
        """Classify the type of change between two segments."""
        if not old_segment or not new_segment:
            return "unknown"

        old_mean = sum(old_segment) / len(old_segment)
        new_mean = sum(new_segment) / len(new_segment)
        old_std = (sum((x - old_mean) ** 2 for x in old_segment) / len(old_segment)) ** 0.5
        new_std = (sum((x - new_mean) ** 2 for x in new_segment) / len(new_segment)) ** 0.5

        mean_change = abs(new_mean - old_mean) / (abs(old_mean) + 1e-10)
        var_change = abs(new_std - old_std) / (old_std + 1e-10)

        if mean_change > 0.2:
            return "level_shift"
        elif var_change > 0.5:
            return "variance_change"
        elif new_mean > old_mean * 1.1:
            return "increase"
        elif new_mean < old_mean * 0.9:
            return "decrease"
        else:
            return "minor_fluctuation"

    # --- Private helpers ---

    def _pelt_algorithm(
        self, series: List[float], penalty: float
    ) -> List[int]:
        """Simplified PELT algorithm."""
        n = len(series)
        cost = lambda s, e: self._segment_cost(series, s, e)

        # F[k] = minimum cost for series[0:k]
        F = [0.0] + [float("inf")] * n
        cp_list = [[] for _ in range(n + 1)]

        for k in range(1, n + 1):
            for j in range(max(0, k - 50), k):  # Limit lookback for efficiency
                c = F[j] + cost(j, k) + penalty
                if c < F[k]:
                    F[k] = c
                    cp_list[k] = cp_list[j] + [k]

        return cp_list[n][:-1] if cp_list[n] else []

    def _segment_cost(self, series: List[float], start: int, end: int) -> float:
        """Compute cost of a segment (sum of squared deviations from mean)."""
        segment = series[start:end]
        if not segment:
            return 0.0
        mean = sum(segment) / len(segment)
        return sum((x - mean) ** 2 for x in segment)

    def _build_segments(
        self, series: List[float], change_indices: List[int]
    ) -> List[Dict[str, Any]]:
        """Build segment descriptions from change points."""
        segments = []
        boundaries = [0] + sorted(change_indices) + [len(series)]

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            segment = series[start:end]
            if segment:
                segments.append({
                    "start_index": start,
                    "end_index": end,
                    "length": len(segment),
                    "mean": round(sum(segment) / len(segment), 4),
                    "std": round(
                        (sum((x - sum(segment) / len(segment)) ** 2 for x in segment) / len(segment)) ** 0.5,
                        4,
                    ),
                })

        return segments

    def _merge_change_points(
        self, points: List[Dict], tolerance: int = 5
    ) -> List[Dict[str, Any]]:
        """Merge change points that are close together."""
        if not points:
            return []

        sorted_points = sorted(points, key=lambda p: p["index"])
        merged = [sorted_points[0]]

        for cp in sorted_points[1:]:
            if cp["index"] - merged[-1]["index"] < tolerance:
                # Keep the one with higher magnitude
                if cp["magnitude"] > merged[-1]["magnitude"]:
                    merged[-1] = cp
            else:
                merged.append(cp)

        return merged
