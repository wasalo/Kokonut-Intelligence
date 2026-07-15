"""SWOT Enhanced service — TOWS Matrix, Factor Classification, Competitor SWOT.

Extends the base SWOT analysis with:
- Classified factors (internal/external, category tagging)
- TOWS matrix strategic option generation (SO/ST/WO/WT)
- Competitor SWOT tracking
- Temporal snapshots with diff tracking
- Action linkage to decision policies and work items
- Strategic fit scoring
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db

# Factor categories per Wikipedia's classification
INTERNAL_CATEGORIES = [
    "human_resources", "physical_resources", "financial",
    "activities_processes", "past_experiences",
]
EXTERNAL_CATEGORIES = [
    "future_trends", "economy", "funding_sources",
    "demographics", "physical_environment", "legislation", "events",
]

FACTOR_TYPE_TO_CLASSIFICATION = {
    "strength": "internal",
    "weakness": "internal",
    "opportunity": "external",
    "threat": "external",
}

TOWS_LABELS = {
    "SO": "Maxi-Maxi (Aggressive)",
    "ST": "Maxi-Mini (Diversification)",
    "WO": "Mini-Maxi (Turnaround)",
    "WT": "Mini-Mini (Defensive)",
}


# ──────────────────────────────────────────────
# Factor Classification
# ──────────────────────────────────────────────

def create_factor(
    conn, swot_id: str, factor_type: str, category: str,
    description: str, priority: int = 0, confidence: float = 0.5,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    classification = FACTOR_TYPE_TO_CLASSIFICATION.get(factor_type)
    if not classification:
        raise ValueError(f"invalid factor_type: {factor_type}")
    if factor_type in ("strength", "weakness") and category not in INTERNAL_CATEGORIES:
        raise ValueError(f"{factor_type} must use an internal category: {INTERNAL_CATEGORIES}")
    if factor_type in ("opportunity", "threat") and category not in EXTERNAL_CATEGORIES:
        raise ValueError(f"{factor_type} must use an external category: {EXTERNAL_CATEGORIES}")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO swot_factor (
                swot_id, factor_type, classification, category,
                description, priority, confidence, source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, factor_type, classification, category, description
            """,
            (swot_id, factor_type, classification, category,
             description, priority, confidence, source),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_factors(
    conn, swot_id: str, factor_type: Optional[str] = None,
    classification: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conditions = ["swot_id = %s"]
    params: list = [swot_id]
    if factor_type:
        conditions.append("factor_type = %s")
        params.append(factor_type)
    if classification:
        conditions.append("classification = %s")
        params.append(classification)
    where = " AND ".join(conditions)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT id, factor_type, classification, category, description,
                   priority, confidence, source, created_at
            FROM swot_factor
            WHERE {where}
            ORDER BY factor_type, priority DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def delete_factor(conn, factor_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM swot_factor WHERE id = %s", (factor_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


# ──────────────────────────────────────────────
# TOWS Matrix Generation
# ──────────────────────────────────────────────

def generate_tows(conn, swot_id: str) -> Dict[str, Any]:
    """Auto-generate TOWS strategies from classified factors.

    For each TOWS type, finds matching factor pairs and generates
    strategy descriptions with action suggestions.
    """
    factors = list_factors(conn, swot_id)
    by_type = {}
    for f in factors:
        by_type.setdefault(f["factor_type"], []).append(f)

    strengths = by_type.get("strength", [])
    weaknesses = by_type.get("weakness", [])
    opportunities = by_type.get("opportunity", [])
    threats = by_type.get("threat", [])

    strategies = []

    # SO: Strengths × Opportunities (Maxi-Maxi)
    so_pairs = _match_pairs(strengths, opportunities)
    so_desc = _generate_strategy_description("SO", so_pairs)
    strategies.append(_upsert_strategy(
        conn, swot_id, "SO", TOWS_LABELS["SO"], so_desc, so_pairs,
    ))

    # ST: Strengths × Threats (Maxi-Mini)
    st_pairs = _match_pairs(strengths, threats)
    st_desc = _generate_strategy_description("ST", st_pairs)
    strategies.append(_upsert_strategy(
        conn, swot_id, "ST", TOWS_LABELS["ST"], st_desc, st_pairs,
    ))

    # WO: Weaknesses × Opportunities (Mini-Maxi)
    wo_pairs = _match_pairs(weaknesses, opportunities)
    wo_desc = _generate_strategy_description("WO", wo_pairs)
    strategies.append(_upsert_strategy(
        conn, swot_id, "WO", TOWS_LABELS["WO"], wo_desc, wo_pairs,
    ))

    # WT: Weaknesses × Threats (Mini-Mini)
    wt_pairs = _match_pairs(weaknesses, threats)
    wt_desc = _generate_strategy_description("WT", wt_pairs)
    strategies.append(_upsert_strategy(
        conn, swot_id, "WT", TOWS_LABELS["WT"], wt_desc, wt_pairs,
    ))

    return {
        "swot_id": swot_id,
        "strategies": strategies,
        "factor_counts": {
            "strengths": len(strengths),
            "weaknesses": len(weaknesses),
            "opportunities": len(opportunities),
            "threats": len(threats),
        },
    }


def _match_pairs(
    left: List[Dict], right: List[Dict],
) -> List[Dict[str, Any]]:
    """Match factors from two lists by category overlap and priority."""
    pairs = []
    for l_item in left:
        for r_item in right:
            # Score pair: same category = higher priority
            category_match = 1.0 if l_item.get("category") == r_item.get("category") else 0.0
            priority_score = (l_item.get("priority", 0) + r_item.get("priority", 0)) / 20.0
            confidence_avg = (
                float(l_item.get("confidence", 0.5)) + float(r_item.get("confidence", 0.5))
            ) / 2.0
            score = category_match * 0.5 + priority_score * 0.3 + confidence_avg * 0.2
            if score > 0.2 or (not left or not right):
                pairs.append({
                    "left_id": str(l_item["id"]),
                    "left_type": l_item["factor_type"],
                    "left_desc": l_item["description"],
                    "right_id": str(r_item["id"]),
                    "right_type": r_item["factor_type"],
                    "right_desc": r_item["description"],
                    "score": round(score, 3),
                    "category_match": category_match > 0,
                })
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs[:10]  # Top 10 pairs


def _generate_strategy_description(
    strategy_type: str, pairs: List[Dict],
) -> str:
    if not pairs:
        return f"No matching factor pairs for {strategy_type} strategy."
    top = pairs[0]
    if strategy_type == "SO":
        return (
            f"Leverage '{top['left_desc']}' to capitalize on '{top['right_desc']}'. "
            f"{len(pairs)} potential pairings identified."
        )
    elif strategy_type == "ST":
        return (
            f"Use '{top['left_desc']}' to mitigate threat '{top['right_desc']}'. "
            f"{len(pairs)} potential pairings identified."
        )
    elif strategy_type == "WO":
        return (
            f"Address weakness '{top['left_desc']}' to capture opportunity '{top['right_desc']}'. "
            f"{len(pairs)} potential pairings identified."
        )
    else:  # WT
        return (
            f"Minimize weakness '{top['left_desc']}' to reduce exposure to '{top['right_desc']}'. "
            f"{len(pairs)} potential pairings identified."
        )


def _upsert_strategy(
    conn, swot_id: str, strategy_type: str, strategy_label: str,
    description: str, pairs: List[Dict],
) -> Dict[str, Any]:
    pair_data = [
        {
            "left_id": p["left_id"], "right_id": p["right_id"],
            "score": p["score"], "category_match": p["category_match"],
        }
        for p in pairs
    ]
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO towS_strategy (swot_id, strategy_type, strategy_label, description, factor_pairs)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (swot_id, strategy_type) DO UPDATE
            SET description = EXCLUDED.description,
                factor_pairs = EXCLUDED.factor_pairs,
                updated_at = NOW()
            RETURNING id, strategy_type, strategy_label, description, status
            """,
            (swot_id, strategy_type, strategy_label, description, json.dumps(pair_data)),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def get_tows(conn, swot_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, strategy_type, strategy_label, description,
                   factor_pairs, action_items, priority, status, created_at
            FROM towS_strategy
            WHERE swot_id = %s
            ORDER BY strategy_type
            """,
            (swot_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def approve_tows(
    conn, strategy_id: str, approved_by: str,
    action_items: Optional[List[str]] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE towS_strategy
            SET status = 'approved', approved_by = %s, approved_at = NOW(),
                action_items = COALESCE(%s, action_items), updated_at = NOW()
            WHERE id = %s
            RETURNING id, strategy_type, status, approved_at
            """,
            (approved_by, json.dumps(action_items) if action_items else None, strategy_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"strategy {strategy_id} not found")
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Strategic Fit Score
# ──────────────────────────────────────────────

def compute_strategic_fit(conn, swot_id: str) -> Dict[str, Any]:
    """Compute strategic fit: how well internal strengths match external opportunities."""
    factors = list_factors(conn, swot_id)
    strengths = [f for f in factors if f["factor_type"] == "strength"]
    weaknesses = [f for f in factors if f["factor_type"] == "weakness"]
    opportunities = [f for f in factors if f["factor_type"] == "opportunity"]
    threats = [f for f in factors if f["factor_type"] == "threat"]

    # Category overlap between strengths and opportunities
    s_cats = {f["category"] for f in strengths}
    o_cats = {f["category"] for f in opportunities}
    overlap = s_cats & o_cats
    overlap_score = (len(overlap) / max(len(o_cats), 1)) * 100

    # Balance score: ratio of strengths to weaknesses
    balance = len(strengths) / max(len(weaknesses), 1)
    balance_score = min(100, balance * 25)

    # Coverage: do strengths cover the key opportunity categories?
    coverage = len(overlap) / max(len(o_cats), 1) * 100

    # Composite
    strategic_fit = (overlap_score * 0.4 + balance_score * 0.3 + coverage * 0.3)
    strategic_fit = round(min(100.0, strategic_fit), 1)

    return {
        "swot_id": swot_id,
        "strategic_fit_score": strategic_fit,
        "strength_count": len(strengths),
        "weakness_count": len(weaknesses),
        "opportunity_count": len(opportunities),
        "threat_count": len(threats),
        "category_overlap": list(overlap),
        "overlap_score": round(overlap_score, 1),
        "balance_score": round(balance_score, 1),
        "coverage_score": round(coverage, 1),
    }


# ──────────────────────────────────────────────
# Competitor SWOT
# ──────────────────────────────────────────────

def create_competitor(
    conn, location_id: str, competitor_name: str,
    competitor_type: Optional[str] = None,
    strengths: Optional[List[str]] = None,
    weaknesses: Optional[List[str]] = None,
    market_position: Optional[str] = None,
    competitive_threat_level: str = "moderate",
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO competitor_swot (
                location_id, competitor_name, competitor_type,
                strengths, weaknesses, market_position,
                competitive_threat_level, last_assessed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, competitor_name, competitive_threat_level
            """,
            (
                location_id, competitor_name, competitor_type,
                strengths or [], weaknesses or [], market_position,
                competitive_threat_level,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_competitors(conn, location_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, competitor_name, competitor_type, strengths, weaknesses,
                   market_position, competitive_threat_level, last_assessed
            FROM competitor_swot
            WHERE location_id = %s
            ORDER BY competitive_threat_level DESC, competitor_name
            """,
            (location_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def update_competitor(
    conn, competitor_id: str, **kwargs,
) -> Dict[str, Any]:
    allowed = {
        "competitor_name", "competitor_type", "strengths", "weaknesses",
        "market_position", "competitive_threat_level",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        raise ValueError("no valid fields to update")
    set_clauses = []
    params = []
    for k, v in updates.items():
        if k in ("strengths", "weaknesses"):
            set_clauses.append(f"{k} = %s")
            params.append(v)
        else:
            set_clauses.append(f"{k} = %s")
            params.append(v)
    set_clauses.append("updated_at = NOW()")
    set_clauses.append("last_assessed = NOW()")
    params.append(competitor_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"UPDATE competitor_swot SET {', '.join(set_clauses)} WHERE id = %s RETURNING id, competitor_name",
            params,
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"competitor {competitor_id} not found")
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Temporal Snapshots
# ──────────────────────────────────────────────

def snapshot_temporal(conn, swot_id: str, change_summary: Optional[str] = None) -> Dict[str, Any]:
    """Create a temporal snapshot of the current SWOT state with diff from previous."""
    factors = list_factors(conn, swot_id)
    snapshot = {
        "strengths": [f["description"] for f in factors if f["factor_type"] == "strength"],
        "weaknesses": [f["description"] for f in factors if f["factor_type"] == "weakness"],
        "opportunities": [f["description"] for f in factors if f["factor_type"] == "opportunity"],
        "threats": [f["description"] for f in factors if f["factor_type"] == "threat"],
        "factor_count": len(factors),
    }

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Get previous version
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_ver FROM swot_temporal WHERE swot_id = %s",
            (swot_id,),
        )
        max_ver = cur.fetchone()["max_ver"]
        next_version = max_ver + 1

        # Compute diffs if previous exists
        strengths_diff = weaknesses_diff = opportunities_diff = threats_diff = None
        if max_ver > 0:
            cur.execute(
                "SELECT snapshot FROM swot_temporal WHERE swot_id = %s AND version = %s",
                (swot_id, max_ver),
            )
            prev = cur.fetchone()
            if prev:
                prev_snap = prev["snapshot"]
                strengths_diff = _compute_diff(prev_snap.get("strengths", []), snapshot["strengths"])
                weaknesses_diff = _compute_diff(prev_snap.get("weaknesses", []), snapshot["weaknesses"])
                opportunities_diff = _compute_diff(prev_snap.get("opportunities", []), snapshot["opportunities"])
                threats_diff = _compute_diff(prev_snap.get("threats", []), snapshot["threats"])

        cur.execute(
            """
            INSERT INTO swot_temporal (
                swot_id, version, snapshot, strengths_diff, weaknesses_diff,
                opportunities_diff, threats_diff, change_summary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, swot_id, version, change_summary
            """,
            (
                swot_id, next_version, json.dumps(snapshot),
                json.dumps(strengths_diff) if strengths_diff else None,
                json.dumps(weaknesses_diff) if weaknesses_diff else None,
                json.dumps(opportunities_diff) if opportunities_diff else None,
                json.dumps(threats_diff) if threats_diff else None,
                change_summary,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def _compute_diff(old: List[str], new: List[str]) -> Dict[str, List[str]]:
    old_set, new_set = set(old), set(new)
    return {
        "added": list(new_set - old_set),
        "removed": list(old_set - new_set),
        "unchanged": list(old_set & new_set),
    }


def list_temporal(conn, swot_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, version, snapshot, change_summary, created_at
            FROM swot_temporal
            WHERE swot_id = %s
            ORDER BY version DESC
            """,
            (swot_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ──────────────────────────────────────────────
# Action Linkage
# ──────────────────────────────────────────────

def link_action(
    conn, swot_id: str, action_description: str,
    target_type: str = "manual", target_id: Optional[str] = None,
    factor_id: Optional[str] = None, strategy_id: Optional[str] = None,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO swot_action_link (
                swot_id, factor_id, strategy_id, target_type,
                target_id, action_description
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, action_description, status
            """,
            (swot_id, factor_id, strategy_id, target_type, target_id, action_description),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def list_actions(conn, swot_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    conditions = ["swot_id = %s"]
    params: list = [swot_id]
    if status:
        conditions.append("status = %s")
        params.append(status)
    where = " AND ".join(conditions)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT id, factor_id, strategy_id, target_type, target_id,
                   action_description, status, created_at
            FROM swot_action_link
            WHERE {where}
            ORDER BY created_at DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def update_action_status(conn, action_id: str, new_status: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "UPDATE swot_action_link SET status = %s WHERE id = %s RETURNING id, status",
            (new_status, action_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"action {action_id} not found")
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Enhanced Suggest
# ──────────────────────────────────────────────

def suggest_enhanced(conn, swot_id: str) -> Dict[str, Any]:
    """Auto-populate classified factors from existing platform data."""
    # Get the SWOT's location
    with conn.cursor() as cur:
        cur.execute(
            "SELECT location_id, organization_id FROM swot_analysis WHERE id = %s",
            (swot_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"swot {swot_id} not found")
        location_id = str(row[0]) if row[0] else None
        org_id = str(row[1]) if row[1] else None

    created = []
    # Strengths from CRISP low-risk dimensions
    try:
        with conn.cursor() as cur:
            filt = "l.id = %s" if location_id else "1=0"
            params = [location_id] if location_id else []
            cur.execute(
                f"""
                SELECT a.dimension, a.rating_band FROM crisp_risk_assessment a
                JOIN location l ON l.id = a.location_id
                WHERE {filt} AND a.status = 'active'
                ORDER BY a.assessed_at DESC LIMIT 10
                """,
                params,
            )
            for dim, band in cur.fetchall():
                if band in ("AAA", "AA", "A"):
                    cat = "financial" if "financial" in dim.lower() else "activities_processes"
                    f = create_factor(conn, swot_id, "strength", cat,
                                      f"{dim} risk rated {band} — low risk is a strength",
                                      source="crisp.risk")
                    created.append(str(f["id"]))
    except psycopg2.Error:
        pass

    # Threats from threatcasting
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT threat_name, severity_potential FROM threat
                WHERE is_active = TRUE
                ORDER BY severity_potential DESC LIMIT 10
                """,
            )
            for name, severity in cur.fetchall():
                cat = "future_trends"  # Default for threats
                f = create_factor(conn, swot_id, "threat", cat,
                                  f"{name} (severity: {severity})",
                                  source="threatcasting.threat")
                created.append(str(f["id"]))
    except psycopg2.Error:
        pass

    # Opportunities from desirable narratives
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title FROM threat_narrative
                WHERE narrative_type IN ('desirable', 'baseline')
                ORDER BY created_at DESC LIMIT 10
                """,
            )
            for (title,) in cur.fetchall():
                f = create_factor(conn, swot_id, "opportunity", "future_trends",
                                  title, source="threatcasting.narrative")
                created.append(str(f["id"]))
    except psycopg2.Error:
        pass

    # Weaknesses from high-risk CRISP dimensions
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.dimension, a.rating_band FROM crisp_risk_assessment a
                WHERE a.status = 'active'
                ORDER BY a.assessed_at DESC LIMIT 10
                """,
            )
            for dim, band in cur.fetchall():
                if band in ("C", "D"):
                    cat = "financial" if "financial" in dim.lower() else "activities_processes"
                    f = create_factor(conn, swot_id, "weakness", cat,
                                      f"{dim} risk rated {band} — high risk is a weakness",
                                      source="crisp.risk")
                    created.append(str(f["id"]))
    except psycopg2.Error:
        pass

    return {"factors_created": len(created), "factor_ids": created}
