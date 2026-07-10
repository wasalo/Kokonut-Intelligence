"""Externality countermeasures — tracking, alerting, and remediation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.externalities")


def compute_externality_index(conn, location_id: str, period_start: str, period_end: str) -> Dict[str, Any]:
    """Compute composite externality score from hidden cost observations."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Aggregate hidden costs by category
    cur.execute("""
        SELECT
            COALESCE(SUM(estimated_value_usd), 0) AS total_hidden_cost,
            COALESCE(SUM(CASE WHEN cost_category IN ('pollution', 'environmental') THEN estimated_value_usd ELSE 0 END), 0) AS environmental_impact,
            COALESCE(SUM(CASE WHEN cost_category IN ('health', 'social') THEN estimated_value_usd ELSE 0 END), 0) AS social_impact,
            COALESCE(SUM(CASE WHEN cost_category IN ('knowledge', 'intergenerational') THEN estimated_value_usd ELSE 0 END), 0) AS natural_capital_impact,
            COUNT(*) AS observation_count
        FROM hidden_cost_observation
        WHERE location_id = %s
        AND observation_date BETWEEN %s AND %s
    """, (location_id, period_start, period_end))
    costs = dict(cur.fetchone() or {})

    # Get natural capital valuation for context
    cur.execute("""
        SELECT COALESCE(SUM(total_value_usd), 0) AS total_natural_capital
        FROM natural_capital_valuation
        WHERE location_id = %s
    """, (location_id,))
    nc = dict(cur.fetchone() or {})

    total_cost = float(costs.get("total_hidden_cost", 0) or 0)
    nc_value = float(nc.get("total_natural_capital", 0) or 0)

    # Compute externality score (0-100, higher = worse)
    if nc_value > 0:
        score = min(100, (total_cost / nc_value) * 100)
    else:
        score = min(100, total_cost / 10)  # Fallback: $10 = score 1

    # Determine severity
    if score >= 75:
        severity = "critical"
    elif score >= 50:
        severity = "high"
    elif score >= 25:
        severity = "moderate"
    elif score > 0:
        severity = "low"
    else:
        severity = "negligible"

    cur.execute("""
        INSERT INTO externality_index
            (location_id, period_start, period_end, total_hidden_cost_usd,
             externality_score, severity, natural_capital_impact,
             social_impact, environmental_impact)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        location_id, period_start, period_end, total_cost,
        round(score, 2), severity,
        float(costs.get("natural_capital_impact", 0) or 0),
        float(costs.get("social_impact", 0) or 0),
        float(costs.get("environmental_impact", 0) or 0),
    ))
    index_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    return {
        "externality_index_id": index_id,
        "total_hidden_cost": round(total_cost, 2),
        "externality_score": round(score, 2),
        "severity": severity,
    }


def check_externality_thresholds(conn, location_id: str) -> List[Dict[str, Any]]:
    """Check externality levels against thresholds and create alerts."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get latest externality index
    cur.execute("""
        SELECT * FROM externality_index
        WHERE location_id = %s
        ORDER BY period_end DESC, computed_at DESC
        LIMIT 1
    """, (location_id,))
    index = cur.fetchone()

    if not index:
        cur.close()
        return []

    index = dict(index)
    alerts = []

    # Check thresholds
    if float(index.get("externality_score", 0) or 0) >= 75:
        alert = _create_alert(conn, location_id, str(index["id"]), "externality_critical",
                              "critical", f"Externality score {index['externality_score']} exceeds critical threshold",
                              75.0, float(index["externality_score"]))
        alerts.append(alert)
    elif float(index.get("externality_score", 0) or 0) >= 50:
        alert = _create_alert(conn, location_id, str(index["id"]), "externality_high",
                              "warning", f"Externality score {index['externality_score']} exceeds warning threshold",
                              50.0, float(index["externality_score"]))
        alerts.append(alert)

    cur.close()
    return alerts


def _create_alert(conn, location_id: str, index_id: str, alert_type: str,
                  severity: str, message: str, threshold: float, actual: float) -> Dict[str, Any]:
    """Create an externality alert."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO externality_alert
            (location_id, externality_index_id, alert_type, severity, message,
             threshold_value, actual_value, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
        RETURNING id
    """, (location_id, index_id, alert_type, severity, message, threshold, actual))
    alert_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return {"alert_id": alert_id, "severity": severity, "message": message}


def propose_counteraction(
    conn,
    location_id: str,
    action_type: str,
    description: str,
    target_reduction_pct: float = None,
    responsible_party: str = None,
    start_date: str = None,
    target_date: str = None,
) -> str:
    """Propose a remediation action for an externality."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO externality_counteraction
            (location_id, action_type, description, target_reduction_pct,
             responsible_party, start_date, target_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'proposed')
        RETURNING id
    """, (
        location_id, action_type, description, target_reduction_pct,
        responsible_party, start_date, target_date,
    ))
    counter_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return counter_id


def track_counteraction_progress(
    conn,
    counteraction_id: str,
    progress_pct: float,
    evidence_urls: List[str] = None,
) -> Dict[str, Any]:
    """Track remediation progress."""
    status = "completed" if progress_pct >= 100 else "in_progress"

    cur = conn.cursor()
    cur.execute("""
        UPDATE externality_counteraction
        SET progress_pct = %s, status = %s, evidence_urls = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, action_type, progress_pct, status
    """, (progress_pct, status, evidence_urls or [], counteraction_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()

    return dict(row) if row else {"status": "error", "message": "Counteraction not found"}
