"""Offline checks for the database-independent EAS GraphQL adapter."""

from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.eas_provider import (
    EASProviderQueryError,
    execute_eas_query,
)


def test_execute_query_returns_data_and_closes_response():
    response = MagicMock()
    response.json.return_value = {"data": {"attestations": [{"id": "uid"}]}}

    with patch("services.ingestion.eas_provider.http.post", return_value=response) as post:
        result = execute_eas_query("celo", "query Example", {"recipient": "0xabc"})

    assert result == {"attestations": [{"id": "uid"}]}
    post.assert_called_once_with(
        "https://celo.easscan.org/graphql",
        json={"query": "query Example", "variables": {"recipient": "0xabc"}},
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    response.close.assert_called_once_with()


@pytest.mark.parametrize(
    "payload, expected_message",
    [
        ({"errors": [{"message": "private upstream detail"}], "data": None}, "EAS GraphQL query failed"),
        ({"errors": [{"message": "partial failure"}], "data": {"attestations": []}}, "EAS GraphQL query failed"),
        ({"data": None}, "EAS provider response has no data object"),
        ([{"data": {}}], "EAS provider returned an invalid response"),
    ],
)
def test_execute_query_rejects_graphql_errors_and_invalid_payloads(payload, expected_message):
    response = MagicMock()
    response.json.return_value = payload

    with (
        patch("services.ingestion.eas_provider.http.post", return_value=response),
        pytest.raises(EASProviderQueryError, match=expected_message) as exc_info,
    ):
        execute_eas_query("celo", "query Example", {})

    assert "private upstream detail" not in str(exc_info.value)
    response.close.assert_called_once_with()


def test_execute_query_rejects_invalid_json_and_closes_response():
    response = MagicMock()
    response.json.side_effect = ValueError("not json")

    with (
        patch("services.ingestion.eas_provider.http.post", return_value=response),
        pytest.raises(EASProviderQueryError, match="EAS provider returned invalid JSON"),
    ):
        execute_eas_query("celo", "query Example", {})

    response.close.assert_called_once_with()


def test_http_status_failure_propagates_and_closes_response():
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("http failure")

    with (
        patch("services.ingestion.eas_provider.http.post", return_value=response),
        pytest.raises(RuntimeError, match="http failure"),
    ):
        execute_eas_query("celo", "query Example", {})

    response.json.assert_not_called()
    response.close.assert_called_once_with()
