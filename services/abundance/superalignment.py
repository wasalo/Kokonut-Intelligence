"""Superalignment framework — cross-ecosystem alignment and impact propagation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.superalignment")


def register_ecosystem(
    conn,
    ecosystem_name: str,
    chain: str = None,
    currency_name: str = None,
    currency_symbol: str = None,
    chain_id: int = None,
    contract_address: str = None,
    participation_rules: str = None,
) -> str:
    """Register an abundance ecosystem."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ecosystem_registry
            (ecosystem_name, chain, currency_name, currency_symbol,
             chain_id, contract_address, participation_rules)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ecosystem_name) DO UPDATE SET
            chain = EXCLUDED.chain,
            currency_name = EXCLUDED.currency_name,
            updated_at = NOW()
        RETURNING id
    """, (ecosystem_name, chain, currency_name, currency_symbol,
          chain_id, contract_address, participation_rules))
    eco_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Registered ecosystem: %s", ecosystem_name)
    return eco_id


def propagate_impact(
    conn,
    contributor_id: str,
    source_ecosystem_id: str,
    target_ecosystem_id: str,
    impact_score: float,
    project_hash: str = None,
    impact_category: str = None,
) -> str:
    """Propagate impact across ecosystems."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cross_ecosystem_impact
            (contributor_id, source_ecosystem_id, target_ecosystem_id,
             project_hash, impact_score, impact_category, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'recorded')
        RETURNING id
    """, (
        contributor_id, source_ecosystem_id, target_ecosystem_id,
        project_hash, impact_score, impact_category,
    ))
    propagation_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Propagated impact %.1f from ecosystem %s to %s", impact_score, source_ecosystem_id[:8], target_ecosystem_id[:8])
    return propagation_id


def compute_alignment_score(conn, ecosystem_id: str, period_start: str = None, period_end: str = None) -> Dict[str, Any]:
    """Compute superalignment score for an ecosystem.

    Measures participant alignment and cross-ecosystem alignment.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Participant alignment: ratio of active contributors to total participants
    cur.execute("""
        SELECT
            COUNT(DISTINCT e.id) AS total_evaluators,
            COUNT(DISTINCT CASE WHEN e.last_active_at >= NOW() - INTERVAL '30 days' THEN e.id END) AS active_evaluators,
            COUNT(DISTINCT CASE WHEN e.trust_score >= 0.7 THEN e.id END) AS high_trust_evaluators
        FROM evaluator e WHERE e.status = 'active'
    """)
    participants = dict(cur.fetchone() or {})

    # Cross-ecosystem alignment: count of validated cross-ecosystem impacts
    cur.execute("""
        SELECT COUNT(*) AS cross_impacts
        FROM cross_ecosystem_impact
        WHERE source_ecosystem_id = %s OR target_ecosystem_id = %s
        AND status = 'validated'
    """, (ecosystem_id, ecosystem_id))
    cross = dict(cur.fetchone() or {})

    # Adversarial signals: count of disputes
    cur.execute("""
        SELECT COUNT(*) AS disputes
        FROM cross_ecosystem_impact
        WHERE (source_ecosystem_id = %s OR target_ecosystem_id = %s)
        AND status = 'disputed'
    """, (ecosystem_id, ecosystem_id))
    adv = dict(cur.fetchone() or {})

    cur.close()

    total = int(participants.get("total_evaluators", 0) or 0)
    active = int(participants.get("active_evaluators", 0) or 0)
    high_trust = int(participants.get("high_trust_evaluators", 0) or 0)
    cross_impacts = int(cross.get("cross_impacts", 0) or 0)
    disputes = int(adv.get("disputes", 0) or 0)

    # Compute scores
    participant_score = (active / max(total, 1)) * 50 + (high_trust / max(total, 1)) * 50
    cross_score = min(100, cross_impacts * 10)
    adv_penalty = min(50, disputes * 5)
    cross_alignment = max(0, cross_score - adv_penalty)

    composite = (participant_score * 0.6) + (cross_alignment * 0.4)

    return {
        "ecosystem_id": ecosystem_id,
        "participant_alignment_score": round(participant_score, 2),
        "cross_ecosystem_alignment_score": round(cross_alignment, 2),
        "composite_alignment_score": round(composite, 2),
        "adversarial_signals_detected": disputes,
        "total_evaluators": total,
        "active_evaluators": active,
        "cross_ecosystem_impacts": cross_impacts,
    }


def detect_adversarial_dynamics(conn, ecosystem_id: str) -> List[Dict[str, Any]]:
    """Detect patterns that suggest adversarial dynamics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    signals = []

    # High dispute rate
    cur.execute("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'disputed') AS disputes
        FROM cross_ecosystem_impact
        WHERE source_ecosystem_id = %s OR target_ecosystem_id = %s
    """, (ecosystem_id, ecosystem_id))
    imp = dict(cur.fetchone() or {})
    total = int(imp.get("total", 0) or 0)
    disputes = int(imp.get("disputes", 0) or 0)
    if total > 0 and disputes / total > 0.2:
        signals.append({"signal": "high_dispute_rate", "value": round(disputes / total, 4), "severity": "warning"})

    # Low active evaluator ratio
    cur.execute("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE last_active_at >= NOW() - INTERVAL '30 days') AS active
        FROM evaluator WHERE status = 'active'
    """)
    ev = dict(cur.fetchone() or {})
    total_ev = int(ev.get("total", 0) or 0)
    active_ev = int(ev.get("active", 0) or 0)
    if total_ev > 0 and active_ev / total_ev < 0.1:
        signals.append({"signal": "low_engagement", "value": round(active_ev / total_ev, 4), "severity": "warning"})

    cur.close()
    return signals
