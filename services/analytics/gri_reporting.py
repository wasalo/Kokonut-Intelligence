"""GRI Reporting analytics: compliance scoring, materiality matrix."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_gri_compliance_score(conn, location_id: str) -> dict[str, Any]:
    """Compute GRI compliance score based on indicator coverage."""
    cur = conn.cursor()

    # Get all active GRI indicators
    cur.execute(
        """
        SELECT gri_code, gri_standard, indicator_name, platform_table, platform_field, data_type
        FROM gri_indicator
        WHERE status = 'active'
        """,
    )
    indicators = cur.fetchall()

    total = len(indicators)
    covered = 0
    coverage_details = []

    for ind in indicators:
        gri_code = ind[0]
        gri_standard = ind[1]
        indicator_name = ind[2]
        platform_table = ind[3]
        platform_field = ind[4]
        data_type = ind[5]

        # Check if data exists for this indicator
        has_data = False
        if platform_table:
            try:
                cur.execute(
                    f"SELECT COUNT(*) FROM {platform_table} WHERE location_id = %s LIMIT 1",
                    (location_id,),
                )
                count = cur.fetchone()[0]
                has_data = count > 0
            except Exception:
                has_data = False

        if has_data:
            covered += 1

        coverage_details.append({
            "gri_code": gri_code,
            "gri_standard": gri_standard,
            "indicator_name": indicator_name,
            "platform_table": platform_table,
            "has_data": has_data,
        })

    cur.close()

    compliance_pct = (covered / total * 100) if total > 0 else 0

    result = {
        "location_id": location_id,
        "total_indicators": total,
        "covered_indicators": covered,
        "compliance_pct": round(compliance_pct, 1),
        "indicators": coverage_details,
    }

    logger.info("GRI compliance for %s: %d/%d (%.1f%%)", location_id, covered, total, compliance_pct)
    return result


def compute_materiality_matrix(conn, location_id: str) -> dict[str, Any]:
    """Compute materiality matrix from stakeholder assessments."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT stakeholder_group, material_topic, topic_category,
               importance_to_stakeholder, importance_to_business, priority_level, notes
        FROM materiality_assessment
        WHERE location_id = %s AND status = 'published'
        ORDER BY importance_to_stakeholder DESC, importance_to_business DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    matrix = []
    for row in rows:
        matrix.append({
            "stakeholder_group": row[0],
            "material_topic": row[1],
            "topic_category": row[2],
            "importance_to_stakeholder": row[3],
            "importance_to_business": row[4],
            "priority_level": row[5],
            "notes": row[6],
        })

    # Summary by priority
    high_count = sum(1 for m in matrix if m["priority_level"] == "high")
    medium_count = sum(1 for m in matrix if m["priority_level"] == "medium")
    low_count = sum(1 for m in matrix if m["priority_level"] == "low")

    # Summary by category
    categories: dict[str, list] = {}
    for m in matrix:
        categories.setdefault(m["topic_category"], []).append(m)

    result = {
        "location_id": location_id,
        "total_topics": len(matrix),
        "high_priority": high_count,
        "medium_priority": medium_count,
        "low_priority": low_count,
        "by_category": {
            cat: {
                "count": len(topics),
                "avg_stakeholder_importance": round(sum(t["importance_to_stakeholder"] for t in topics) / len(topics), 1),
                "avg_business_importance": round(sum(t["importance_to_business"] for t in topics) / len(topics), 1),
            }
            for cat, topics in categories.items()
        },
        "matrix": matrix,
    }

    logger.info("Materiality matrix for %s: %d topics (%d high, %d medium, %d low)",
                location_id, len(matrix), high_count, medium_count, low_count)
    return result
