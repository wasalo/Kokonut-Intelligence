"""Abstract remote sensing fetcher.

Orchestrates automated satellite data acquisition from multiple providers.
Supports Google Earth Engine (primary) and Copernicus Data Space (fallback).

Usage:
    python3 -m services.ingestion.remote_sensing_fetcher --location-id UUID
    python3 -m services.ingestion.remote_sensing_fetcher --run-jobs
    python3 -m services.ingestion.remote_sensing_fetcher --list-jobs
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger
from .base import get_db
from services.common.cli import print_json
logger = get_logger("ingestion.remote_sensing_fetcher")

PROVIDERS = ("gee", "copernicus")
RETRYABLE_MESSAGES = re.compile(
    r"(timeout|timed out|temporar|unavailable|connection|rate limit|429|502|503|504|try again)",
    re.IGNORECASE,
)


def _classify_provider_result(result: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None) -> str:
    """Return ``success``, ``no_data``, ``retryable``, or ``non_retryable``."""
    if error is not None:
        return (
            "retryable"
            if isinstance(error, (ConnectionError, TimeoutError, OSError))
            else ("retryable" if RETRYABLE_MESSAGES.search(str(error)) else "non_retryable")
        )
    result = result or {}
    if result.get("status") == "success":
        return "success" if result.get("observations", 0) else "no_data"
    if result.get("retryable") is True:
        return "retryable"
    if result.get("retryable") is False:
        return "non_retryable"
    return "retryable" if RETRYABLE_MESSAGES.search(str(result.get("message", ""))) else "non_retryable"


def _fallback_provider(provider: str, job: Dict[str, Any]) -> Optional[str]:
    """Resolve the configured fallback without allowing an arbitrary provider."""
    metadata = job.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    if metadata.get("fallback_enabled", True) is False:
        return None
    fallback = metadata.get("fallback_provider")
    if fallback is None and provider in PROVIDERS:
        fallback = PROVIDERS[1 - PROVIDERS.index(provider)]
    return fallback if fallback in PROVIDERS and fallback != provider else None


def _query_active_jobs(conn) -> List[Dict[str, Any]]:
    """Query active remote sensing fetch jobs that are due."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM remote_sensing_job
        WHERE status = 'active'
        AND (next_run_at IS NULL OR next_run_at <= NOW())
        AND (lease_expires_at IS NULL OR lease_expires_at <= NOW())
        ORDER BY next_run_at NULLS FIRST
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def _claim_due_jobs(conn) -> List[Dict[str, Any]]:
    """Claim due jobs atomically so concurrent workers do not fetch twice."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    worker = f"remote-sensing-{uuid.uuid4()}"
    try:
        cur.execute(
            """
            WITH due AS (
            SELECT id
            FROM remote_sensing_job
            WHERE status = 'active'
              AND (next_run_at IS NULL OR next_run_at <= NOW())
              AND (lease_expires_at IS NULL OR lease_expires_at <= NOW())
            ORDER BY next_run_at NULLS FIRST
            FOR UPDATE SKIP LOCKED
        )
        UPDATE remote_sensing_job j
        SET lease_owner = %s,
            lease_expires_at = NOW() + INTERVAL '30 minutes',
            attempt_count = COALESCE(j.attempt_count, 0) + 1,
            updated_at = NOW()
        FROM due
        WHERE j.id = due.id
        RETURNING j.*
        """,
            (worker,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _query_job(conn, job_id: str) -> Optional[Dict[str, Any]]:
    """Query a specific job."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM remote_sensing_job WHERE id = %s", (job_id,))
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None


def _update_job_status(
    conn,
    job_id: str,
    status: str = None,
    last_run_at: datetime = None,
    last_run_status: str = None,
    observations_fetched: int = None,
    next_run_at: datetime = None,
    lease_owner: str = None,
    error_class: str = None,
    error_message: str = None,
) -> None:
    """Update job run status."""
    cur = conn.cursor()
    updates = []
    params = []
    if status is not None:
        updates.append("status = %s")
        params.append(status)
    if last_run_at is not None:
        updates.append("last_run_at = %s")
        params.append(last_run_at)
    if last_run_status is not None:
        updates.append("last_run_status = %s")
        params.append(last_run_status)
    if observations_fetched is not None:
        updates.append("observations_fetched = observations_fetched + %s")
        params.append(observations_fetched)
    if next_run_at is not None:
        updates.append("next_run_at = %s")
        params.append(next_run_at)
    if lease_owner is not None:
        updates.extend(["lease_owner = NULL", "lease_expires_at = NULL"])
    if error_class is not None:
        updates.append("last_error_class = %s")
        params.append(error_class)
    if error_message is not None:
        updates.append("last_error = %s")
        params.append(error_message[:2000])
    updates.append("updated_at = NOW()")
    params.append(job_id)
    where = "id = %s"
    if lease_owner is not None:
        where += " AND lease_owner = %s"
        params.append(lease_owner)
    cur.execute(
        f"UPDATE remote_sensing_job SET {', '.join(updates)} WHERE {where}",
        params,
    )
    cur.close()


def _compute_next_run(cadence_days: int) -> datetime:
    """Compute next run time based on cadence."""
    from datetime import timedelta

    return datetime.now(timezone.utc) + timedelta(days=cadence_days)


def _resolve_bbox_from_job(conn, job: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Resolve bbox from job or from plot geometries."""
    # If job has explicit bbox, use it
    if job.get("bbox"):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT ST_XMin(bbox) AS west, ST_YMin(bbox) AS south, ST_XMax(bbox) AS east, ST_YMax(bbox) AS north FROM (SELECT bbox FROM remote_sensing_job WHERE id = %s) sub",
            (str(job["id"]),),
        )
        row = cur.fetchone()
        cur.close()
        if row and row["west"] is not None:
            return {
                "west": float(row["west"]),
                "south": float(row["south"]),
                "east": float(row["east"]),
                "north": float(row["north"]),
            }

    # Otherwise derive from plot geometries
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            ST_XMin(ST_Extent(p.geometry)) AS west,
            ST_YMin(ST_Extent(p.geometry)) AS south,
            ST_XMax(ST_Extent(p.geometry)) AS east,
            ST_YMax(ST_Extent(p.geometry)) AS north
        FROM plot p
        JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s AND p.geometry IS NOT NULL
    """,
        (str(job["location_id"]),),
    )
    row = cur.fetchone()
    cur.close()
    if row and row["west"] is not None:
        return {
            "west": float(row["west"]),
            "south": float(row["south"]),
            "east": float(row["east"]),
            "north": float(row["north"]),
        }
    return None


def _record_provider_attempt(conn, job_id: str, attempt: Dict[str, Any]) -> None:
    """Persist one provider attempt; this is intentionally append-only."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO remote_sensing_provider_attempt
            (job_id, provider, attempt_number, outcome, retryable, observations,
             error_message, started_at, finished_at, fallback_used, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            job_id,
            attempt["provider"],
            attempt["attempt_number"],
            attempt["outcome"],
            attempt.get("retryable"),
            attempt.get("observations", 0),
            attempt.get("message"),
            attempt["started_at"],
            attempt["finished_at"],
            attempt.get("fallback_used", False),
            json.dumps(attempt.get("metadata", {})),
        ),
    )
    cur.close()


def fetch_job(conn, job: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a remote sensing fetch job.

    Dispatches to the appropriate provider (gee or copernicus).
    Resolves bbox from job or plot geometries before dispatching.
    """
    provider = job.get("provider", "gee")
    job_id = str(job["id"])

    # Resolve bbox before dispatching to provider
    bbox = _resolve_bbox_from_job(conn, job)
    if bbox:
        job["_resolved_bbox"] = bbox

    started = datetime.now(timezone.utc)
    lease_owner = job.get("lease_owner")
    attempts = []
    providers = [provider]
    fallback = _fallback_provider(provider, job)
    for selected_provider in list(providers):
        attempt_started = datetime.now(timezone.utc)
        try:
            if selected_provider == "gee":
                from .gee_remote_sensing import fetch_gee

                result = fetch_gee(conn, job)
            elif selected_provider == "copernicus":
                from .copernicus_remote_sensing import fetch_copernicus

                result = fetch_copernicus(conn, job)
            else:
                result = {"status": "error", "message": f"Unknown provider: {selected_provider}", "retryable": False}
            outcome = _classify_provider_result(result)
            error = result.get("message")
        except Exception as exc:
            result = {"status": "error", "message": str(exc), "observations": 0}
            outcome = _classify_provider_result(error=exc)
            error = str(exc)

        attempt = {
            "provider": selected_provider,
            "attempt_number": len(attempts) + 1,
            "outcome": outcome,
            "retryable": outcome == "retryable",
            "observations": int(result.get("observations", 0) or 0),
            "message": error,
            "started_at": attempt_started,
            "finished_at": datetime.now(timezone.utc),
            "fallback_used": len(attempts) > 0,
        }
        attempts.append(attempt)
        _record_provider_attempt(conn, job_id, attempt)
        # Commit the append-only attempt before any later provider/state work.
        conn.commit()
        if outcome in ("success", "no_data") or outcome == "non_retryable" or not fallback:
            break
        providers.append(fallback)
        fallback = None

    final = attempts[-1]
    success = final["outcome"] in ("success", "no_data")
    retryable = final["outcome"] == "retryable"
    try:
        _update_job_status(
            conn,
            job_id,
            status="active" if success or retryable else "error",
            last_run_at=started,
            last_run_status="success" if success else "error",
            observations_fetched=final["observations"],
            next_run_at=(datetime.now(timezone.utc) + timedelta(minutes=15))
            if retryable
            else _compute_next_run(job.get("cadence_days", 7)),
            lease_owner=lease_owner,
            error_class=final["outcome"] if not success else None,
            error_message=final.get("message"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "job_id": job_id,
        "provider": final["provider"],
        "configured_provider": provider,
        "status": "success" if success else "error",
        "observations": final["observations"],
        "attempts": attempts,
        "duration_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
        "message": final.get("message"),
    }


def run_due_jobs(conn) -> Dict[str, Any]:
    """Run all due remote sensing fetch jobs."""
    jobs = _claim_due_jobs(conn)
    if not jobs:
        return {"status": "no_jobs_due", "executed": 0}

    results = []
    for job in jobs:
        logger.info("Running job %s (provider=%s)", str(job["id"])[:8], job.get("provider"))
        result = fetch_job(conn, job)
        results.append(result)

    success = sum(1 for r in results if r.get("status") == "success")
    return {
        "status": "completed",
        "executed": len(results),
        "success": success,
        "failed": len(results) - success,
        "results": results,
    }


def list_jobs(conn) -> List[Dict[str, Any]]:
    """List all remote sensing fetch jobs."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT j.*, l.name AS location_name
        FROM remote_sensing_job j
        JOIN location l ON l.id = j.location_id
        ORDER BY j.created_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Remote sensing fetch orchestrator")
    parser.add_argument("--run-jobs", action="store_true", help="Run all due jobs")
    parser.add_argument("--list-jobs", action="store_true", help="List all jobs")
    parser.add_argument("--job-id", help="Run a specific job by ID")
    parser.add_argument("--location-id", help="Location UUID for new job")
    parser.add_argument("--provider", choices=["gee", "copernicus"], default="gee")
    parser.add_argument("--cadence-days", type=int, default=7)
    args = parser.parse_args()

    conn = get_db()
    try:
        if args.run_jobs:
            result = run_due_jobs(conn)
            print_json(result)
        elif args.list_jobs:
            result = list_jobs(conn)
            print_json(result)
        elif args.job_id:
            job = _query_job(conn, args.job_id)
            if job:
                result = fetch_job(conn, job)
                print_json(result)
            else:
                print(f"Job {args.job_id} not found")
        elif args.location_id:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO remote_sensing_job (location_id, provider, cadence_days, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id
            """,
                (args.location_id, args.provider, args.cadence_days),
            )
            job_id = str(cur.fetchone()[0])
            conn.commit()
            print(json.dumps({"job_id": job_id, "status": "created"}))
        else:
            parser.print_help()
    finally:
        conn.close()
