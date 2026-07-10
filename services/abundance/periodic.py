"""Abundance Protocol: Periodic Validation and Relatedness Coefficients."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("abundance.periodic")


def create_periodic_validation(
    conn,
    estimate_id: str,
    period_start: str,
    period_end: str,
    validation_type: str = "realized_impact",
) -> str:
    """Create a periodic validation for realized impact assessment."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO periodic_validation (estimate_id, period_start, period_end, validation_type, status)
        VALUES (%s, %s, %s, %s, 'collecting_data')
        RETURNING id
    """, (estimate_id, period_start, period_end, validation_type))
    validation_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created periodic validation %s for estimate %s", validation_id[:8], estimate_id[:8])
    return validation_id


def record_realized_impact(
    conn,
    validation_id: str,
    category_id: str,
    measured_value: float,
    measurement_date: str,
    source_type: str = None,
    source_record_id: str = None,
    source_evidence: List[str] = None,
    notes: str = None,
) -> str:
    """Record an actual impact measurement."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO realized_impact_record
            (validation_id, category_id, measured_value, measurement_date,
             source_type, source_record_id, source_evidence, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        validation_id, category_id, measured_value, measurement_date,
        source_type, source_record_id, source_evidence or [], notes,
    ))
    record_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Recorded realized impact: category=%s, value=%.2f", category_id[:8], measured_value)
    return record_id


def compute_impact_deviation(conn, validation_id: str) -> List[Dict[str, Any]]:
    """Compare estimated vs realized impact for each category."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get the estimate
    cur.execute("""
        SELECT pv.estimate_id, eep.estimated_impact_score
        FROM periodic_validation pv
        JOIN impact_estimate_post eep ON eep.id = pv.estimate_id
        WHERE pv.id = %s
    """, (validation_id,))
    pv = cur.fetchone()
    if not pv:
        cur.close()
        return []

    estimate_id = str(pv["estimate_id"])

    # Get category assignments from the estimate
    cur.execute("""
        SELECT eca.category_id, eca.relative_impact_score, ec.category_name
        FROM estimate_category_assignment eca
        JOIN expertise_category ec ON ec.id = eca.category_id
        WHERE eca.estimate_id = %s
    """, (estimate_id,))
    categories = [dict(r) for r in cur.fetchall()]

    # Get realized impact per category
    cur.execute("""
        SELECT category_id, SUM(measured_value) AS total_realized
        FROM realized_impact_record
        WHERE validation_id = %s
        GROUP BY category_id
    """, (validation_id,))
    realized = {str(r["category_id"]): float(r["total_realized"] or 0) for r in cur.fetchall()}

    # Compute deviations
    results = []
    cur2 = conn.cursor()
    for cat in categories:
        cat_id = str(cat["category_id"])
        estimated = float(cat["relative_impact_score"])
        realized_val = realized.get(cat_id, 0)

        deviation = realized_val - estimated
        deviation_pct = (deviation / estimated * 100) if estimated > 0 else 0
        is_significant = abs(deviation_pct) > 20  # >20% deviation is significant

        cur2.execute("""
            INSERT INTO impact_deviation
                (validation_id, estimate_id, category_id, estimated_value, realized_value,
                 deviation_tonnes, deviation_pct, is_significant, review_required, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'computed')
            RETURNING id
        """, (
            validation_id, estimate_id, cat_id, estimated, realized_val,
            deviation, round(deviation_pct, 4), is_significant, is_significant,
        ))
        dev_id = str(cur2.fetchone()[0])

        results.append({
            "deviation_id": dev_id,
            "category": cat["category_name"],
            "estimated": estimated,
            "realized": realized_val,
            "deviation": round(deviation, 4),
            "deviation_pct": round(deviation_pct, 4),
            "is_significant": is_significant,
        })

    conn.commit()
    cur.close()

    return results


def update_relatedness_coefficients(conn) -> Dict[str, Any]:
    """Recompute category relatedness from validated project co-occurrence."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Find all categories that co-occur in validated estimates
    cur.execute("""
        SELECT
            eca1.category_id AS cat_a,
            eca2.category_id AS cat_b,
            COUNT(*) AS co_occurrence,
            AVG(eca1.relative_impact_score + eca2.relative_impact_score) AS avg_impact
        FROM estimate_category_assignment eca1
        JOIN estimate_category_assignment eca2
            ON eca1.estimate_id = eca2.estimate_id
            AND eca1.category_id < eca2.category_id
        JOIN impact_estimate_post eep ON eep.id = eca1.estimate_id
        WHERE eep.status IN ('validated', 'finalized')
        GROUP BY eca1.category_id, eca2.category_id
        HAVING COUNT(*) >= 2  -- Need at least 2 co-occurrences
    """)
    co_occurrences = [dict(r) for r in cur.fetchall()]

    # Compute relatedness coefficients
    results = []
    cur2 = conn.cursor()
    for co in co_occurrences:
        cat_a = str(co["cat_a"])
        cat_b = str(co["cat_b"])
        count = int(co["co_occurrence"])
        avg_impact = float(co["avg_impact"] or 0)

        # Relatedness = min(1.0, co_occurrence_count / 10) * impact_weight
        coefficient = min(1.0, count / 10.0) * min(1.0, avg_impact / 10.0)

        cur2.execute("""
            INSERT INTO relatedness_coefficient
                (category_a_id, category_b_id, coefficient, co_occurrence_count,
                 avg_impact_weight, computed_from_projects, last_computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (category_a_id, category_b_id) DO UPDATE SET
                coefficient = EXCLUDED.coefficient,
                co_occurrence_count = EXCLUDED.co_occurrence_count,
                avg_impact_weight = EXCLUDED.avg_impact_weight,
                computed_from_projects = EXCLUDED.computed_from_projects,
                last_computed_at = NOW(),
                updated_at = NOW()
        """, (cat_a, cat_b, round(coefficient, 4), count, round(avg_impact, 4), count))

        results.append({
            "category_a": cat_a,
            "category_b": cat_b,
            "coefficient": round(coefficient, 4),
            "co_occurrence_count": count,
        })

    conn.commit()
    cur.close()

    logger.info("Updated %d relatedness coefficients", len(results))
    return {"updated": len(results), "coefficients": results}
