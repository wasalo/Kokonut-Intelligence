"""Consensus math for Real-time Delphi.

Computes aggregated statistics from panel contributions and measures
convergence (interquartile range, coefficient of variation, inter-submission
stability). Pure functions so they are trivially testable without a database.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


def median(values: Sequence[float]) -> Optional[float]:
    """Return the median of a sequence, or None if empty."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2.0)


def weighted_median(values: Sequence[float], weights: Sequence[float]) -> Optional[float]:
    """Return the weighted median.

    Weights need not sum to 1. Returns None if no values.
    """
    if not values:
        return None
    if len(values) != len(weights):
        raise ValueError("values and weights must have equal length")
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError("values must be finite")
    if any(not math.isfinite(float(w)) or w < 0 for w in weights):
        raise ValueError("weights must be finite and non-negative")
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total = sum(w for _, w in pairs)
    if total <= 0:
        return median(values)
    cumulative = 0.0
    for v, w in pairs:
        cumulative += w
        if cumulative >= total / 2.0:
            return float(v)
    return float(pairs[-1][0])


def mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def stddev(values: Sequence[float]) -> Optional[float]:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    assert m is not None
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def coefficient_of_variation(values: Sequence[float]) -> Optional[float]:
    """CV = stddev / |mean|. None if mean is 0 or values empty."""
    if not values:
        return None
    m = mean(values)
    if m is None or abs(m) < 1e-9:
        return None
    sd = stddev(values)
    assert sd is not None
    return round(sd / abs(m), 4)


def interquartile_range(values: Sequence[float]) -> Optional[float]:
    """IQR = Q3 - Q1 (linear interpolation). None if < 2 values."""
    if not values or len(values) < 2:
        return None
    s = sorted(values)
    q1 = _percentile(s, 25)
    q3 = _percentile(s, 75)
    return round(q3 - q1, 4)


def _percentile(s: List[float], p: float) -> float:
    """Linear-interpolation percentile (p in 0..100)."""
    if not s:
        return 0.0
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return s[lo]
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def stability_pct(
    prev_median: Optional[float],
    prev_iqr: Optional[float],
    cur_median: Optional[float],
    cur_iqr: Optional[float],
) -> Optional[float]:
    """Percentage change in dispersion between two consensus snapshots.

    Defined as the relative change in IQR (primary dispersion measure for
    Delphi). Lower = more stable. Returns None if no previous snapshot.
    """
    if prev_iqr is None or cur_iqr is None:
        return None
    if prev_iqr < 1e-9 and cur_iqr < 1e-9:
        return 0.0
    if prev_iqr < 1e-9:
        return 100.0
    change = abs(cur_iqr - prev_iqr) / prev_iqr * 100.0
    return round(change, 4)


def consensus_reached(
    iqr: Optional[float],
    participant_count: int,
    min_participants: int,
    iqr_threshold: float,
) -> bool:
    """Decide whether consensus is reached for one item.

    Consensus requires enough participants AND an IQR at or below threshold.
    """
    if iqr is None:
        return False
    if participant_count < min_participants:
        return False
    return iqr <= iqr_threshold


class ConsensusCalculator:
    """Aggregates contributions into consensus statistics for one item."""

    def compute(
        self,
        scores: Sequence[float],
        weights: Optional[Sequence[float]] = None,
    ) -> dict:
        """Compute full consensus dict for a list of scores.

        Args:
            scores: Raw contribution scores for one item.
            weights: Optional per-contribution expert weights.

        Returns:
            Dict with median, mean, iqr, stddev, cv, participant_count,
            weighted_median.
        """
        scores = list(scores)
        if not scores:
            return {
                "median": None,
                "mean": None,
                "iqr": None,
                "stddev": None,
                "cv": None,
                "participant_count": 0,
                "weighted_median": None,
            }

        if weights is None:
            weights = [1.0] * len(scores)

        return {
            "median": median(scores),
            "mean": mean(scores),
            "iqr": interquartile_range(scores),
            "stddev": stddev(scores),
            "cv": coefficient_of_variation(scores),
            "participant_count": len(scores),
            "weighted_median": weighted_median(scores, weights),
        }

    def evaluate_stopping(
        self,
        study_stopping_criteria: dict,
        item_consensus: dict,
        prev_history: Optional[dict],
        opened_at=None,
        now=None,
    ) -> Tuple[bool, dict]:
        """Evaluate whether the study should stop for an item.

        Stopping triggers (any):
          * consensus reached (iqr <= iqr_threshold and enough participants)
          * stability: IQR change vs previous snapshot <= stability_pct
          * duration: elapsed > max_duration_hours

        Returns (should_stop, detail_dict).
        """
        min_participants = int(study_stopping_criteria.get("min_participants", 3))
        iqr_threshold = float(study_stopping_criteria.get("iqr_threshold", 1.0))
        stability_pct_thr = float(study_stopping_criteria.get("stability_pct", 5.0))
        max_duration = float(study_stopping_criteria.get("max_duration_hours", 720))

        iqr = item_consensus.get("iqr")
        participant_count = item_consensus.get("participant_count", 0)

        reasons = []

        reached = consensus_reached(
            iqr, participant_count, min_participants, iqr_threshold
        )
        if reached:
            reasons.append("consensus_reached")

        stab = None
        median_shift = None
        if prev_history is not None:
            stab = stability_pct(
                prev_history.get("median"),
                prev_history.get("iqr"),
                item_consensus.get("median"),
                iqr,
            )
            if stab is not None and stab <= stability_pct_thr and participant_count >= min_participants:
                previous_median = prev_history.get("median")
                current_median = item_consensus.get("median")
                if previous_median is not None and current_median is not None:
                    median_shift = abs(float(current_median) - float(previous_median))
                median_threshold = float(study_stopping_criteria.get("median_shift_threshold", iqr_threshold * 0.1))
                if median_shift is not None and median_shift <= median_threshold:
                    reasons.append("stable")

        duration_trigger = False
        if opened_at is not None and now is not None:
            elapsed_hours = (now - opened_at).total_seconds() / 3600.0
            if elapsed_hours >= max_duration:
                duration_trigger = True
                reasons.append("duration_exceeded")

        participation_met = participant_count >= min_participants
        stable = "stable" in reasons
        should_stop = bool(reached or stable or duration_trigger)
        if reached and duration_trigger:
            outcome = "time_limit_with_consensus"
        elif reached:
            outcome = "consensus_reached"
        elif duration_trigger:
            outcome = "time_limit_without_consensus"
        elif stable:
            outcome = "stable_without_consensus"
        elif not participation_met:
            outcome = "insufficient_participation"
        elif prev_history is None:
            outcome = "insufficient_stability_history"
        else:
            outcome = "continue"
        return should_stop, {
            "outcome": outcome,
            "consensus_reached": reached,
            "participation_met": participation_met,
            "stability_pct": stab,
            "median_shift": median_shift,
            "stability_met": stable,
            "duration_trigger": duration_trigger,
            "reasons": reasons,
        }
