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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger
from .base import get_db

logger = get_logger("ingestion.remote_sensing_fetcher")


def _query_active_jobs(conn) -> List[Dict[str, Any]]:
    """Query active remote sensing fetch jobs that are due."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM remote_sensing_job
        WHERE status = 'active'
        AND (next_run_at IS NULL OR next_run_at <= NOW())
        ORDER BY next_run_at NULLS FIRST
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


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
    updates.append("updated_at = NOW()")
    params.append(job_id)
    cur.execute(
        f"UPDATE remote_sensing_job SET {', '.join(updates)} WHERE id = %s",
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
    cur.execute("""
        SELECT
            ST_XMin(ST_Extent(p.geometry)) AS west,
            ST_YMin(ST_Extent(p.geometry)) AS south,
            ST_XMax(ST_Extent(p.geometry)) AS east,
            ST_YMax(ST_Extent(p.geometry)) AS north
        FROM plot p
        JOIN farm f ON p.farm_id = f.id
        WHERE f.location_id = %s AND p.geometry IS NOT NULL
    """, (str(job["location_id"]),))
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

    now = datetime.now(timezone.utc)
    _update_job_status(conn, job_id, last_run_at=now)

    try:
        if provider == "gee":
            from .gee_remote_sensing import fetch_gee
            result = fetch_gee(conn, job)
        elif provider == "copernicus":
            from .copernicus_remote_sensing import fetch_copernicus
            result = fetch_copernicus(conn, job)
        else:
            result = {"status": "error", "message": f"Unknown provider: {provider}"}

        observations = result.get("observations", 0)
        _update_job_status(
            conn,
            job_id,
            last_run_status="success" if result.get("status") == "success" else "error",
            observations_fetched=observations,
            next_run_at=_compute_next_run(job.get("cadence_days", 7)),
        )
        conn.commit()

        return {
            "job_id": job_id,
            "provider": provider,
            "status": result.get("status", "error"),
            "observations": observations,
            "duration_seconds": (datetime.now(timezone.utc) - now).total_seconds(),
        }

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        _update_job_status(
            conn,
            job_id,
            last_run_status="error",
            next_run_at=_compute_next_run(job.get("cadence_days", 7)),
        )
        conn.commit()
        return {
            "job_id": job_id,
            "provider": provider,
            "status": "error",
            "message": str(e),
        }


def run_due_jobs(conn) -> Dict[str, Any]:
    """Run all due remote sensing fetch jobs."""
    jobs = _query_active_jobs(conn)
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
            print(json.dumps(result, indent=2, default=str))
        elif args.list_jobs:
            result = list_jobs(conn)
            print(json.dumps(result, indent=2, default=str))
        elif args.job_id:
            job = _query_job(conn, args.job_id)
            if job:
                result = fetch_job(conn, job)
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Job {args.job_id} not found")
        elif args.location_id:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO remote_sensing_job (location_id, provider, cadence_days, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id
            """, (args.location_id, args.provider, args.cadence_days))
            job_id = str(cur.fetchone()[0])
            conn.commit()
            print(json.dumps({"job_id": job_id, "status": "created"}))
        else:
            parser.print_help()
    finally:
        conn.close()
