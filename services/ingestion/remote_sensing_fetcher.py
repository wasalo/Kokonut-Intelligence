"""Abstract remote sensing fetcher.

Orchestrates automated satellite data acquisition from multiple providers.
Supports Google Earth Engine (primary) and Copernicus Data Space (fallback).

Usage:
    python3 -m services.ingestion.remote_sensing_fetcher --location-id UUID
    python3 -m services.ingestion.remote_sensing_fetcher --run-jobs --location-id UUID
    python3 -m services.ingestion.remote_sensing_fetcher --list-jobs --location-id UUID
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.cli import print_json

from ..common.logging import get_logger
from .base import get_db
from .clickhouse_outbox import OutboxEnqueueError

logger = get_logger("ingestion.remote_sensing_fetcher")

PROVIDERS = ("gee", "copernicus")
MAX_RUN_BATCH_SIZE = 10
RETRYABLE_MESSAGES = re.compile(
    r"(timeout|timed out|temporar|unavailable|connection|rate limit|429|502|503|504|try again)",
    re.IGNORECASE,
)


def _canonical_location_id(location_id: str | None) -> str:
    """Require one canonical location before remote-sensing database access."""
    if location_id is None:
        raise ValueError("remote-sensing operations require an explicit location UUID")
    try:
        return str(uuid.UUID(str(location_id)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("location_id must be a UUID") from None


def _canonical_job_id(job_id: str) -> str:
    """Require a canonical job UUID before querying PostgreSQL."""
    try:
        return str(uuid.UUID(str(job_id)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("job_id must be a UUID") from None


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


def _safe_provider_attempt_message(
    provider: str,
    outcome: str,
    *,
    error: Exception | None = None,
) -> str | None:
    """Summarize provider failures without persisting exception or response text."""
    label = provider if provider in PROVIDERS else "remote-sensing"
    if error is not None:
        return f"{label} provider failed ({type(error).__name__})"
    if outcome == "success":
        return None
    if outcome == "no_data":
        return f"{label} returned no observations"
    if outcome == "retryable":
        return f"{label} provider failed (retryable)"
    if outcome == "non_retryable":
        return f"{label} provider rejected the request"
    return "remote-sensing provider failed"


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


def _query_active_jobs(conn, location_id: str) -> List[Dict[str, Any]]:
    """Query active remote sensing jobs due for one location."""
    location_id = _canonical_location_id(location_id)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM remote_sensing_job
            WHERE status = 'active'
            AND location_id = %s
            AND (next_run_at IS NULL OR next_run_at <= NOW())
            AND (lease_expires_at IS NULL OR lease_expires_at <= NOW())
            ORDER BY next_run_at NULLS FIRST
        """, (location_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def _claim_due_jobs(conn, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Claim one due job for a required location, keeping leases bounded."""
    location_id = _canonical_location_id(location_id)
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
              AND location_id = %s::uuid
            ORDER BY next_run_at NULLS FIRST
            LIMIT 1
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
            (location_id, worker),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _query_job(conn, job_id: str, location_id: str) -> Optional[Dict[str, Any]]:
    """Query a specific job only within one location."""
    job_id = _canonical_job_id(job_id)
    location_id = _canonical_location_id(location_id)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "SELECT * FROM remote_sensing_job WHERE id = %s AND location_id = %s",
            (job_id, location_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()


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
        try:
            cur.execute(
                "SELECT ST_XMin(bbox) AS west, ST_YMin(bbox) AS south, ST_XMax(bbox) AS east, ST_YMax(bbox) AS north FROM (SELECT bbox FROM remote_sensing_job WHERE id = %s AND location_id = %s) sub",
                (str(job["id"]), str(job["location_id"])),
            )
            row = cur.fetchone()
        finally:
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
    try:
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
    finally:
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


def fetch_job(conn, job: Dict[str, Any], *, location_id: str) -> Dict[str, Any]:
    """Execute a remote sensing fetch job.

    Dispatches to the appropriate provider (gee or copernicus).
    Resolves bbox from job or plot geometries before dispatching.
    """
    location_id = _canonical_location_id(location_id)
    job_location_id = _canonical_location_id(job.get("location_id"))
    if job_location_id != location_id:
        raise ValueError("remote-sensing job is outside the requested location")

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
        except OutboxEnqueueError:
            # Provider source writes and their projection must stay atomic.
            conn.rollback()
            raise OutboxEnqueueError("ClickHouse outbox enqueue failed") from None
        except Exception as exc:
            result = {"status": "error", "observations": 0}
            outcome = _classify_provider_result(error=exc)
            error = _safe_provider_attempt_message(selected_provider, outcome, error=exc)
        else:
            error = _safe_provider_attempt_message(selected_provider, outcome)

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


def run_due_jobs(conn, limit: int = 1, *, location_id: Optional[str] = None) -> Dict[str, Any]:
    """Run a bounded number of due jobs for one explicit location."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RUN_BATCH_SIZE:
        raise ValueError(f"limit must be an integer between 1 and {MAX_RUN_BATCH_SIZE}")
    location_id = _canonical_location_id(location_id)

    results = []
    for _ in range(limit):
        jobs = _claim_due_jobs(conn, location_id=location_id)
        if not jobs:
            break
        job = jobs[0]
        logger.info("Running job %s (provider=%s)", str(job["id"])[:8], job.get("provider"))
        results.append(fetch_job(conn, job, location_id=location_id))

    if not results:
        return {"status": "no_jobs_due", "executed": 0}

    success = sum(1 for r in results if r.get("status") == "success")
    return {
        "status": "completed",
        "executed": len(results),
        "success": success,
        "failed": len(results) - success,
        "results": results,
    }


def list_jobs(conn, location_id: str) -> List[Dict[str, Any]]:
    """List remote sensing fetch jobs for one location."""
    location_id = _canonical_location_id(location_id)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT j.*, l.name AS location_name
            FROM remote_sensing_job j
            JOIN location l ON l.id = j.location_id
            WHERE j.location_id = %s
            ORDER BY j.created_at DESC
        """, (location_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Remote sensing fetch orchestrator")
    parser.add_argument("--run-jobs", action="store_true", help="Run a bounded batch of due jobs")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help=f"Maximum due jobs to run sequentially (1-{MAX_RUN_BATCH_SIZE}; default: 1)",
    )
    parser.add_argument("--list-jobs", action="store_true", help="List all jobs")
    parser.add_argument("--job-id", help="Run a specific job by ID")
    parser.add_argument("--location-id", help="Location UUID to scope due jobs or to create a new job")
    parser.add_argument("--provider", choices=["gee", "copernicus"], default="gee")
    parser.add_argument("--cadence-days", type=int, default=7)
    args = parser.parse_args(argv)

    explicit_operations = [args.run_jobs, args.list_jobs, args.job_id is not None]
    if not any(explicit_operations) and args.location_id is None:
        parser.print_help()
        return
    if sum(explicit_operations) > 1:
        parser.error("choose exactly one of --run-jobs, --list-jobs, or --job-id")
    if not any(explicit_operations) and args.cadence_days < 1:
        parser.error("--cadence-days must be a positive integer when creating a job")

    if args.run_jobs and not 1 <= args.limit <= MAX_RUN_BATCH_SIZE:
        parser.error(f"--limit must be between 1 and {MAX_RUN_BATCH_SIZE}")
    try:
        if args.job_id is not None:
            args.job_id = _canonical_job_id(args.job_id)
        location_id = _canonical_location_id(args.location_id)
    except ValueError as exc:
        parser.error(str(exc))

    conn = get_db()
    try:
        if args.run_jobs:
            result = run_due_jobs(conn, limit=args.limit, location_id=location_id)
            print_json(result)
        elif args.list_jobs:
            result = list_jobs(conn, location_id)
            print_json(result)
        elif args.job_id:
            job = _query_job(conn, args.job_id, location_id)
            if job:
                result = fetch_job(conn, job, location_id=location_id)
                print_json(result)
            else:
                print(f"Job {args.job_id} not found")
        else:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO remote_sensing_job (location_id, provider, cadence_days, status)
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (location_id, args.provider, args.cadence_days),
                )
                job_id = str(cur.fetchone()[0])
                conn.commit()
                print(json.dumps({"job_id": job_id, "status": "created"}))
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
