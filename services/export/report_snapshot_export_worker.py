"""One-shot worker for private, governed report-snapshot exports.

The worker claims durable requests through bounded database functions, commits
its lease before touching private artifact storage, and acknowledges only while
the same lease remains valid. It never uses the shared application database
configuration and never applies artifact retention automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID, uuid4

import psycopg2.extras

from services.common.worker_database import get_worker_db
from services.core.features import require_feature
from services.export.artifact_storage import (
    ArtifactStorageError,
    LocalPrivateArtifactStore,
    PrivateArtifactStore,
)
from services.export.report_snapshot_export import (
    ReportSnapshotExportError,
    ReportSnapshotExportMalformed,
    serialize_report_snapshot_json,
)

_WORKER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,98}$")
_FEATURE = "isolated_report_snapshot_export_worker"
_ARTIFACT_DIRECTORY_ENV = "KOKONUT_PRIVATE_EXPORT_DIR"
_MAX_BATCH_SIZE = 20
_MAX_LEASE_SECONDS = 900
_MAX_ATTEMPTS = 8


class _SourceUnavailable(RuntimeError):
    """The bounded source reader found no source for a live request lease."""


def _validate(worker_id: str, limit: int, lease_seconds: int) -> None:
    if not isinstance(worker_id, str) or not _WORKER_ID.fullmatch(worker_id):
        raise ValueError("report export worker ID has an invalid format")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise ValueError("report export worker batch limit must be between 1 and 20")
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or not 30 <= lease_seconds <= _MAX_LEASE_SECONDS
    ):
        raise ValueError("report export worker lease must be between 30 and 900 seconds")


def _uuid(value: object, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"report export {field} is invalid") from exc
    raise ValueError(f"report export {field} is invalid")


def _claim(
    connection,
    worker_id: str,
    limit: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    """Claim a bounded batch and commit its leases before filesystem I/O."""
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.claim_report_snapshot_export_batch(
                       %s, %s, %s
                   )""",
                (worker_id, limit, lease_seconds),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        connection.commit()
        return rows
    except Exception:
        connection.rollback()
        raise


def _read_source(
    connection,
    request_id: UUID,
    worker_id: str,
    lease_token: UUID,
) -> dict[str, Any]:
    """Read the bounded source, closing the DB transaction before serialization."""
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.read_report_snapshot_export_source(
                       %s, %s, %s
                   )""",
                (request_id, worker_id, lease_token),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        connection.commit()
        if len(rows) != 1:
            raise _SourceUnavailable("report export source is unavailable")
        return rows[0]
    except _SourceUnavailable:
        raise
    except Exception:
        connection.rollback()
        raise


def _retry_delay_seconds(attempt_count: int) -> int:
    exponent = min(max(attempt_count - 1, 0), 8)
    return min(3600, 15 * (2**exponent))


def _error_class(error: Exception) -> str:
    if isinstance(error, _SourceUnavailable):
        return "source_changed"
    if isinstance(error, ArtifactStorageError):
        return "storage_write_failed"
    if isinstance(error, ReportSnapshotExportError):
        if type(error).__name__ == "ReportSnapshotExportTooLarge":
            return "snapshot_too_large"
        return "snapshot_invalid"
    # Persist only a fixed safe class name; never store exception text or
    # report content in the bounded failure receipt.
    return "serialization_failed"


def _finish(
    connection,
    *,
    request_id: UUID,
    worker_id: str,
    lease_token: UUID,
    success: bool,
    error_class: str | None,
    retry_delay_seconds: int,
    artifact_id: UUID | None,
    sha256: str | None,
    size: int | None,
) -> str:
    """Finish one attempt; commit failures are ambiguous and must propagate."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.finish_report_snapshot_export_attempt(
                       %s, %s, %s, %s, %s, %s, %s, %s, %s
                   )""",
                (
                    request_id,
                    worker_id,
                    lease_token,
                    success,
                    error_class,
                    retry_delay_seconds,
                    artifact_id,
                    sha256,
                    size,
                ),
            )
            result = cursor.fetchone()
        if result is None or not isinstance(result[0], str):
            raise RuntimeError("report export completion function returned an invalid result")
        status = result[0]
        connection.commit()
        return status
    except Exception:
        # The server may have committed even if the client lost the response.
        # The caller deliberately leaves any written artifact in place.
        connection.rollback()
        raise


def _cleanup_after_rejection(
    store: PrivateArtifactStore,
    artifact_id: UUID | None,
    status: str,
) -> bool:
    if artifact_id is None or status not in {"lease_lost", "rejected"}:
        return False
    store.delete(artifact_id)
    return True


def _validate_claim(row: Mapping[str, Any]) -> tuple[UUID, UUID, UUID, UUID, int]:
    request_id = _uuid(row.get("request_id"), "request ID")
    snapshot_id = _uuid(row.get("snapshot_id"), "snapshot ID")
    location_id = _uuid(row.get("location_id"), "location ID")
    lease_token = _uuid(row.get("lease_token"), "lease token")
    attempt_count = row.get("attempt_count")
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 1 <= attempt_count <= _MAX_ATTEMPTS
    ):
        raise ValueError("report export attempt number is invalid")
    return request_id, snapshot_id, location_id, lease_token, attempt_count


def _process_claim(
    connection,
    store: PrivateArtifactStore,
    row: Mapping[str, Any],
    worker_id: str,
) -> str:
    request_id, snapshot_id, location_id, lease_token, attempt_count = _validate_claim(row)
    artifact_id: UUID | None = None
    try:
        snapshot = _read_source(connection, request_id, worker_id, lease_token)
        if _uuid(snapshot.get("id"), "source snapshot ID") != snapshot_id:
            raise ReportSnapshotExportMalformed("Report snapshot is malformed")
        content = serialize_report_snapshot_json(snapshot, location_id)
        # Each attempt gets a fresh opaque object key. A stale attempt can
        # never overwrite an artifact from a later successful attempt.
        artifact_id = uuid4()
        store.write(artifact_id, content)
    except (ReportSnapshotExportError, ArtifactStorageError, _SourceUnavailable) as exc:
        status = _finish(
            connection,
            request_id=request_id,
            worker_id=worker_id,
            lease_token=lease_token,
            success=False,
            error_class=_error_class(exc),
            retry_delay_seconds=_retry_delay_seconds(attempt_count),
            artifact_id=None,
            sha256=None,
            size=None,
        )
        _cleanup_after_rejection(store, artifact_id, status)
        return status

    digest = hashlib.sha256(content).hexdigest()
    status = _finish(
        connection,
        request_id=request_id,
        worker_id=worker_id,
        lease_token=lease_token,
        success=True,
        error_class=None,
        retry_delay_seconds=0,
        artifact_id=artifact_id,
        sha256=digest,
        size=len(content),
    )
    _cleanup_after_rejection(store, artifact_id, status)
    return status


def _artifact_store_from_environment(
    environ: Mapping[str, str] | None = None,
) -> LocalPrivateArtifactStore:
    source = os.environ if environ is None else environ
    directory = source.get(_ARTIFACT_DIRECTORY_ENV, "")
    if not isinstance(directory, str) or not directory.strip():
        raise RuntimeError(f"{_ARTIFACT_DIRECTORY_ENV} is required")
    return LocalPrivateArtifactStore(directory)


def run_once(
    worker_id: str = "report-snapshot-export-worker",
    limit: int = 10,
    lease_seconds: int = 300,
    *,
    connection_factory: Callable[[], Any] | None = None,
    artifact_store: PrivateArtifactStore | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, int]:
    """Process one bounded export batch using the dedicated database login."""
    _validate(worker_id, limit, lease_seconds)
    require_feature(_FEATURE)
    store = artifact_store if artifact_store is not None else _artifact_store_from_environment(environ)
    connection = (connection_factory or (lambda: get_worker_db("report_snapshot_export")))()
    try:
        rows = _claim(connection, worker_id, limit, lease_seconds)
        result = {
            "claimed": len(rows),
            "completed": 0,
            "retryable": 0,
            "dead_letter": 0,
            "lease_lost": 0,
            "rejected": 0,
        }
        for row in rows:
            status = _process_claim(connection, store, row, worker_id)
            if status not in result:
                raise RuntimeError("report export worker received an invalid completion status")
            result[status] += 1
        return result
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a bounded report snapshot export batch")
    parser.add_argument("--worker-id", default="report-snapshot-export-worker")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args()

    from services.common.cli import print_json, run

    run(lambda: print_json(run_once(args.worker_id, args.limit, args.lease_seconds)))


if __name__ == "__main__":
    main()
