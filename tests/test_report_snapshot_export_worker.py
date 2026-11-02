"""Mocked contract checks for the isolated report snapshot export worker."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from services.export import report_snapshot_export_worker as worker
from services.export.reports.context import compute_hash


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.connection.events.append(("execute", sql, params))
        if "claim_report_snapshot_export_batch" in sql:
            self.rows = self.connection.claim_rows
        elif "read_report_snapshot_export_source" in sql:
            if self.connection.source_error is not None:
                raise self.connection.source_error
            self.rows = self.connection.source_rows
        elif "finish_report_snapshot_export_attempt" in sql:
            self.connection.finish_calls.append(params)
            self.result = (self.connection.finish_statuses.pop(0),)
        else:
            raise AssertionError("unexpected SQL in mocked export worker")

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.result


class _Connection:
    def __init__(self, *, claim_rows, source_rows, finish_statuses=None, source_error=None):
        self.claim_rows = claim_rows
        self.source_rows = source_rows
        self.finish_statuses = list(finish_statuses or ["completed"])
        self.source_error = source_error
        self.events = []
        self.finish_calls = []
        self.commit_count = 0
        self.rollback_count = 0
        self.closed = False
        self.fail_commit_at = None

    def cursor(self, **_kwargs):
        return _Cursor(self)

    def commit(self):
        self.commit_count += 1
        self.events.append(("commit", self.commit_count))
        if self.commit_count == self.fail_commit_at:
            raise OSError("simulated ambiguous commit")

    def rollback(self):
        self.rollback_count += 1
        self.events.append(("rollback", self.rollback_count))

    def close(self):
        self.closed = True


class _Store:
    def __init__(self, connection=None, *, fail_write=False):
        self.connection = connection
        self.fail_write = fail_write
        self.writes = []
        self.deletes = []

    def write(self, artifact_id, content):
        if self.fail_write:
            raise worker.ArtifactStorageError("private artifact write failed")
        self.writes.append((artifact_id, content))
        if self.connection is not None:
            self.connection.events.append(("artifact_write", artifact_id, content))

    def read(self, _artifact_id):
        raise AssertionError("worker must not read artifacts")

    def delete(self, artifact_id):
        self.deletes.append(artifact_id)


def _fixture(*, status="verified", location_id=None):
    request_id = uuid4()
    snapshot_id = uuid4()
    expected_location_id = location_id or uuid4()
    lease_token = uuid4()
    report_data = {"summary": "synthetic report", "total": 12}
    claim = {
        "request_id": request_id,
        "snapshot_id": snapshot_id,
        "location_id": expected_location_id,
        "requested_by": uuid4(),
        "attempt_count": 1,
        "lease_token": lease_token,
    }
    source = {
        "id": snapshot_id,
        "location_id": expected_location_id,
        "report_name": "Synthetic report",
        "report_type": "operations",
        "status": status,
        "period_start": None,
        "period_end": None,
        "snapshot_hash": compute_hash(report_data),
        "report_data": report_data,
    }
    connection = _Connection(claim_rows=[claim], source_rows=[source])
    return connection, claim, source


@pytest.fixture(autouse=True)
def _enable_worker(monkeypatch):
    monkeypatch.setattr(worker, "require_feature", lambda _feature: None)


def test_success_commits_lease_and_source_before_artifact_write():
    connection, claim, _source = _fixture()
    store = _Store(connection)
    result = worker.run_once(
        connection_factory=lambda: connection,
        artifact_store=store,
    )

    assert result == {
        "claimed": 1,
        "completed": 1,
        "retryable": 0,
        "dead_letter": 0,
        "lease_lost": 0,
        "rejected": 0,
    }
    assert connection.commit_count == 3
    assert connection.closed
    assert len(store.writes) == 1
    artifact_id, content = store.writes[0]
    assert isinstance(artifact_id, UUID)
    assert artifact_id != claim["request_id"]
    assert b"synthetic report" in content
    assert not store.deletes
    sql = [event[1] for event in connection.events if event[0] == "execute"]
    assert "claim_report_snapshot_export_batch" in sql[0]
    assert "read_report_snapshot_export_source" in sql[1]
    assert "finish_report_snapshot_export_attempt" in sql[2]
    assert connection.events.index(next(event for event in connection.events if event[0] == "artifact_write")) > 3
    finish = connection.finish_calls[0]
    assert finish[0:3] == (claim["request_id"], "report-snapshot-export-worker", claim["lease_token"])
    assert finish[3:6] == (True, None, 0)
    assert finish[6] == artifact_id
    assert finish[7] == worker.hashlib.sha256(content).hexdigest()
    assert finish[8] == len(content)


@pytest.mark.parametrize("status, expected", [("retryable", "retryable"), ("dead_letter", "dead_letter")])
def test_non_exportable_snapshot_is_failed_without_writing_artifact(status, expected):
    connection, _claim, _source = _fixture(status="draft")
    connection.finish_statuses = [status]
    store = _Store(connection)

    result = worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert result[expected] == 1
    assert not store.writes
    assert connection.finish_calls[0][3] is False
    assert connection.finish_calls[0][4] == "snapshot_invalid"
    assert connection.finish_calls[0][6:] == (None, None, None)


@pytest.mark.parametrize("status", ["lease_lost", "rejected"])
def test_explicit_finish_rejection_removes_unique_artifact(status):
    connection, _claim, _source = _fixture()
    connection.finish_statuses = [status]
    store = _Store(connection)

    result = worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert result[status] == 1
    assert len(store.writes) == 1
    assert store.deletes == [store.writes[0][0]]


def test_source_database_error_is_not_reclassified_or_acknowledged():
    connection, _claim, _source = _fixture()
    connection.source_error = RuntimeError("database authorization denied")
    store = _Store(connection)

    with pytest.raises(RuntimeError, match="database authorization denied"):
        worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert not connection.finish_calls
    assert not store.writes
    assert connection.rollback_count == 1
    assert connection.closed


def test_ambiguous_finish_commit_preserves_written_artifact():
    connection, _claim, _source = _fixture()
    connection.fail_commit_at = 3
    store = _Store(connection)

    with pytest.raises(OSError, match="simulated ambiguous commit"):
        worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert len(store.writes) == 1
    assert not store.deletes
    assert connection.rollback_count == 1
    assert connection.closed


def test_feature_off_fails_before_storage_or_database_access(monkeypatch):
    calls = []

    def disabled(feature):
        calls.append(feature)
        raise RuntimeError("feature is disabled")

    monkeypatch.setattr(worker, "require_feature", disabled)
    with pytest.raises(RuntimeError, match="feature is disabled"):
        worker.run_once(connection_factory=lambda: pytest.fail("database must not open"))
    assert calls == ["isolated_report_snapshot_export_worker"]


def test_feature_flag_defaults_off_in_a_clean_environment():
    environment = os.environ.copy()
    environment.pop("KOKONUT_FEATURE_ISOLATED_REPORT_SNAPSHOT_EXPORT_WORKER", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from services.core.features import FEATURES; "
            "print(FEATURES['isolated_report_snapshot_export_worker']['enabled'])",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.stdout.strip() == "False"


def test_compose_worker_is_opt_in_one_shot_and_has_no_shared_database_credentials():
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.worker.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    worker_service = compose["services"]["report-snapshot-export-worker"]
    init_service = compose["services"]["report-snapshot-export-artifact-init"]

    assert worker_service["profiles"] == ["report-snapshot-export"]
    assert worker_service["restart"] == "no"
    assert worker_service["user"] == "appuser"
    assert worker_service["command"][:3] == [
        "python3", "-m", "services.export.report_snapshot_export_worker"
    ]
    assert worker_service["environment"][
        "KOKONUT_FEATURE_ISOLATED_REPORT_SNAPSHOT_EXPORT_WORKER"
    ].endswith(":-false}")
    assert "KOKONUT_REPORT_SNAPSHOT_EXPORT_DATABASE_URL" in worker_service["environment"]
    assert worker_service["environment"]["KOKONUT_PRIVATE_EXPORT_DIR"] == (
        "/var/lib/kokonut/report-snapshot-exports"
    )
    assert "KOKONUT_PRIVATE_EXPORT_S3_WORKER_ACCESS_KEY_ID" in worker_service["environment"]
    assert "KOKONUT_PRIVATE_EXPORT_S3_READER_ACCESS_KEY_ID" not in worker_service["environment"]
    assert not {"PG_USER", "PG_PASSWORD", "POSTGRES_PASSWORD"} & set(
        worker_service["environment"]
    )
    assert "report-snapshot-export-artifact-init" in worker_service["depends_on"]
    assert init_service["profiles"] == ["report-snapshot-export"]
    assert init_service["user"] == "0:0"

    gateway_service = compose["services"]["gateway"]
    assert gateway_service["environment"]["KOKONUT_PRIVATE_EXPORT_DIR"] == (
        "/var/lib/kokonut/report-snapshot-exports"
    )
    assert "KOKONUT_PRIVATE_EXPORT_S3_READER_ACCESS_KEY_ID" in gateway_service["environment"]
    assert "KOKONUT_PRIVATE_EXPORT_S3_WORKER_ACCESS_KEY_ID" not in gateway_service["environment"]
    assert gateway_service["volumes"] == [
        "report-snapshot-export-artifacts:/var/lib/kokonut/report-snapshot-exports:ro"
    ]


def test_storage_failure_is_recorded_without_export_metadata():
    connection, _claim, _source = _fixture()
    connection.finish_statuses = ["retryable"]
    store = _Store(fail_write=True)

    result = worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert result["retryable"] == 1
    assert not store.writes
    assert not store.deletes
    finish = connection.finish_calls[0]
    assert finish[3] is False
    assert finish[4] == "storage_write_failed"
    assert finish[6:] == (None, None, None)


def test_missing_bounded_source_is_recorded_without_artifact():
    connection, _claim, _source = _fixture()
    connection.source_rows = []
    connection.finish_statuses = ["retryable"]
    store = _Store()

    result = worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert result["retryable"] == 1
    assert not store.writes
    assert connection.finish_calls[0][4] == "source_changed"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"worker_id": "bad worker"},
        {"limit": 0},
        {"limit": 21},
        {"lease_seconds": 29},
        {"lease_seconds": 901},
    ],
)
def test_invalid_worker_bounds_fail_before_database_access(kwargs):
    with pytest.raises(ValueError):
        worker.run_once(
            connection_factory=lambda: pytest.fail("database must not open"),
            artifact_store=_Store(),
            **kwargs,
        )


def test_dedicated_worker_database_key_is_used(monkeypatch):
    connection, _claim, _source = _fixture()
    keys = []
    monkeypatch.setattr(worker, "get_worker_db", lambda key: (keys.append(key), connection)[1])

    worker.run_once(artifact_store=_Store())

    assert keys == ["report_snapshot_export"]


def test_claimed_snapshot_identity_mismatch_fails_attempt_without_write():
    connection, _claim, source = _fixture()
    source["id"] = uuid4()
    connection.finish_statuses = ["retryable"]
    store = _Store(connection)

    result = worker.run_once(connection_factory=lambda: connection, artifact_store=store)

    assert result["retryable"] == 1
    assert not store.writes
    assert connection.finish_calls[0][4] == "snapshot_invalid"
