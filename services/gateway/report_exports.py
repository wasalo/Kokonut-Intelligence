"""Tenant-scoped Gateway operations for private report snapshot exports."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from functools import partial
from typing import Callable
from uuid import UUID

import psycopg2

from services.common.tenant_context import set_operator_tenant_context
from services.export.artifact_storage import (
    ArtifactStorageError,
    PrivateArtifactStore,
    create_private_artifact_store,
)

MAX_ARTIFACT_BYTES = 512 * 1024
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class ReportExportNotFound(LookupError):
    """A report export request is unavailable within the caller's scope."""


class ReportExportConflict(RuntimeError):
    """An idempotency key conflicts with an earlier request."""


class ReportExportArtifactUnavailable(RuntimeError):
    """A completed private artifact is missing or cannot be verified."""


@dataclass(frozen=True)
class ReportExportArtifact:
    """Verified export bytes for a response; no storage key or path escapes."""

    request_id: UUID
    content: bytes


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {label} identifier") from exc


def _rows(cursor, rows) -> list[dict]:
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [dict(row) for row in rows]
    columns = [getattr(column, "name", None) or column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _row(cursor, row) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    columns = [getattr(column, "name", None) or column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _set_context(connection, *, operator_id: str, location_id: str, action: str) -> None:
    set_operator_tenant_context(
        connection,
        operator_id=operator_id,
        location_id=location_id,
        resource="report_snapshot_export",
        action=action,
    )


def request_report_export(
    operator_id: str,
    location_id: str,
    report_snapshot_id: str,
    idempotency_key: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create or retrieve one exact-location export request through the DB API."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    report_snapshot_id = _uuid(report_snapshot_id, "report snapshot")
    idempotency_key = _uuid(idempotency_key, "idempotency")
    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            _set_context(
                connection,
                operator_id=operator_id,
                location_id=location_id,
                action="create",
            )
            cursor.execute(
                """SELECT request_id, status, created_at
                     FROM kokonut_security.request_report_snapshot_export(
                         %s::uuid, %s::uuid, %s::uuid
                     )""",
                (location_id, report_snapshot_id, idempotency_key),
            )
            result = _row(cursor, cursor.fetchone())
        if result is None:
            raise ReportExportNotFound("Report snapshot is unavailable for export")
        connection.commit()
        committed = True
        return result
    except psycopg2.errors.UniqueViolation:
        raise ReportExportConflict(
            "This idempotency key is already bound to another request"
        ) from None
    finally:
        if not committed:
            try:
                connection.rollback()
            except Exception:
                pass
        connection.close()


def list_report_exports(
    operator_id: str,
    location_id: str,
    limit: int = 50,
    *,
    connection_factory: Callable | None = None,
) -> list[dict]:
    """Return a bounded request-status list for one authorized location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            # The signed tenant-context setter locks current grants with
            # SELECT ... FOR SHARE, which PostgreSQL rejects in a read-only
            # transaction. Keep the API projection allow-listed through its
            # bounded SELECT function and leave all mutations to the worker.
            _set_context(
                connection,
                operator_id=operator_id,
                location_id=location_id,
                action="read",
            )
            cursor.execute(
                """SELECT request_id, snapshot_id, location_id, status,
                          attempt_count, artifact_size, created_at, updated_at,
                          completed_at, last_error_class
                     FROM kokonut_security.list_report_snapshot_exports(
                         %s::uuid, %s::integer
                     )""",
                (location_id, limit),
            )
            return _rows(cursor, cursor.fetchall())
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_report_export(
    operator_id: str,
    location_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Read one request summary within the caller's exact location scope."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    request_id = _uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            _set_context(
                connection,
                operator_id=operator_id,
                location_id=location_id,
                action="read",
            )
            cursor.execute(
                """SELECT request_id, snapshot_id, location_id, status,
                          attempt_count, artifact_size, created_at, updated_at,
                          completed_at, last_error_class
                     FROM kokonut_security.get_report_snapshot_export(
                         %s::uuid, %s::uuid
                     )""",
                (location_id, request_id),
            )
            return _row(cursor, cursor.fetchone())
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _artifact_store() -> PrivateArtifactStore:
    return create_private_artifact_store(os.environ, access="reader")


def download_report_export(
    operator_id: str,
    location_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
    artifact_store_factory: Callable[[], PrivateArtifactStore] | None = None,
) -> ReportExportArtifact:
    """Authorize and read one verified private artifact within a DB transaction.

    The current location grant and artifact metadata are checked by PostgreSQL.
    The private store read and size/digest verification happen before the
    transaction is closed, and only verified bytes are returned to the route.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    normalized_request_id = _uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            _set_context(
                connection,
                operator_id=operator_id,
                location_id=location_id,
                action="download",
            )
            cursor.execute(
                """SELECT artifact_id, artifact_sha256, artifact_size
                     FROM kokonut_security.authorize_report_snapshot_export_download(
                         %s::uuid, %s::uuid
                     )""",
                (location_id, normalized_request_id),
            )
            metadata = _row(cursor, cursor.fetchone())
            if metadata is None:
                raise ReportExportNotFound("Report export is not available")

        try:
            artifact_id = _uuid(metadata.get("artifact_id"), "artifact")
        except ValueError:
            raise ReportExportArtifactUnavailable(
                "Report export could not be verified"
            ) from None
        expected_hash = metadata.get("artifact_sha256")
        expected_size = metadata.get("artifact_size")
        if (
            not isinstance(expected_hash, str)
            or not _SHA256_HEX.fullmatch(expected_hash)
            or isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
            or not 1 <= expected_size <= MAX_ARTIFACT_BYTES
        ):
            raise ReportExportArtifactUnavailable("Report export could not be verified")
        try:
            store = (artifact_store_factory or _artifact_store)()
            content = store.read(artifact_id, max_bytes=expected_size)
        except (ArtifactStorageError, OSError, ValueError):
            raise ReportExportArtifactUnavailable(
                "Report export is temporarily unavailable"
            ) from None
        if (
            not isinstance(content, bytes)
            or len(content) != expected_size
            or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), expected_hash)
        ):
            raise ReportExportArtifactUnavailable("Report export could not be verified")
        return ReportExportArtifact(UUID(normalized_request_id), content)
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
