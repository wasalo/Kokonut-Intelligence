"""Failure-injection tests for ClickHouse ingestion writes."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import base
from services.ingestion.base import retry


def test_http_insert_keeps_malicious_values_out_of_query_text():
    response = MagicMock()
    with patch("requests.post", return_value=response) as post:
        assert base.post_clickhouse_rows(
            "sensor_readings",
            ["sensor_id", "metadata"],
            [["x'); DROP TABLE sensor_readings; --", {"note": "'quoted'"}]],
        )

    query = post.call_args.kwargs["params"]["query"]
    payload = post.call_args.kwargs["data"].decode()
    assert "DROP TABLE" not in query
    assert "x'); DROP TABLE sensor_readings; --" in payload
    response.close.assert_called_once()


def test_http_insert_closes_response_after_partial_failure():
    response = MagicMock()
    response.raise_for_status.side_effect = ConnectionError("connection dropped")
    with patch("requests.post", return_value=response):
        with pytest.raises(ConnectionError):
            base.post_clickhouse_rows("sensor_readings", ["sensor_id"], [["sensor-1"]])
    response.close.assert_called_once()


def test_native_insert_closes_client_when_insert_fails():
    client = MagicMock()
    client.insert.side_effect = ConnectionError("write failed")
    with patch.object(base, "get_clickhouse", return_value=client):
        with pytest.raises(ConnectionError):
            base.insert_clickhouse_rows("sensor_readings", ["sensor_id"], [["sensor-1"]])
    client.close.assert_called_once()


def test_transient_http_write_can_be_retried_without_reusing_response():
    response = MagicMock()
    with patch("requests.post", side_effect=[ConnectionError("temporary outage"), response]) as post:
        write = retry(max_retries=2, backoff=0, jitter=0)(
            lambda: base.post_clickhouse_rows("sensor_readings", ["sensor_id"], [["sensor-1"]])
        )
        assert write()
    assert post.call_count == 2
    response.close.assert_called_once()


def test_http_insert_rejects_dynamic_identifiers_before_network_call():
    with patch("requests.post") as post:
        with pytest.raises(ValueError):
            base.post_clickhouse_rows("sensor_readings; DROP TABLE x", ["sensor_id"], [["x"]])
    post.assert_not_called()
