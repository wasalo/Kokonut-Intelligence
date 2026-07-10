"""Abundance Protocol: Impact Estimate Posts.

Manages the creation, sorting, and category grafting for impact estimates.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.estimates")


def compute_validation_fee(impact_score: float, effort_level: str, expertise_required: float) -> float:
    """Compute validation fee based on impact, effort, and expertise.

    Higher impact and expertise = higher fee (proportional scrutiny).
    """
    effort_multiplier = {"low": 0.5, "medium": 1.0, "high": 1.5, "very_high": 2.0}.get(effort_level, 1.0)
    base_fee = impact_score * 0.01  # 1% of impact score
    expertise_factor = max(1.0, expertise_required / 1000)
    return round(base_fee * effort_multiplier * expertise_factor, 4)


def create_estimate_post(
    conn,
    project_hash: str,
    estimated_impact_score: float,
    credibility_score: float = None,
    categories: List[Dict[str, Any]] = None,
    urgency: str = "normal",
    effort_level: str = "medium",
    estimator_id: str = None,
    location_id: str = None,
    comments: str = None,
    supporting_sources: List[str] = None,
) -> str:
    """Create a new impact estimate post and add to waiting list."""
    # Compute expertise required from categories
    total_expertise = 0.0
    if categories:
        for cat in categories:
            total_expertise += cat.get("relative_impact_score", 0)

    validation_fee = compute_validation_fee(estimated_impact_score, effort_level, total_expertise)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO impact_estimate_post (
            project_hash, estimator_id, location_id,
            estimated_impact_score, credibility_score,
            urgency, effort_level, validation_fee,
            comments, supporting_sources, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'submitted')
        RETURNING id
    """, (
        project_hash, estimator_id, location_id,
        estimated_impact_score, credibility_score,
        urgency, effort_level, validation_fee,
        comments, supporting_sources or [],
    ))
    estimate_id = str(cur.fetchone()[0])

    # Add category assignments
    if categories:
        for cat in categories:
            cat_id = cat.get("category_id")
            if cat_id:
                cur.execute("""
                    INSERT INTO estimate_category_assignment
                        (estimate_id, category_id, relative_impact_score, justification)
                    VALUES (%s, %s, %s, %s)
                """, (estimate_id, cat_id, cat.get("relative_impact_score", 0), cat.get("justification")))

    # Add to waiting list
    cur.execute("""
        INSERT INTO waiting_list_entry (estimate_id, position, sort_score, credibility_component, impact_component, expertise_component)
        VALUES (%s, (SELECT COALESCE(MAX(position), 0) + 1 FROM waiting_list_entry), %s, %s, %s, %s)
    """, (
        estimate_id,
        estimated_impact_score * (credibility_score or 0.5) * max(1, total_expertise / 100),
        credibility_score or 0.5,
        estimated_impact_score,
        total_expertise,
    ))

    conn.commit()
    cur.close()

    logger.info("Created estimate %s for project %s (impact=%.1f, fee=%.2f)", estimate_id[:8], project_hash[:10], estimated_impact_score, validation_fee)
    return estimate_id


def sort_waiting_list(conn) -> List[Dict[str, Any]]:
    """Sort waiting list by credibility × impact × expertise (highest first)."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT wle.*, eep.estimated_impact_score, eep.credibility_score, eep.status AS estimate_status
        FROM waiting_list_entry wle
        JOIN impact_estimate_post eep ON eep.id = wle.estimate_id
        WHERE wle.status = 'queued'
        ORDER BY wle.sort_score DESC
    """)
    entries = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Re-assign positions
    cur = conn.cursor()
    for i, entry in enumerate(entries):
        cur.execute("UPDATE waiting_list_entry SET position = %s WHERE id = %s", (i + 1, str(entry["id"])))
    conn.commit()
    cur.close()

    return entries


def graft_category(
    conn,
    new_category_name: str,
    related_category_ids: List[str],
    estimated_coefficients: Dict[str, float],
    initiated_by: str = None,
    description: str = None,
) -> str:
    """Create a new expertise category with validator-assigned relatedness."""
    cur = conn.cursor()

    # Create the new category
    cur.execute("""
        INSERT INTO expertise_category (category_name, description, created_by)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (new_category_name, description, initiated_by))
    new_cat_id = str(cur.fetchone()[0])

    # Create graft record
    cur.execute("""
        INSERT INTO category_graft
            (new_category_id, graft_initiated_by, related_category_ids, estimated_coefficients, status)
        VALUES (%s, %s, %s, %s, 'proposed')
        RETURNING id
    """, (new_cat_id, initiated_by, related_category_ids, json.dumps(estimated_coefficients)))
    graft_id = str(cur.fetchone()[0])

    # Create initial relatedness entries
    for related_id in related_category_ids:
        coeff = estimated_coefficients.get(related_id, 0.5)
        cur.execute("""
            INSERT INTO category_relatedness (category_a_id, category_b_id, relatedness_coefficient)
            VALUES (%s, %s, %s)
            ON CONFLICT (category_a_id, category_b_id) DO UPDATE SET
                relatedness_coefficient = EXCLUDED.relatedness_coefficient
        """, (new_cat_id, related_id, coeff))

    conn.commit()
    cur.close()

    logger.info("Grafted category '%s' with %d related categories", new_category_name, len(related_category_ids))
    return new_cat_id
