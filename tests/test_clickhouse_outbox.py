from unittest.mock import MagicMock, patch

from services.ingestion.clickhouse_outbox import enqueue


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


@patch("services.ingestion.clickhouse_outbox.get_clickhouse")
def test_unavailable_clickhouse_does_not_claim_success(mock_client):
    mock_client.return_value = None
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.description = []
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    from services.ingestion.clickhouse_outbox import deliver_batch

    assert deliver_batch(conn, "worker-1") == {"claimed": 0, "delivered": 0, "failed": 0}
