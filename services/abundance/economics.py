"""Abundance Protocol: Coin Economics and Incentive Alignment.

Manages coin inflation, validator compensation, funding requests,
and incentive alignment tracking.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.economics")


def compute_compensation(
    conn,
    validator_id: str,
    round_id: str,
    accuracy_score: float,
) -> Dict[str, Any]:
    """Compute validator compensation from inflation based on accuracy.

    Accuracy bonus: validators whose reviews align with final impact get bonus.
    Overestimate penalty: validators who overestimate lose compensation.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get existing compensation record
    cur.execute("""
        SELECT * FROM validator_compensation
        WHERE round_id = %s AND evaluator_id = %s
    """, (round_id, validator_id))
    comp = cur.fetchone()

    if not comp:
        cur.close()
        return {"status": "error", "message": "No compensation record found"}

    comp = dict(comp)
    base = float(comp.get("base_compensation", 0) or 0)

    # Accuracy-based adjustment
    # accuracy_score: 1.0 = perfectly accurate, 0.0 = completely wrong
    accuracy_bonus = base * 0.2 * accuracy_score  # Up to 20% bonus for perfect accuracy
    overestimate_penalty = base * 0.3 * (1 - accuracy_score) if accuracy_score < 0.5 else 0

    total = base + accuracy_bonus - overestimate_penalty
    total = max(0, total)  # Never negative

    # Update compensation
    cur.execute("""
        UPDATE validator_compensation SET
            accuracy_bonus = %s,
            overestimate_penalty = %s,
            total_compensation = %s,
            status = 'calculated'
        WHERE id = %s
    """, (accuracy_bonus, overestimate_penalty, total, str(comp["id"])))

    # Log incentive alignment
    cur.execute("""
        INSERT INTO incentive_alignment_log
            (evaluator_id, round_id, accuracy_score, compensation_amount, alignment_score)
        VALUES (%s, %s, %s, %s, %s)
    """, (validator_id, round_id, accuracy_score, total, accuracy_score))

    conn.commit()
    cur.close()

    return {
        "validator_id": validator_id,
        "base": round(base, 2),
        "accuracy_bonus": round(accuracy_bonus, 2),
        "overestimate_penalty": round(overestimate_penalty, 2),
        "total_compensation": round(total, 2),
        "accuracy_score": accuracy_score,
    }


def issue_coins(
    conn,
    validation_id: str,
    impact_score: float,
    recipient_address: str,
    recipient_evaluator_id: str = None,
) -> str:
    """Issue coins based on validated impact score.

    Coins are issued from inflation, not from existing supply.
    """
    # Simple issuance formula: amount proportional to impact
    amount = impact_score * 0.1  # 0.1 coins per unit of impact

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO coin_inflation_event
            (validation_id, amount, recipient_address, recipient_evaluator_id,
             basis_impact_score, status)
        VALUES (%s, %s, %s, %s, %s, 'issued')
        RETURNING id
    """, (validation_id, amount, recipient_address, recipient_evaluator_id, impact_score))
    event_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Issued %.4f coins for validation %s (impact=%.1f)", amount, validation_id[:8], impact_score)
    return event_id


def check_value_preservation(conn) -> Dict[str, Any]:
    """Monitor inflation vs economic growth for value preservation."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Total coins issued
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_issued FROM coin_inflation_event WHERE status = 'issued'")
    total_issued = float(cur.fetchone()["total_issued"] or 0)

    # Total impact validated
    cur.execute("SELECT COALESCE(SUM(basis_impact_score), 0) AS total_impact FROM coin_inflation_event WHERE status = 'issued'")
    total_impact = float(cur.fetchone()["total_impact"] or 0)

    # Active inflation schedule
    cur.execute("SELECT * FROM inflation_schedule WHERE status = 'active' LIMIT 1")
    schedule = cur.fetchone()

    cur.close()

    # Value preservation check: inflation should be offset by impact growth
    if total_impact > 0:
        coins_per_impact = total_issued / total_impact
    else:
        coins_per_impact = 0

    return {
        "total_coins_issued": round(total_issued, 8),
        "total_impact_validated": round(total_impact, 4),
        "coins_per_unit_impact": round(coins_per_impact, 8),
        "inflation_rate": float(schedule["initial_inflation_rate"]) if schedule else None,
        "target_value_growth_pct": float(schedule["target_value_growth_pct"]) if schedule else None,
    }


def create_funding_request(
    conn,
    proposer_id: str,
    project_hash: str,
    expected_impact_score: float,
    requested_amount: float,
    timeline_months: int = None,
    contributor_breakdown: Dict[str, Any] = None,
    investor_terms: str = None,
    location_id: str = None,
    project_description: str = None,
) -> str:
    """Submit a structured funding request."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO funding_request
            (proposer_id, location_id, project_hash, project_description,
             expected_impact_score, requested_amount, timeline_months,
             contributor_breakdown, investor_terms, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'submitted')
        RETURNING id
    """, (
        proposer_id, location_id, project_hash, project_description,
        expected_impact_score, requested_amount, timeline_months,
        json.dumps(contributor_breakdown or {}), investor_terms,
    ))
    request_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created funding request %s (amount=%.2f, impact=%.1f)", request_id[:8], requested_amount, expected_impact_score)
    return request_id


def submit_bid(
    conn,
    request_id: str,
    investor_id: str,
    bid_amount: float,
    expected_return_pct: float = None,
    terms: str = None,
) -> str:
    """Submit an investor bid on a funding request."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO funding_bid
            (request_id, investor_id, bid_amount, expected_return_pct, terms, status)
        VALUES (%s, %s, %s, %s, %s, 'submitted')
        RETURNING id
    """, (request_id, investor_id, bid_amount, expected_return_pct, terms))
    bid_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Bid submitted: %.2f for request %s", bid_amount, request_id[:8])
    return bid_id


def compute_fund_distribution(conn, request_id: str) -> List[Dict[str, Any]]:
    """Compute contributor/influencer fund split based on breakdown."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get funding request
    cur.execute("SELECT * FROM funding_request WHERE id = %s", (request_id,))
    request = cur.fetchone()
    if not request:
        cur.close()
        return []

    request = dict(request)
    breakdown = request.get("contributor_breakdown", {})
    total_amount = float(request.get("requested_amount", 0) or 0)

    # Create distribution records
    results = []
    cur2 = conn.cursor()
    for entity_id, share_pct in breakdown.items():
        share_amount = total_amount * float(share_pct) / 100

        cur2.execute("""
            INSERT INTO fund_distribution
                (request_id, entity_id, entity_type, share_pct, share_amount, consensus_status, status)
            VALUES (%s, %s, 'contributor', %s, %s, 'pending', 'pending')
            RETURNING id
        """, (request_id, entity_id, share_pct, share_amount))
        dist_id = str(cur2.fetchone()[0])

        results.append({
            "distribution_id": dist_id,
            "entity_id": entity_id,
            "share_pct": share_pct,
            "share_amount": round(share_amount, 2),
        })

    conn.commit()
    cur.close()

    logger.info("Computed fund distribution for request %s: %d entities", request_id[:8], len(results))
    return results


def log_incentive_alignment(
    conn,
    evaluator_id: str,
    round_id: str,
    accuracy: float,
    compensation: float,
    expertise_change: float = 0,
) -> str:
    """Log incentive alignment for audit trail."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO incentive_alignment_log
            (evaluator_id, round_id, accuracy_score, compensation_amount,
             expertise_change, alignment_score)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (evaluator_id, round_id, accuracy, compensation, expertise_change, accuracy))
    log_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return log_id
