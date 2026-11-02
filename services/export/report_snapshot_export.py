"""Validate and serialize one governed report snapshot for private export.

This module is intentionally independent of database access, storage, and HTTP.
Callers must supply a bounded snapshot read under their own authorization
boundary. The resulting bytes contain only ``report_data``; in particular,
the legacy ``file_url`` column is never used.
"""

from __future__ import annotations

import json
import math
import re
from uuid import UUID

from services.export.reports.context import compute_hash

MAX_REPORT_SNAPSHOT_BYTES = 512 * 1024
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_EXPORTABLE_STATUSES = frozenset({"verified", "published"})


class ReportSnapshotExportError(ValueError):
    """Base class for safe report-export validation failures."""


class ReportSnapshotExportMalformed(ReportSnapshotExportError):
    """The supplied snapshot or report JSON has an invalid shape."""


class ReportSnapshotExportScopeMismatch(ReportSnapshotExportError):
    """The snapshot is not bound to the requested location."""


class ReportSnapshotExportLifecycleDenied(ReportSnapshotExportError):
    """The snapshot has not reached an exportable lifecycle state."""


class ReportSnapshotExportIntegrityError(ReportSnapshotExportError):
    """The snapshot hash is missing, malformed, or does not match its data."""


class ReportSnapshotExportTooLarge(ReportSnapshotExportError):
    """The serialized report exceeds the private export size limit."""


def _normalize_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ReportSnapshotExportMalformed("Report snapshot is malformed") from exc
    raise ReportSnapshotExportMalformed("Report snapshot is malformed")


def _require_json_value(value: object) -> None:
    """Reject values that PostgreSQL JSONB cannot contain without coercion."""
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ReportSnapshotExportMalformed("Report snapshot data is malformed")
    if isinstance(value, list):
        for item in value:
            _require_json_value(item)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ReportSnapshotExportMalformed("Report snapshot data is malformed")
        for item in value.values():
            _require_json_value(item)
        return
    raise ReportSnapshotExportMalformed("Report snapshot data is malformed")


def serialize_report_snapshot_json(
    snapshot: dict[str, object], expected_location_id: str | UUID
) -> bytes:
    """Return only the JSON payload of a verified, exact-location snapshot.

    ``snapshot`` must come from an existing bounded reader that has already
    checked the current operator grant in the same transaction as the source
    query. This function rechecks payload identity, lifecycle, integrity, and
    size without performing any I/O.
    """
    if not isinstance(snapshot, dict):
        raise ReportSnapshotExportMalformed("Report snapshot is malformed")

    _normalize_uuid(snapshot.get("id"))
    expected_location = _normalize_uuid(expected_location_id)
    location_id = snapshot.get("location_id")
    if location_id is None:
        raise ReportSnapshotExportScopeMismatch(
            "Report snapshot is not bound to the requested location"
        )
    if _normalize_uuid(location_id) != expected_location:
        raise ReportSnapshotExportScopeMismatch(
            "Report snapshot is not bound to the requested location"
        )

    status = snapshot.get("status")
    if not isinstance(status, str) or status not in _EXPORTABLE_STATUSES:
        raise ReportSnapshotExportLifecycleDenied(
            "Report snapshot is not available for export"
        )

    snapshot_hash = snapshot.get("snapshot_hash")
    if not isinstance(snapshot_hash, str) or not _SHA256_HEX.fullmatch(snapshot_hash):
        raise ReportSnapshotExportIntegrityError(
            "Report snapshot integrity could not be verified"
        )

    report_data = snapshot.get("report_data")
    if not isinstance(report_data, dict):
        raise ReportSnapshotExportMalformed("Report snapshot data is malformed")
    try:
        _require_json_value(report_data)
    except RecursionError as exc:
        raise ReportSnapshotExportMalformed(
            "Report snapshot data is malformed"
        ) from exc
    try:
        payload = json.dumps(
            report_data,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ReportSnapshotExportMalformed(
            "Report snapshot data is malformed"
        ) from exc

    if len(payload) > MAX_REPORT_SNAPSHOT_BYTES:
        raise ReportSnapshotExportTooLarge("Report snapshot exceeds the export size limit")

    try:
        actual_hash = compute_hash(report_data)
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ReportSnapshotExportMalformed(
            "Report snapshot data is malformed"
        ) from exc
    if actual_hash != snapshot_hash:
        raise ReportSnapshotExportIntegrityError(
            "Report snapshot integrity could not be verified"
        )

    return payload
