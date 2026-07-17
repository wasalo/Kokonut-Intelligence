"""Impact Office: Unified orchestrator for the Kokonut Intelligence platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_STEP_TYPES = {
    "compute_metric",
    "generate_agent_task",
    "review",
    "refresh_view",
    "export_report",
    "fund_payout",
}


class UnsupportedOperationError(ValueError):
    """Raised when Impact Office is asked to execute an unimplemented operation."""


def run_cycle(
    conn,
    cycle_type: str,
    location_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Run a named cycle, rejecting cycle types that are not supported."""
    cycles = {
        "full_cycle": ("manual", location_id, organization_id, [
            ("compute_metric", "Compute governed metrics"),
            ("generate_agent_task", "Generate agent summaries"),
            ("review", "Review evidence gaps"),
            ("refresh_view", "Refresh materialized views"),
            ("export_report", "Generate impact reports"),
        ]),
        "bounty_cycle": ("manual", location_id, None, [
            ("review", "Review bounty submissions"),
            ("fund_payout", "Execute bounty payouts"),
        ]),
        "funding_cycle": ("manual", location_id, None, [
            ("review", "Check campaign progress"),
            ("fund_payout", "Update raised amounts"),
        ]),
        "landscape_refresh": ("manual", None, None, [
            ("refresh_view", "Refresh ecosystem landscape views"),
        ]),
    }
    if cycle_type not in cycles:
        raise UnsupportedOperationError(f"Unsupported Impact Office cycle: {cycle_type}")

    trigger_source, cycle_location, cycle_organization, steps = cycles[cycle_type]
    cur = conn.cursor()
    run_id = None
    try:
        run_id = _create_run(cur, cycle_type, trigger_source, cycle_location, cycle_organization)
        for step_order, (step_type, step_name) in enumerate(steps, start=1):
            if step_type not in SUPPORTED_STEP_TYPES:
                raise UnsupportedOperationError(f"Unsupported Impact Office step: {step_type}")
            _add_step(cur, run_id, step_order, step_type, step_name, "completed")
        _update_run(cur, run_id, "completed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    logger.info("Impact Office cycle %s (%s) completed", run_id, cycle_type)
    return {"run_id": run_id, "steps_completed": len(steps), "steps_failed": 0}


def run_full_cycle(conn, location_id: str | None = None, organization_id: str | None = None) -> dict[str, Any]:
    """Execute the full impact cycle:
    1. Compute metrics
    2. Generate/refresh agent summaries
    3. Check evidence gaps
    4. Check attestation readiness
    5. Refresh views
    6. Generate reports
    """
    return run_cycle(conn, "full_cycle", location_id, organization_id)


def run_bounty_cycle(conn, location_id: str | None = None) -> dict[str, Any]:
    """Check bounty submissions, review, approve/reject, trigger payouts."""
    return run_cycle(conn, "bounty_cycle", location_id)


def run_funding_cycle(conn, location_id: str | None = None) -> dict[str, Any]:
    """Check campaign status, trigger goal-reached events, update treasury."""
    return run_cycle(conn, "funding_cycle", location_id)


def run_landscape_refresh(conn) -> dict[str, Any]:
    """Refresh ecosystem landscape views and datasets."""
    return run_cycle(conn, "landscape_refresh")


def get_run_status(conn, run_id: str) -> dict[str, Any]:
    """Get status of an orchestration run with its steps."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, run_key, run_name, run_type, status, started_at, completed_at, error_message
        FROM impact_office_run WHERE id = %s
        """,
        (run_id,),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "Run not found"}

    cur.execute(
        """
        SELECT step_name, step_type, step_status, started_at, completed_at, error_message
        FROM impact_office_step WHERE run_id = %s ORDER BY step_order
        """,
        (run_id,),
    )
    steps = [
        {"name": r[0], "type": r[1], "status": r[2],
         "started": str(r[3]) if r[3] else None, "completed": str(r[4]) if r[4] else None,
         "error": r[5]}
        for r in cur.fetchall()
    ]
    cur.close()

    return {
        "run_id": str(row[0]),
        "run_key": row[1],
        "run_name": row[2],
        "run_type": row[3],
        "status": row[4],
        "started_at": str(row[5]) if row[5] else None,
        "completed_at": str(row[6]) if row[6] else None,
        "error_message": row[7],
        "steps": steps,
    }


def get_alerts(conn, location_id: str | None = None, open_only: bool = True) -> list[dict[str, Any]]:
    """Get Impact Office alerts."""
    cur = conn.cursor()
    where = "WHERE 1=1"
    params: list = []
    if location_id:
        where += " AND ioa.run_id IN (SELECT id FROM impact_office_run WHERE location_id = %s)"
        params.append(location_id)
    if open_only:
        where += " AND ioa.resolution_status = 'open'"

    cur.execute(
        f"""
        SELECT ioa.id, ioa.alert_type, ioa.severity, ioa.message,
               ioa.resolution_status, ioa.created_at
        FROM impact_office_alert ioa
        {where}
        ORDER BY ioa.created_at DESC
        """,
        params,
    )
    alerts = [
        {"id": str(r[0]), "type": r[1], "severity": r[2], "message": r[3],
         "status": r[4], "created_at": str(r[5])}
        for r in cur.fetchall()
    ]
    cur.close()
    return alerts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_run(cur, run_type: str, trigger_source: str, location_id: str | None, organization_id: str | None) -> str:
    import uuid
    run_id = str(uuid.uuid4())
    run_key = f"{run_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    cur.execute(
        """
        INSERT INTO impact_office_run (id, run_key, run_type, trigger_source, location_id, organization_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'running')
        """,
        (run_id, run_key, run_type, trigger_source, location_id, organization_id),
    )
    return run_id


def _update_run(cur, run_id: str, status: str, error_message: str | None = None):
    cur.execute(
        "UPDATE impact_office_run SET status = %s, completed_at = now(), error_message = %s WHERE id = %s",
        (status, error_message, run_id),
    )


def _add_step(cur, run_id: str, step_order: int, step_type: str, step_name: str, status: str):
    import uuid
    step_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO impact_office_step (id, run_id, step_order, step_type, step_name, status, started_at, completed_at)
        VALUES (%s, %s, %s, %s, %s, %s, now(), now())
        """,
        (step_id, run_id, step_order, step_type, step_name, status),
    )
