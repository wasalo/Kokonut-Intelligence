"""Measurement schedule: tracking cadence and due dates for forest monitoring."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)

# Frequency to interval mapping
FREQUENCY_INTERVALS = {
    "monthly": timedelta(days=30),
    "quarterly": timedelta(days=91),
    "semi_annual": timedelta(days=182),
    "annual": timedelta(days=365),
}


def compute_next_due_date(last_date: date, frequency: str) -> date:
    """Compute next measurement due date based on last measurement and frequency."""
    interval = FREQUENCY_INTERVALS.get(frequency, timedelta(days=182))
    return last_date + interval


def check_overdue_zones(conn, location_id: str | None = None) -> dict[str, Any]:
    """Find zones with overdue measurements."""
    cur = conn.cursor()

    if location_id:
        cur.execute(
            """
            SELECT zone_id, location_id, location_name, zone_name, zone_type,
                   measurement_frequency, last_measurement_date, next_measurement_due,
                   schedule_status, days_overdue, tree_count
            FROM v_measurement_schedule
            WHERE location_id = %s AND schedule_status = 'overdue'
            ORDER BY days_overdue DESC
            """,
            (location_id,),
        )
    else:
        cur.execute(
            """
            SELECT zone_id, location_id, location_name, zone_name, zone_type,
                   measurement_frequency, last_measurement_date, next_measurement_due,
                   schedule_status, days_overdue, tree_count
            FROM v_measurement_schedule
            WHERE schedule_status = 'overdue'
            ORDER BY days_overdue DESC
            """,
        )

    rows = cur.fetchall()
    cur.close()

    overdue = [
        {
            "zone_id": str(r[0]),
            "location_id": str(r[1]),
            "location_name": r[2],
            "zone_name": r[3],
            "zone_type": r[4],
            "measurement_frequency": r[5],
            "last_measurement_date": str(r[6]) if r[6] else None,
            "next_measurement_due": str(r[7]) if r[7] else None,
            "schedule_status": r[8],
            "days_overdue": r[9],
            "tree_count": r[10],
        }
        for r in rows
    ]

    logger.info("Found %d overdue zones", len(overdue))
    return {
        "total_overdue": len(overdue),
        "overdue_zones": overdue,
    }


def update_schedule_after_measurement(
    conn,
    zone_id: str,
    measurement_date: date | None = None,
) -> dict[str, Any]:
    """Update zone schedule after a measurement is completed."""
    if measurement_date is None:
        measurement_date = date.today()

    cur = conn.cursor()

    # Get current frequency
    cur.execute(
        "SELECT measurement_frequency FROM farm_zone WHERE id = %s",
        (zone_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Zone not found"}

    frequency = row[0] or "semi_annual"
    next_due = compute_next_due_date(measurement_date, frequency)

    cur.execute(
        """
        UPDATE farm_zone
        SET last_measurement_date = %s,
            next_measurement_due = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (measurement_date, next_due, zone_id),
    )

    cur.close()

    logger.info("Updated schedule for zone %s: next due %s", zone_id, next_due)
    return {
        "zone_id": zone_id,
        "last_measurement_date": str(measurement_date),
        "next_measurement_due": str(next_due),
        "frequency": frequency,
    }


def get_measurement_summary(conn, location_id: str) -> dict[str, Any]:
    """Get measurement schedule summary for a location."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COUNT(*) AS total_scheduled,
            COUNT(*) FILTER (WHERE schedule_status = 'overdue') AS overdue,
            COUNT(*) FILTER (WHERE schedule_status = 'due_soon') AS due_soon,
            COUNT(*) FILTER (WHERE schedule_status = 'on_track') AS on_track,
            COUNT(*) FILTER (WHERE schedule_status = 'no_schedule') AS no_schedule
        FROM v_measurement_schedule
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_scheduled": row[0] or 0,
        "overdue": row[1] or 0,
        "due_soon": row[2] or 0,
        "on_track": row[3] or 0,
        "no_schedule": row[4] or 0,
    }


def set_measurement_schedule(
    conn,
    zone_id: str,
    frequency: str,
    start_date: date | None = None,
) -> dict[str, Any]:
    """Set or update measurement frequency for a zone."""
    if frequency not in FREQUENCY_INTERVALS:
        return {"error": f"Invalid frequency: {frequency}. Must be one of: {list(FREQUENCY_INTERVALS.keys())}"}

    if start_date is None:
        start_date = date.today()

    next_due = compute_next_due_date(start_date, frequency)

    cur = conn.cursor()
    cur.execute(
        """
        UPDATE farm_zone
        SET measurement_frequency = %s,
            next_measurement_due = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (frequency, next_due, zone_id),
    )
    cur.close()

    logger.info("Set measurement schedule for zone %s: %s, next due %s", zone_id, frequency, next_due)
    return {
        "zone_id": zone_id,
        "frequency": frequency,
        "next_measurement_due": str(next_due),
    }
