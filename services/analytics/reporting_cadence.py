"""Reporting cadence management with automated report generation."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.reporting_cadence")


def create_cadence(
    conn,
    location_id: str,
    obligation_key: str,
    obligation_name: str,
    report_type: str,
    description: str,
    frequency: str,
    start_date: str,
    required_sections: List[str] = None,
    required_data_sources: List[str] = None,
    recipient_role: str = None,
    delivery_format: str = None,
    auto_generate_report: bool = False,
    report_generator_command: str = None,
    **kwargs,
) -> str:
    """Define a reporting obligation."""
    from datetime import date as date_type

    freq_days = {
        "weekly": 7, "monthly": 30, "quarterly": 90,
        "semi_annual": 180, "annual": 365,
    }
    grace = 7
    next_due = datetime.strptime(start_date, "%Y-%m-%d").date() + timedelta(days=freq_days.get(frequency, 30))

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reporting_cadence (
            location_id, obligation_key, obligation_name, report_type, description,
            required_sections, required_data_sources, frequency,
            start_date, next_due_date, grace_period_days,
            recipient_role, delivery_format, auto_generate_report, report_generator_command, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
        ON CONFLICT (location_id, obligation_key) DO UPDATE SET
            description = EXCLUDED.description, frequency = EXCLUDED.frequency, updated_at = NOW()
        RETURNING id
    """, (
        location_id, obligation_key, obligation_name, report_type, description,
        required_sections or [], required_data_sources or [], frequency,
        start_date, next_due, grace,
        recipient_role, delivery_format, auto_generate_report, report_generator_command,
    ))
    cadence_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created reporting cadence: %s (type=%s, freq=%s)", obligation_key, report_type, frequency)
    return cadence_id


def check_overdue(conn, location_id: str = None) -> List[Dict[str, Any]]:
    """Find reporting obligations that are overdue."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    today = datetime.now(timezone.utc).date()

    query = """
        SELECT rc.*, l.name AS location_name
        FROM reporting_cadence rc
        JOIN location l ON l.id = rc.location_id
        WHERE rc.status = 'published'
        AND rc.next_due_date IS NOT NULL
        AND rc.next_due_date < %s
    """
    params = [today]

    if location_id:
        query += " AND rc.location_id = %s"
        params.append(location_id)

    query += " ORDER BY rc.next_due_date ASC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Update compliance status
    cur2 = conn.cursor()
    for row in rows:
        days_overdue = (today - row["next_due_date"]).days
        grace = row.get("grace_period_days", 7) or 7
        if days_overdue > grace:
            status = "overdue"
        else:
            status = "at_risk"
        cur2.execute("""
            UPDATE reporting_cadence SET compliance_status = %s, overdue_count = overdue_count + 1
            WHERE id = %s
        """, (status, str(row["id"])))
    conn.commit()
    cur2.close()

    return rows


def mark_completed(
    conn,
    cadence_id: str,
    report_snapshot_id: str = None,
) -> Dict[str, Any]:
    """Mark a reporting obligation as completed and schedule next."""
    from datetime import date as date_type

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM reporting_cadence WHERE id = %s", (cadence_id,))
    cadence = cur.fetchone()
    if not cur.fetchall():
        cur.close()
        return {"status": "error", "message": "Cadence not found"}

    cadence = dict(cadence)
    today = datetime.now(timezone.utc).date()

    # Compute next due date
    freq_days = {
        "weekly": 7, "monthly": 30, "quarterly": 90,
        "semi_annual": 180, "annual": 365,
    }
    days = freq_days.get(cadence.get("frequency", "monthly"), 30)
    next_due = today + timedelta(days=days)

    cur2 = conn.cursor()
    cur2.execute("""
        UPDATE reporting_cadence SET
            last_completed_date = %s, next_due_date = %s,
            compliance_status = 'current', overdue_count = 0,
            updated_at = NOW()
        WHERE id = %s
    """, (today, next_due, cadence_id))
    conn.commit()
    cur2.close()
    cur.close()

    return {
        "cadence_id": cadence_id,
        "completed_date": str(today),
        "next_due_date": str(next_due),
        "compliance_status": "current",
    }


def escalate_overdue(conn) -> List[Dict[str, Any]]:
    """Escalate overdue reporting obligations."""
    today = datetime.now(timezone.utc).date()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT rc.*, l.name AS location_name
        FROM reporting_cadence rc
        JOIN location l ON l.id = rc.location_id
        WHERE rc.compliance_status = 'overdue'
        AND rc.escalation_role IS NOT NULL
        AND rc.escalation_after_days IS NOT NULL
        AND rc.next_due_date + rc.escalation_after_days <= %s
    """, (today,))
    overdue = [dict(r) for r in cur.fetchall()]
    cur.close()

    escalated = []
    for row in overdue:
        escalated.append({
            "cadence_id": str(row["id"]),
            "obligation_name": row["obligation_name"],
            "location_name": row["location_name"],
            "escalation_role": row["escalation_role"],
            "days_overdue": (today - row["next_due_date"]).days,
        })

    return escalated


def trigger_auto_generation(conn, cadence_id: str) -> Dict[str, Any]:
    """Trigger automated report generation for a cadence."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM reporting_cadence WHERE id = %s", (cadence_id,))
    cadence = cur.fetchone()
    if not cadence:
        cur.close()
        return {"status": "error", "message": "Cadence not found"}

    cadence = dict(cadence)

    if not cadence.get("auto_generate_report"):
        cur.close()
        return {"status": "skipped", "message": "Auto-generation not enabled"}

    command = cadence.get("report_generator_command")
    if not command:
        cur.close()
        return {"status": "error", "message": "No report generator command configured"}

    # Execute report generator
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=300,
        )
        success = result.returncode == 0

        if success:
            # Mark completed
            mark_completed(conn, cadence_id)

        cur.close()
        return {
            "status": "success" if success else "failed",
            "output": result.stdout[-500:] if result.stdout else "",
            "error": result.stderr[-500:] if result.stderr and not success else None,
        }
    except Exception as e:
        cur.close()
        return {"status": "error", "message": str(e)}


def get_cadence_summary(conn, location_id: str) -> Dict[str, Any]:
    """Get overview of all reporting obligations for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE compliance_status = 'current') AS current,
            COUNT(*) FILTER (WHERE compliance_status = 'overdue') AS overdue,
            COUNT(*) FILTER (WHERE compliance_status = 'at_risk') AS at_risk,
            COUNT(*) FILTER (WHERE compliance_status = 'suspended') AS suspended,
            COUNT(*) FILTER (WHERE auto_generate_report = TRUE) AS auto_generated
        FROM reporting_cadence
        WHERE location_id = %s AND status = 'published'
    """, (location_id,))
    summary = dict(cur.fetchone() or {})
    cur.close()
    return summary
