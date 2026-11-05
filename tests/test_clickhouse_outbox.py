import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import clickhouse_outbox, clickhouse_outbox_worker
from services.ingestion.clickhouse_outbox import (
    OutboxEnqueueError,
    deliver_claimed_batch,
    enqueue,
)


def _row(row_id: str, attempt_count: int = 1) -> dict:
    return {
        "id": row_id,
        "attempt_count": attempt_count,
        "lease_token": f"lease-{row_id}",
        "event_key": f"event:{row_id}",
        "target_table": "sensor_readings",
        "columns": ["timestamp", "sensor_id", "sensor_type", "location_id", "value"],
        "rows": [[
            "2026-10-25T12:00:00Z",
            "sensor-1",
            "soil_moisture",
            "11111111-1111-4111-8111-111111111111",
            24.5,
        ]],
    }


@pytest.mark.parametrize(
    ("attempt_count", "expected_seconds"),
    [(1, 60), (2, 120), (3, 240), (6, 1920), (7, 3600), (8, 3600), (0, 60)],
)
def test_retry_delay_grows_exponentially_and_caps(attempt_count, expected_seconds):
    assert clickhouse_outbox._retry_delay_seconds(attempt_count) == expected_seconds


@pytest.mark.parametrize("attempt_count", [True, 1.5, "2"])
def test_retry_delay_rejects_non_integer_attempt_count(attempt_count):
    with pytest.raises(ValueError, match="integer"):
        clickhouse_outbox._retry_delay_seconds(attempt_count)


def test_finish_uses_the_computed_delay_and_commits_outcome():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True,)

    assert clickhouse_outbox_worker._finish(
        conn,
        "worker-1",
        {"id": "outbox-id", "lease_token": "lease-token"},
        success=False,
        error="offline",
        retry_delay_seconds=480,
    )

    statement, params = cursor.execute.call_args.args
    assert "kokonut_security.finish_clickhouse_outbox_delivery" in statement
    assert params == (
        "outbox-id", "worker-1", "lease-token", False, "offline", 480, False
    )
    conn.commit.assert_called_once()


def test_finish_can_permanently_dead_letter_invalid_projection():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True,)

    assert clickhouse_outbox_worker._finish(
        conn,
        "worker-1",
        {"id": "outbox-id", "lease_token": "lease-token"},
        success=False,
        error="projection contract rejected",
        permanent_failure=True,
    )

    statement, params = cursor.execute.call_args.args
    assert "kokonut_security.finish_clickhouse_outbox_delivery" in statement
    assert params[6] is True
    conn.commit.assert_called_once()


def test_enqueue_is_idempotent_and_stays_in_caller_transaction():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("outbox-id",)

    result = enqueue(
        conn,
        event_key="event:1",
        source_table="sensor_reading",
        source_id="reading-1",
        target_table="sensor_readings",
        columns=["id", "value"],
        rows=[["reading-1", 12.5]],
        payload_hash="a" * 64,
    )

    assert result == "outbox-id"
    conn.commit.assert_not_called()
    statement = conn.cursor.return_value.__enter__.return_value.execute.call_args.args[0]
    assert "ON CONFLICT (event_key)" in statement


@pytest.mark.parametrize("failure", ["database", "conflicting_projection"])
def test_enqueue_failure_has_a_distinct_transactional_error(failure):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    if failure == "database":
        cursor.execute.side_effect = RuntimeError("database failed with token enqueue-secret")
    else:
        cursor.fetchone.return_value = None

    with pytest.raises(OutboxEnqueueError) as error:
        enqueue(
            conn,
            event_key="event:1",
            source_table="sensor_reading",
            source_id="reading-1",
            target_table="sensor_readings",
            columns=["id", "value"],
            rows=[["reading-1", 12.5]],
            payload_hash="a" * 64,
        )

    expected = (
        "Could not enqueue the canonical ClickHouse projection"
        if failure == "database"
        else "Outbox event key conflicts with an existing projection"
    )
    assert str(error.value) == expected
    if failure == "database":
        assert error.value.__suppress_context__ is True
        assert "enqueue-secret" not in str(error.value)
    conn.commit.assert_not_called()


def test_compatibility_delivery_wrapper_ignores_shared_connection_and_routes_to_worker(
    monkeypatch,
):
    connection = MagicMock()
    result = {"claimed": 2, "delivered": 1, "failed": 1}
    run_once = MagicMock(return_value=result)
    monkeypatch.setattr(clickhouse_outbox_worker, "run_once", run_once)

    assert clickhouse_outbox.deliver_batch(connection, "compat-worker", 12) == result

    run_once.assert_called_once_with(worker_id="compat-worker", limit=12)
    connection.cursor.assert_not_called()
    connection.commit.assert_not_called()


def test_empty_claimed_batch_does_not_open_clickhouse_or_finish(monkeypatch):
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_clickhouse",
        lambda: pytest.fail("empty claimed batches must not open ClickHouse"),
    )
    finish = MagicMock()

    assert deliver_claimed_batch([], "worker-empty", finish) == {
        "claimed": 0,
        "delivered": 0,
        "failed": 0,
    }
    finish.assert_not_called()


def test_client_setup_failure_records_a_failed_outcome_for_each_claim(monkeypatch):
    rows = [_row("one"), _row("two", attempt_count=3)]
    finished = []
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: (_ for _ in ()).throw(OSError("offline")))

    result = deliver_claimed_batch(
        rows,
        "worker-setup",
        lambda row, **kwargs: finished.append((row["id"], kwargs)) or True,
    )

    assert result == {"claimed": 2, "delivered": 0, "failed": 2}
    assert finished == [
        ("one", {
            "success": False,
            "error": "client setup failed: OSError",
            "retry_delay_seconds": 60,
        }),
        ("two", {
            "success": False,
            "error": "client setup failed: OSError",
            "retry_delay_seconds": 240,
        }),
    ]


def test_missing_client_after_enabled_provider_records_setup_failure(monkeypatch):
    row = _row("one")
    finished = []
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: None)

    result = deliver_claimed_batch(
        [row],
        "worker-no-client",
        lambda got_row, **kwargs: finished.append((got_row["id"], kwargs)) or True,
    )

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert finished == [(
        "one",
        {
            "success": False,
            "error": "client setup failed: RuntimeError",
            "retry_delay_seconds": 60,
        },
    )]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_table", "users"),
        ("columns", ["timestamp", "sensor_id", "location_id", "value", "private_column"]),
        ("columns", ["timestamp", "sensor_id", "location_id", "value", "value"]),
        ("columns", ["timestamp", "sensor_id", "value"]),
        ("rows", [["only-one-value"]]),
    ],
)
def test_invalid_projection_is_dead_lettered_without_opening_clickhouse(
    monkeypatch, field, value
):
    row = _row("invalid")
    row[field] = value
    finished = []
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_clickhouse",
        lambda: pytest.fail("invalid projections must not open ClickHouse"),
    )

    result = deliver_claimed_batch(
        [row],
        "worker-invalid",
        lambda got_row, **kwargs: finished.append((got_row, kwargs)) or True,
    )

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert finished == [(
        row,
        {"success": False, "error": "projection contract rejected", "permanent_failure": True},
    )]


@pytest.mark.parametrize(
    ("target", "columns"),
    [
        ("attestation_events", ["timestamp", "attestation_uid", "chain", "subject_type"]),
        ("dlego_events", ["timestamp", "protocol_id", "chain", "action_type"]),
        ("remote_sensing_events", ["timestamp", "observation_id", "location_id", "source"]),
        ("sensor_readings", ["timestamp", "sensor_id", "location_id", "value"]),
        ("wallet_events", ["timestamp", "wallet_address", "chain", "tx_hash", "event_type"]),
        ("weather_events", ["timestamp", "location_id", "source"]),
    ],
)
def test_projection_contract_accepts_each_repository_target(target, columns):
    clickhouse_outbox._validate_outbox_projection(
        {"target_table": target, "columns": columns, "rows": [[None] * len(columns)]}
    )


def test_projection_contract_columns_exist_in_clickhouse_schema():
    schema_root = Path(__file__).resolve().parents[1] / "schemas" / "clickhouse"
    schema_sql = "\n".join(path.read_text(encoding="utf-8") for path in schema_root.glob("*.sql"))
    actual_columns: dict[str, set[str]] = {}

    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*ENGINE",
        schema_sql,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        table, definition = match.groups()
        actual_columns.setdefault(table, set()).update(
            column_match.group(1)
            for line in definition.splitlines()
            if (column_match := re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s+", line))
        )

    for match in re.finditer(
        r"ALTER TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+ADD COLUMN IF NOT EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)",
        schema_sql,
        flags=re.IGNORECASE,
    ):
        table, column = match.groups()
        actual_columns.setdefault(table, set()).add(column)

    for table, columns in clickhouse_outbox._PROJECTION_COLUMNS.items():
        assert table in actual_columns
        assert columns <= actual_columns[table], (table, sorted(columns - actual_columns[table]))


def test_setup_outcome_database_failure_propagates_without_retrying_finish(monkeypatch):
    rows = [_row("one"), _row("two")]
    finishes = []
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_clickhouse",
        lambda: (_ for _ in ()).throw(OSError("offline")),
    )

    def fail_finish(row, **_kwargs):
        finishes.append(row["id"])
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        deliver_claimed_batch(rows, "worker-setup", fail_finish)

    assert finishes == ["one"]


def test_partial_batch_sanitizes_delivery_errors_and_keeps_independent_outcomes(monkeypatch):
    rows = [_row("success"), _row("failure")]
    client = MagicMock()
    secret = "clickhouse-provider-secret"
    client.raw_insert.side_effect = [None, ConnectionError(f"https://ch.example/?token={secret}")]
    finished = []
    logger = MagicMock()
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)
    monkeypatch.setattr(clickhouse_outbox.logger, "warning", logger.warning)

    result = deliver_claimed_batch(
        rows,
        "worker-partial",
        lambda row, *, success, error, retry_delay_seconds: finished.append(
            (row["id"], success, error, retry_delay_seconds)
        ) or True,
    )

    assert result == {"claimed": 2, "delivered": 1, "failed": 1}
    assert [outcome[:2] for outcome in finished] == [("success", True), ("failure", False)]
    assert finished[1][2] == "ClickHouse delivery failed (ConnectionError)"
    assert secret not in str(finished[1])
    assert secret not in str(logger.warning.call_args)
    assert finished[1][3] == 60
    assert client.raw_insert.call_count == 2
    client.close.assert_called_once()


def test_completion_database_error_propagates_after_insert_without_second_finish(monkeypatch):
    client = MagicMock()
    finishes = []
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)

    def fail_finish(row, **_kwargs):
        finishes.append(row["id"])
        raise RuntimeError("completion database failed")

    with pytest.raises(RuntimeError, match="completion database failed"):
        deliver_claimed_batch([_row("one")], "worker-completion", fail_finish)

    assert client.raw_insert.call_count == 1
    assert finishes == ["one"]
    client.close.assert_called_once()


def test_successful_insert_with_lost_fence_counts_as_failed(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)
    finish = MagicMock(return_value=False)

    result = deliver_claimed_batch([_row("one")], "stale-worker", finish)

    assert result == {"claimed": 1, "delivered": 0, "failed": 1}
    assert finish.call_args.kwargs["success"] is True
    client.close.assert_called_once()


def test_client_close_failure_propagates_after_outcome_is_recorded(monkeypatch):
    client = MagicMock()
    client.close.side_effect = RuntimeError("client close failed")
    finish = MagicMock(return_value=True)
    monkeypatch.setattr(clickhouse_outbox, "get_clickhouse", lambda: client)

    with pytest.raises(RuntimeError, match="client close failed"):
        deliver_claimed_batch([_row("one")], "worker-close", finish)

    assert finish.call_args.kwargs["success"] is True
    client.close.assert_called_once()


def test_run_once_cli_exits_nonzero_when_any_projection_failed(capsys):
    with patch.object(
        clickhouse_outbox_worker,
        "run_once",
        return_value={"claimed": 1, "delivered": 0, "failed": 1},
    ) as run_once:
        with pytest.raises(SystemExit) as exc_info:
            clickhouse_outbox_worker.main(
                ["--run-once", "--worker-id", "worker-cli"]
            )

    assert exc_info.value.code == 1
    assert '"failed": 1' in capsys.readouterr().out
    run_once.assert_called_once_with("worker-cli", 100)


def test_run_once_cli_accepts_empty_or_successful_batch(capsys):
    with patch.object(
        clickhouse_outbox_worker,
        "run_once",
        return_value={"claimed": 0, "delivered": 0, "failed": 0},
    ) as run_once:
        assert clickhouse_outbox_worker.main(
            ["--run-once", "--worker-id", "worker-cli"]
        ) is None

    assert '"failed": 0' in capsys.readouterr().out
    run_once.assert_called_once_with("worker-cli", 100)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--replay-dead-letter", "row-1"],
        ["--dispose-dead-letter", "row-1"],
    ],
)
def test_operator_transition_cli_fails_closed_before_connection(
    monkeypatch, capsys, arguments
):
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_connection",
        lambda: pytest.fail("retired operator actions must fail before PostgreSQL opens"),
    )
    monkeypatch.setattr(sys, "argv", ["clickhouse-outbox", *arguments])

    with pytest.raises(SystemExit) as exc_info:
        clickhouse_outbox.main()

    assert exc_info.value.code == 2
    assert "authenticated Gateway operator" in capsys.readouterr().err


def test_operator_transition_command_fails_closed_before_connection(monkeypatch):
    monkeypatch.setattr(
        clickhouse_outbox,
        "get_connection",
        lambda: pytest.fail("retired operator actions must fail before PostgreSQL opens"),
    )

    with pytest.raises(ValueError, match="authenticated Gateway operator"):
        clickhouse_outbox.command(
            SimpleNamespace(
                replay_dead_letter="row-1",
                dispose_dead_letter=None,
                run_once=False,
                limit=100,
            )
        )
