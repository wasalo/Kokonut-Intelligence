"""Emergency response analytics: response time, impact summary."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_emergency_response_time(conn, location_id: str) -> dict[str, Any]:
    """Compute emergency response time metrics for a location.

    Returns average days from detection to resolution, deadline compliance, and per-incident breakdown.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, incident_type, severity, detection_date, recovery_date,
               response_deadline, affected_area_pct, financial_impact_usd, status
        FROM emergency_incident
        WHERE location_id = %s
        ORDER BY detection_date DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    incidents = []
    resolved_count = 0
    total_response_days = 0
    met_deadline_count = 0
    deadline_compliant_count = 0

    for row in rows:
        response_days = None
        met_deadline = None
        if row[3] and row[4]:  # detection_date and recovery_date
            response_days = (row[4] - row[3]).days
            total_response_days += response_days
            resolved_count += 1
        if row[5] and row[4]:  # response_deadline and recovery_date
            met_deadline = row[4] <= row[5]
            deadline_compliant_count += 1
            if met_deadline:
                met_deadline_count += 1

        incidents.append({
            "id": str(row[0]),
            "incident_type": row[1],
            "severity": row[2],
            "detection_date": str(row[3]) if row[3] else None,
            "recovery_date": str(row[4]) if row[4] else None,
            "response_deadline": str(row[5]) if row[5] else None,
            "response_time_days": response_days,
            "met_deadline": met_deadline,
            "affected_area_pct": float(row[6]) if row[6] else 0,
            "financial_impact_usd": float(row[7]) if row[7] else 0,
            "status": row[8],
        })

    avg_response_days = (total_response_days / resolved_count) if resolved_count > 0 else None
    deadline_compliance_pct = (met_deadline_count / deadline_compliant_count * 100) if deadline_compliant_count > 0 else None

    result = {
        "location_id": location_id,
        "total_incidents": len(incidents),
        "resolved_incidents": resolved_count,
        "avg_response_time_days": round(avg_response_days, 1) if avg_response_days is not None else None,
        "deadline_compliance_pct": round(deadline_compliance_pct, 1) if deadline_compliance_pct is not None else None,
        "met_deadline_count": met_deadline_count,
        "incidents": incidents,
    }

    logger.info("Emergency response time for %s: avg %.1f days", location_id, avg_response_days or 0)
    return result


def compute_emergency_impact_summary(conn, location_id: str) -> dict[str, Any]:
    """Compute emergency impact summary: incidents by type/severity, total financial impact, avg affected area."""
    cur = conn.cursor()

    # By type
    cur.execute(
        """
        SELECT incident_type, COUNT(*) AS count,
               AVG(affected_area_pct) AS avg_affected_area,
               SUM(financial_impact_usd) AS total_financial_impact
        FROM emergency_incident
        WHERE location_id = %s
        GROUP BY incident_type
        ORDER BY count DESC
        """,
        (location_id,),
    )
    by_type = [
        {
            "incident_type": r[0],
            "count": r[1],
            "avg_affected_area_pct": round(float(r[2]), 1) if r[2] else 0,
            "total_financial_impact_usd": round(float(r[3]), 2) if r[3] else 0,
        }
        for r in cur.fetchall()
    ]

    # By severity
    cur.execute(
        """
        SELECT severity, COUNT(*) AS count,
               AVG(affected_area_pct) AS avg_affected_area,
               SUM(financial_impact_usd) AS total_financial_impact
        FROM emergency_incident
        WHERE location_id = %s
        GROUP BY severity
        ORDER BY count DESC
        """,
        (location_id,),
    )
    by_severity = [
        {
            "severity": r[0],
            "count": r[1],
            "avg_affected_area_pct": round(float(r[2]), 1) if r[2] else 0,
            "total_financial_impact_usd": round(float(r[3]), 2) if r[3] else 0,
        }
        for r in cur.fetchall()
    ]

    # Totals
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(financial_impact_usd) AS total_impact,
               AVG(affected_area_pct) AS avg_area,
               COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
               COUNT(*) FILTER (WHERE status = 'escalated') AS escalated
        FROM emergency_incident
        WHERE location_id = %s
        """,
        (location_id,),
    )
    totals = cur.fetchone()
    cur.close()

    result = {
        "location_id": location_id,
        "total_incidents": totals[0] or 0,
        "total_financial_impact_usd": round(float(totals[1]), 2) if totals[1] else 0,
        "avg_affected_area_pct": round(float(totals[2]), 1) if totals[2] else 0,
        "resolved_count": totals[3] or 0,
        "escalated_count": totals[4] or 0,
        "by_type": by_type,
        "by_severity": by_severity,
    }

    logger.info("Emergency impact for %s: %d incidents, $%.2f total impact", location_id, result["total_incidents"], result["total_financial_impact_usd"])
    return result
