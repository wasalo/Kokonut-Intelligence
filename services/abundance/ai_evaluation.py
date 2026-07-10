"""AI-powered impact evaluation with human-in-the-loop validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.ai_evaluation")


def evaluate_impact(
    conn,
    location_id: str,
    evaluation_type: str = "ecological",
    period_start: str = None,
    period_end: str = None,
) -> Dict[str, Any]:
    """AI-powered impact evaluation using governed data.

    Aggregates agent outputs and governed metrics into a composite
    impact score. This is advisory — human validation required.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Gather agent summaries
    cur.execute("""
        SELECT summary_type, summary_text, metadata
        FROM ai_summary
        WHERE location_id = %s AND status = 'published'
        ORDER BY created_at DESC LIMIT 5
    """, (location_id,))
    summaries = [dict(r) for r in cur.fetchall()]

    # Gather metric values
    cur.execute("""
        SELECT metric_name, value, unit
        FROM metric_value
        WHERE location_id = %s AND verified = TRUE
        ORDER BY computation_date DESC LIMIT 20
    """, (location_id,))
    metrics = [dict(r) for r in cur.fetchall()]

    # Gather EBF scorecard
    cur.execute("""
        SELECT overall_score, overall_confidence
        FROM ebf_scorecard
        WHERE location_id = %s AND status = 'published'
        ORDER BY period_end DESC LIMIT 1
    """, (location_id,))
    ebf = dict(cur.fetchone() or {})

    cur.close()

    # Compute composite impact score (0-100)
    # Weighted from available data sources
    scores = []

    if ebf.get("overall_score"):
        scores.append(float(ebf["overall_score"]) * 10)  # EBF is 0-10, scale to 0-100

    if summaries:
        # Each summary contributes to confidence
        summary_confidence = min(100, len(summaries) * 20)
        scores.append(summary_confidence)

    if metrics:
        # Metrics completeness contributes to confidence
        metric_completeness = min(100, len(metrics) * 5)
        scores.append(metric_completescore)

    impact_score = sum(scores) / len(scores) if scores else 0
    confidence = min(1.0, len(summaries) * 0.2 + len(metrics) * 0.05)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_impact_evaluation
            (location_id, evaluation_type, period_start, period_end,
             impact_score, confidence, methodology, evidence_sources,
             agent_outputs, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ai_generated')
        RETURNING id
    """, (
        location_id, evaluation_type, period_start, period_end,
        round(impact_score, 4), round(confidence, 4),
        "agent_aggregation_v1",
        [s.get("summary_type") for s in summaries],
        json.dumps({"summaries": len(summaries), "metrics": len(metrics)}),
    ))
    eval_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("AI impact evaluation: %s score=%.1f confidence=%.2f", eval_id[:8], impact_score, confidence)
    return {
        "evaluation_id": eval_id,
        "impact_score": round(impact_score, 4),
        "confidence": round(confidence, 4),
        "summaries_used": len(summaries),
        "metrics_used": len(metrics),
    }


def validate_evaluation(
    conn,
    evaluation_id: str,
    validator_id: str,
    validation_result: str,
    notes: str = None,
) -> Dict[str, Any]:
    """Human validation of AI-generated evaluation.

    Args:
        validation_result: 'approved', 'rejected', or 'needs_revision'
    """
    cur = conn.cursor()
    cur.execute("""
        UPDATE ai_impact_evaluation
        SET human_validator_id = %s, human_validation_result = %s,
            human_validation_notes = %s, validated_at = NOW(),
            status = CASE
                WHEN %s = 'approved' THEN 'validated'
                WHEN %s = 'rejected' THEN 'rejected'
                ELSE 'pending_validation'
            END,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, impact_score, human_validation_result
    """, (validator_id, validation_result, notes, validation_result, validation_result, evaluation_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()

    if not row:
        return {"status": "error", "message": "Evaluation not found"}

    return {
        "evaluation_id": evaluation_id,
        "validation_result": validation_result,
        "impact_score": float(row[1]) if row[1] else None,
    }


def compute_evaluation_confidence(conn, evaluation_id: str) -> Dict[str, Any]:
    """Compute confidence from data completeness."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM ai_impact_evaluation WHERE id = %s", (evaluation_id,))
    ev = cur.fetchone()
    if not ev:
        cur.close()
        return {"status": "error", "message": "Evaluation not found"}

    ev = dict(ev)
    location_id = ev["location_id"]

    # Check data completeness
    checks = {}

    # Has EBF scorecard?
    cur.execute("SELECT COUNT(*) AS c FROM ebf_scorecard WHERE location_id = %s AND status = 'published'", (location_id,))
    checks["ebf_scorecard"] = dict(cur.fetchone())["c"] > 0

    # Has carbon balance?
    cur.execute("SELECT COUNT(*) AS c FROM v_carbon_balance WHERE location_id = %s", (location_id,))
    checks["carbon_balance"] = dict(cur.fetchone())["c"] > 0

    # Has training data?
    cur.execute("SELECT COUNT(*) AS c FROM training_session WHERE location_id = %s", (location_id,))
    checks["training_data"] = dict(cur.fetchone())["c"] > 0

    # Has revenue data?
    cur.execute("SELECT COUNT(*) AS c FROM revenue_event WHERE location_id = %s", (location_id,))
    checks["revenue_data"] = dict(cur.fetchone())["c"] > 0

    # Has externality data?
    cur.execute("SELECT COUNT(*) AS c FROM hidden_cost_observation WHERE location_id = %s", (location_id,))
    checks["externality_data"] = dict(cur.fetchone())["c"] > 0

    # Has attestations?
    cur.execute("SELECT COUNT(*) AS c FROM attestation_record WHERE subject_id = %s AND status = 'published'", (location_id,))
    checks["attestations"] = dict(cur.fetchone())["c"] > 0

    cur.close()

    completeness = sum(1 for v in checks.values() if v) / len(checks)

    return {
        "evaluation_id": evaluation_id,
        "data_completeness": round(completeness, 4),
        "checks": checks,
    }
