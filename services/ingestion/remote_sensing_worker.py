"""Run remote-sensing provider fetches through signed location functions."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from uuid import UUID

from services.common.cli import print_json, run
from services.common.tenant_context import set_worker_tenant_context
from services.common.worker_database import get_worker_credential, get_worker_db
from services.core.features import is_enabled
from services.ingestion.remote_sensing_fetcher import (
    MAX_RUN_BATCH_SIZE,
    _classify_provider_result,
    _fallback_provider,
)

_WORKER_KEY = "remote_sensing"
_RESOURCE = "remote_sensing"
_ACTION = "run"


def _canonical_location_id(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("an explicit location UUID is required") from None


def _open_scoped_connection(location_id: str, credential: str):
    connection = get_worker_db(_WORKER_KEY)
    try:
        set_worker_tenant_context(
            connection,
            credential=credential,
            location_id=location_id,
            resource=_RESOURCE,
            action=_ACTION,
        )
    except Exception:
        connection.close()
        raise
    return connection


def _claim(location_id: str, credential: str) -> dict | None:
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.claim_remote_sensing_job(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
        connection.commit()
        if row is None or row[0] is None:
            return None
        value = row[0]
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _fetch_records(job: dict) -> tuple[dict, list[dict]]:
    provider = job.get("provider")
    if provider == "gee":
        from services.ingestion.gee_remote_sensing import fetch_gee_records

        return fetch_gee_records(job)
    if provider == "copernicus":
        from services.ingestion.copernicus_remote_sensing import fetch_copernicus_records

        return fetch_copernicus_records(job)
    return ({"status": "error", "message": "unsupported provider", "observations": 0, "retryable": False}, [])


def _attempt_provider_chain(job: dict) -> tuple[list[dict], list[dict], dict]:
    attempts: list[dict] = []
    records: list[dict] = []
    provider = str(job["provider"])
    fallback = _fallback_provider(provider, job)

    while True:
        started_at = datetime.now(UTC)
        try:
            result, provider_records = _fetch_records(job)
            outcome = _classify_provider_result(result)
            message = result.get("message")
        except Exception as exc:
            result = {"observations": 0}
            provider_records = []
            outcome = _classify_provider_result(error=exc)
            message = str(exc)
        finished_at = datetime.now(UTC)
        observations = int(result.get("observations", 0) or 0)
        attempts.append({
            "provider": provider,
            "outcome": outcome,
            "retryable": outcome == "retryable",
            "observations": observations,
            "message": str(message)[:2000] if message else None,
            "fallback_used": len(attempts) > 0,
            "metadata": {},
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        })
        if outcome in ("success", "no_data", "non_retryable") or not fallback:
            records = provider_records
            break
        provider, fallback = fallback, None

    final = attempts[-1]
    if final["outcome"] not in ("success", "no_data"):
        records = []
    if len(records) != final["observations"]:
        raise ValueError("remote-sensing provider count differs from its normalized records")
    return attempts, records, final


def _normalize_records(records: list[dict], location_id: str) -> list[dict]:
    if not isinstance(records, list) or len(records) > 5:
        raise ValueError("remote-sensing provider returned an invalid result list")
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("remote-sensing provider records must be objects")
        try:
            record_location = _canonical_location_id(record.get("location_id"))
        except ValueError:
            raise ValueError("remote-sensing record has an invalid location") from None
        if record_location != location_id:
            raise ValueError("remote-sensing record is outside the signed location")
        value = dict(record)
        metadata = value.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            raise ValueError("remote-sensing metadata must be an object")
        value["metadata"] = metadata
        normalized.append(value)
    return normalized


def _finish(
    job: dict,
    location_id: str,
    credential: str,
    attempts: list[dict],
    records: list[dict],
) -> int:
    connection = _open_scoped_connection(location_id, credential)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.finish_remote_sensing_job(%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb)",
                (
                    job["id"],
                    location_id,
                    job["lease_owner"],
                    json.dumps(attempts, separators=(",", ":")),
                    json.dumps(records, default=str, separators=(",", ":")),
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("remote-sensing completion function returned no result")
            written = int(row[0])
        connection.commit()
        return written
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run_due_jobs(location_id: str, *, limit: int = 1) -> dict:
    """Claim and process a bounded number of jobs for one signed location."""
    canonical_location_id = _canonical_location_id(location_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RUN_BATCH_SIZE:
        raise ValueError(f"limit must be an integer between 1 and {MAX_RUN_BATCH_SIZE}")
    credential = get_worker_credential(_WORKER_KEY)
    results = []
    for _ in range(limit):
        job = _claim(canonical_location_id, credential)
        if job is None:
            break
        if str(job.get("location_id")) != canonical_location_id:
            raise RuntimeError("database returned a job outside the signed location")
        bbox = job.get("bbox")
        job["_resolved_bbox"] = bbox
        attempts, records, final = _attempt_provider_chain(job)
        records = _normalize_records(records, canonical_location_id)
        written = _finish(job, canonical_location_id, credential, attempts, records)
        results.append({
            "job_id": str(job["id"]),
            "provider": final["provider"],
            "configured_provider": job["provider"],
            "status": "success" if final["outcome"] in ("success", "no_data") else "error",
            "observations": final["observations"],
            "records_written": written,
            "attempts": attempts,
            "message": final.get("message"),
        })
    if not results:
        return {"status": "no_jobs_due", "executed": 0}
    succeeded = sum(item["status"] == "success" for item in results)
    return {
        "status": "completed",
        "executed": len(results),
        "success": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run signed remote-sensing provider jobs")
    parser.add_argument("--location-id", required=True, help="One authorized location UUID")
    parser.add_argument("--limit", type=int, default=1, help=f"Maximum claims (1-{MAX_RUN_BATCH_SIZE})")
    args = parser.parse_args(argv)
    try:
        _canonical_location_id(args.location_id)
    except ValueError as exc:
        parser.error(str(exc))
    if not 1 <= args.limit <= MAX_RUN_BATCH_SIZE:
        parser.error(f"--limit must be between 1 and {MAX_RUN_BATCH_SIZE}")
    if not is_enabled("signed_remote_sensing_worker"):
        parser.error("signed remote-sensing worker is disabled")
    print_json(run_due_jobs(args.location_id, limit=args.limit))


if __name__ == "__main__":
    run(main)
