"""Organic certification analytics: readiness score, transition progress, input compliance, buffer adequacy, harvest segregation, record completeness, prohibited substance clearance."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_organic_readiness_score(conn, location_id: str) -> dict[str, Any]:
    """Compute composite organic certification readiness score (0-100).

    Aggregates 8 sub-scores: transition progress, soil health, input compliance,
    pest management, biodiversity, buffer zones, records, training, harvest segregation.
    """
    cur = conn.cursor()

    # Latest readiness assessment
    cur.execute(
        """
        SELECT overall_score, transition_progress_pct, soil_health_score,
               input_compliance_pct, pest_management_score, biodiversity_score,
               buffer_zone_score, record_completeness_pct, training_completion_pct,
               harvest_segregation_score, barriers, recommendations, assessment_date, standard
        FROM organic_readiness_assessment
        WHERE location_id = %s
        ORDER BY assessment_date DESC LIMIT 1
        """,
        (location_id,),
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        return {"location_id": location_id, "status": "no_assessment", "overall_score": 0}

    result = {
        "location_id": location_id,
        "status": "assessed",
        "assessment_date": str(row[12]) if row[12] else None,
        "standard": row[13],
        "overall_score": float(row[0]) if row[0] else 0,
        "transition_progress_pct": float(row[1]) if row[1] else 0,
        "soil_health_score": float(row[2]) if row[2] else 0,
        "input_compliance_pct": float(row[3]) if row[3] else 0,
        "pest_management_score": float(row[4]) if row[4] else 0,
        "biodiversity_score": float(row[5]) if row[5] else 0,
        "buffer_zone_score": float(row[6]) if row[6] else 0,
        "record_completeness_pct": float(row[7]) if row[7] else 0,
        "training_completion_pct": float(row[8]) if row[8] else 0,
        "harvest_segregation_score": float(row[9]) if row[9] else 0,
        "barriers": row[10] or [],
        "recommendations": row[11] or [],
    }

    cur.close()
    logger.info("Organic readiness score for %s: %.1f", location_id, result["overall_score"])
    return result


def compute_transition_progress(conn, location_id: str) -> dict[str, Any]:
    """Compute organic transition progress for all active transitions at a location.

    Returns years elapsed, % complete, milestones, and barriers.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, standard, transition_start_date, expected_certification_date,
               current_year, total_years_required, status,
               prohibited_substance_free_date, buffer_zone_established_date,
               record_keeping_ready_date, training_completed_date,
               organic_management_plan_date, readiness_score, barriers
        FROM organic_transition_plan
        WHERE location_id = %s
        ORDER BY transition_start_date DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    transitions = []
    for row in rows:
        progress = (row[4] / row[5] * 100) if row[5] and row[5] > 0 else 0
        transitions.append({
            "id": str(row[0]),
            "standard": row[1],
            "transition_start_date": str(row[2]) if row[2] else None,
            "expected_certification_date": str(row[3]) if row[3] else None,
            "current_year": row[4],
            "total_years_required": row[5],
            "status": row[6],
            "progress_pct": round(progress, 1),
            "milestones": {
                "prohibited_substance_free": str(row[7]) if row[7] else None,
                "buffer_zone_established": str(row[8]) if row[8] else None,
                "record_keeping_ready": str(row[9]) if row[9] else None,
                "training_completed": str(row[10]) if row[10] else None,
                "management_plan_submitted": str(row[11]) if row[11] else None,
            },
            "readiness_score": float(row[12]) if row[12] else 0,
            "barriers": row[13] or [],
        })

    result = {
        "location_id": location_id,
        "transition_count": len(transitions),
        "active_transitions": [t for t in transitions if t["status"] == "active"],
        "all_transitions": transitions,
    }

    logger.info("Transition progress for %s: %d transitions", location_id, len(transitions))
    return result


def compute_input_compliance_pct(conn, location_id: str, months: int = 12) -> dict[str, Any]:
    """Compute percentage of inputs that are organic-allowed over the last N months.

    An input is 'compliant' if organic_certified = TRUE AND is_prohibited = FALSE.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_inputs,
            COUNT(*) FILTER (WHERE organic_certified = TRUE AND is_prohibited = FALSE) AS compliant_inputs,
            COUNT(*) FILTER (WHERE organic_certified = TRUE) AS organic_certified_inputs,
            COUNT(*) FILTER (WHERE is_prohibited = TRUE) AS prohibited_inputs,
            COUNT(*) FILTER (WHERE input_source = 'on_farm') AS on_farm_inputs,
            COUNT(DISTINCT input_category) AS unique_categories
        FROM organic_input_audit
        WHERE location_id = %s
          AND application_date >= CURRENT_DATE - INTERVAL '%s months'
        """,
        (location_id, months),
    )
    row = cur.fetchone()
    cur.close()

    total = row[0] or 0
    compliant = row[1] or 0
    compliance_pct = (compliant / total * 100) if total > 0 else 0

    result = {
        "location_id": location_id,
        "period_months": months,
        "total_inputs": total,
        "compliant_inputs": compliant,
        "organic_certified_inputs": row[2] or 0,
        "prohibited_inputs": row[3] or 0,
        "on_farm_inputs": row[4] or 0,
        "unique_categories": row[5] or 0,
        "compliance_pct": round(compliance_pct, 1),
        "status": "compliant" if compliance_pct >= 95 and (row[3] or 0) == 0 else "non_compliant",
    }

    logger.info("Input compliance for %s: %.1f%%", location_id, compliance_pct)
    return result


def compute_buffer_adequacy(conn, location_id: str) -> dict[str, Any]:
    """Assess buffer zone adequacy per plot.

    EU standard requires minimum 3m buffer. IFOAM requires site-specific assessment.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, buffer_name, buffer_type, width_m, length_m, area_m2,
               adjacent_use, condition_status, establishment_date, last_inspection_date
        FROM buffer_zone
        WHERE location_id = %s
        ORDER BY width_m ASC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    buffers = []
    total_area = 0
    adequate_count = 0
    for row in rows:
        area = float(row[5]) if row[5] else 0
        total_area += area
        adequate = row[7] == "adequate" and float(row[3]) >= 3.0
        if adequate:
            adequate_count += 1
        buffers.append({
            "id": str(row[0]),
            "buffer_name": row[1],
            "buffer_type": row[2],
            "width_m": float(row[3]),
            "length_m": float(row[4]) if row[4] else None,
            "area_m2": area,
            "adjacent_use": row[6],
            "condition_status": row[7],
            "establishment_date": str(row[8]) if row[8] else None,
            "last_inspection_date": str(row[9]) if row[9] else None,
            "meets_minimum": float(row[3]) >= 3.0,
            "adequate": adequate,
        })

    total_buffers = len(buffers)
    adequacy_pct = (adequate_count / total_buffers * 100) if total_buffers > 0 else 0

    result = {
        "location_id": location_id,
        "total_buffers": total_buffers,
        "adequate_buffers": adequate_count,
        "total_buffer_area_m2": round(total_area, 2),
        "adequacy_pct": round(adequacy_pct, 1),
        "buffers": buffers,
        "status": "adequate" if adequacy_pct >= 80 else "needs_improvement",
    }

    logger.info("Buffer adequacy for %s: %.1f%%", location_id, adequacy_pct)
    return result


def compute_harvest_segregation_score(conn, location_id: str) -> dict[str, Any]:
    """Compute harvest segregation score — % of harvests with organic segregation maintained."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_harvests,
            COUNT(*) FILTER (WHERE organic_segregated = TRUE) AS segregated,
            COUNT(*) FILTER (WHERE equipment_cleaned = TRUE) AS cleaned,
            COUNT(*) FILTER (WHERE temperature_controlled = TRUE) AS temp_controlled,
            COUNT(*) FILTER (WHERE buyer_requirements_met = TRUE) AS buyer_met,
            COUNT(*) FILTER (WHERE contamination_risk = 'low') AS low_risk,
            COUNT(*) FILTER (WHERE organic_lot_number IS NOT NULL AND organic_lot_number != '') AS lot_tracked
        FROM harvest_handling_record
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    total = row[0] or 0
    segregated = row[1] or 0
    segregation_pct = (segregated / total * 100) if total > 0 else 0

    # Composite score: segregation (40%), equipment cleaning (20%), lot tracking (20%), low risk (20%)
    cleaning_pct = (row[2] or 0) / total * 100 if total > 0 else 0
    lot_pct = (row[6] or 0) / total * 100 if total > 0 else 0
    low_risk_pct = (row[5] or 0) / total * 100 if total > 0 else 0
    composite = segregation_pct * 0.4 + cleaning_pct * 0.2 + lot_pct * 0.2 + low_risk_pct * 0.2

    result = {
        "location_id": location_id,
        "total_harvests": total,
        "segregated_harvests": segregated,
        "segregation_pct": round(segregation_pct, 1),
        "equipment_cleaned_pct": round(cleaning_pct, 1),
        "temperature_controlled_count": row[3] or 0,
        "buyer_requirements_met_count": row[4] or 0,
        "low_risk_count": row[5] or 0,
        "lot_tracked_count": row[6] or 0,
        "composite_score": round(composite, 1),
        "status": "compliant" if composite >= 90 else "needs_improvement",
    }

    logger.info("Harvest segregation for %s: %.1f%%", location_id, segregation_pct)
    return result


def compute_record_completeness(conn, location_id: str) -> dict[str, Any]:
    """Compute record completeness across all organic certification tables.

    Checks presence of required records: transition plan, certification record,
    buffer zones, input audits, harvest handling, compliance checklist, readiness assessment.
    """
    cur = conn.cursor()

    checks = {
        "transition_plan": ("SELECT COUNT(*) FROM organic_transition_plan WHERE location_id = %s", "active"),
        "certification_record": ("SELECT COUNT(*) FROM organic_certification_record WHERE location_id = %s", "preparing"),
        "buffer_zones": ("SELECT COUNT(*) FROM buffer_zone WHERE location_id = %s", "adequate"),
        "input_audits": ("SELECT COUNT(*) FROM organic_input_audit WHERE location_id = %s", "organic"),
        "harvest_handling": ("SELECT COUNT(*) FROM harvest_handling_record WHERE location_id = %s", "segregated"),
        "compliance_checklist": ("SELECT COUNT(*) FROM organic_compliance_checklist WHERE location_id = %s", "pass"),
        "readiness_assessment": ("SELECT COUNT(*) FROM organic_readiness_assessment WHERE location_id = %s", "assessed"),
        "prohibited_substances": ("SELECT COUNT(*) FROM prohibited_substance_record WHERE location_id = %s", "cleared"),
    }

    results = {}
    populated = 0
    for name, (sql, _) in checks.items():
        cur.execute(sql, (location_id,))
        count = cur.fetchone()[0]
        results[name] = count
        if count > 0:
            populated += 1

    cur.close()

    completeness_pct = (populated / len(checks) * 100) if checks else 0

    result = {
        "location_id": location_id,
        "record_counts": results,
        "populated_tables": populated,
        "total_required_tables": len(checks),
        "completeness_pct": round(completeness_pct, 1),
        "missing": [name for name, count in results.items() if count == 0],
        "status": "complete" if completeness_pct >= 80 else "incomplete",
    }

    logger.info("Record completeness for %s: %.1f%%", location_id, completeness_pct)
    return result


def compute_prohibited_substance_clearance(conn, location_id: str) -> dict[str, Any]:
    """Check if all prohibited substances have been cleared (withdrawal period completed)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE compliance_status = 'cleared') AS cleared,
            COUNT(*) FILTER (WHERE compliance_status = 'violation') AS violations,
            COUNT(*) FILTER (WHERE compliance_status = 'pending_remediation') AS pending,
            COUNT(*) FILTER (WHERE compliance_status = 'under_review') AS under_review,
            MAX(withdrawal_end_date) FILTER (WHERE compliance_status != 'cleared') AS latest_pending_clearance
        FROM prohibited_substance_record
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    total = row[0] or 0
    cleared = row[1] or 0
    violations = row[2] or 0
    pending = row[3] or 0
    under_review = row[4] or 0
    clearance_pct = (cleared / total * 100) if total > 0 else 100  # No records = clean

    result = {
        "location_id": location_id,
        "total_substances": total,
        "cleared": cleared,
        "violations": violations,
        "pending_remediation": pending,
        "under_review": under_review,
        "clearance_pct": round(clearance_pct, 1),
        "latest_pending_clearance": str(row[5]) if row[5] else None,
        "all_clear": violations == 0 and pending == 0 and under_review == 0,
        "status": "all_clear" if violations == 0 and pending == 0 else "violations_exist",
    }

    logger.info("Prohibited substance clearance for %s: %.1f%%", location_id, clearance_pct)
    return result
