"""Pure validation and serialization for private report-snapshot exports."""

import json
from uuid import UUID

import pytest

from services.export.report_snapshot_export import (
    MAX_REPORT_SNAPSHOT_BYTES,
    ReportSnapshotExportIntegrityError,
    ReportSnapshotExportLifecycleDenied,
    ReportSnapshotExportMalformed,
    ReportSnapshotExportScopeMismatch,
    ReportSnapshotExportTooLarge,
    serialize_report_snapshot_json,
)
from services.export.reports.context import compute_hash

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OTHER_LOCATION_ID = "22222222-2222-4222-8222-222222222222"
SNAPSHOT_ID = "33333333-3333-4333-8333-333333333333"


def _snapshot(**overrides):
    report_data = {
        "report_type": "farm_summary",
        "summary": "Restoration progress",
        "metrics": [{"name": "soil_cover", "value": 0.75}],
    }
    return {
        "id": SNAPSHOT_ID,
        "location_id": LOCATION_ID,
        "status": "verified",
        "snapshot_hash": compute_hash(report_data),
        "report_data": report_data,
        "file_url": "file:///private/secret/report.json",
        **overrides,
    }


def test_serializer_returns_only_verified_report_data_as_json_bytes():
    snapshot = _snapshot()

    payload = serialize_report_snapshot_json(snapshot, UUID(LOCATION_ID))

    assert isinstance(payload, bytes)
    assert json.loads(payload) == snapshot["report_data"]
    assert b"file_url" not in payload
    assert b"file:///private/secret/report.json" not in payload


@pytest.mark.parametrize(
    "location_id",
    [None, OTHER_LOCATION_ID],
    ids=["null-location", "different-location"],
)
def test_serializer_rejects_null_or_mismatched_location(location_id):
    with pytest.raises(ReportSnapshotExportScopeMismatch) as error:
        serialize_report_snapshot_json(_snapshot(location_id=location_id), LOCATION_ID)

    assert "11111111" not in str(error.value)
    assert "22222222" not in str(error.value)


@pytest.mark.parametrize("status", ["draft", "submitted", "rejected", None])
def test_serializer_rejects_non_exportable_lifecycle_status(status):
    with pytest.raises(ReportSnapshotExportLifecycleDenied):
        serialize_report_snapshot_json(_snapshot(status=status), LOCATION_ID)


@pytest.mark.parametrize(
    "snapshot_hash",
    [None, "not-a-digest", "a" * 64],
    ids=["missing", "malformed", "mismatch"],
)
def test_serializer_rejects_missing_malformed_or_mismatched_hash(snapshot_hash):
    with pytest.raises(ReportSnapshotExportIntegrityError) as error:
        serialize_report_snapshot_json(_snapshot(snapshot_hash=snapshot_hash), LOCATION_ID)

    assert "secret" not in str(error.value)


def test_serializer_rejects_a_payload_larger_than_512_kib_before_hash_check():
    report_data = {"body": "x" * MAX_REPORT_SNAPSHOT_BYTES}
    snapshot = _snapshot(report_data=report_data, snapshot_hash="a" * 64)

    with pytest.raises(ReportSnapshotExportTooLarge):
        serialize_report_snapshot_json(snapshot, LOCATION_ID)


@pytest.mark.parametrize(
    "report_data",
    [
        None,
        ["not", "an", "object"],
        {1: "non-string key"},
        {"value": float("nan")},
        {"value": object()},
    ],
    ids=["null", "array", "non-string-key", "non-finite-number", "not-json"],
)
def test_serializer_rejects_malformed_report_data(report_data):
    with pytest.raises(ReportSnapshotExportMalformed):
        serialize_report_snapshot_json(_snapshot(report_data=report_data), LOCATION_ID)


@pytest.mark.parametrize(
    "snapshot_id",
    [None, "not-a-uuid"],
    ids=["missing", "malformed"],
)
def test_serializer_rejects_malformed_snapshot_identity(snapshot_id):
    with pytest.raises(ReportSnapshotExportMalformed):
        serialize_report_snapshot_json(_snapshot(id=snapshot_id), LOCATION_ID)
