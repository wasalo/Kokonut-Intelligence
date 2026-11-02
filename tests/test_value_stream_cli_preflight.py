"""Value-stream observation pagination is bounded before database access."""

import sys
from unittest.mock import Mock

import pytest

from services.analytics import cli_value_stream_defs, value_stream_defs


@pytest.mark.parametrize("limit", ["0", "-1", "501", "1.5"])
def test_invalid_observation_limit_fails_before_service(monkeypatch, limit):
    monkeypatch.setattr(sys, "argv", [
        "kokonut-value-streams", "observations", "stage-id", "--limit", limit,
    ])
    get_observations = Mock(side_effect=AssertionError("service must not be called"))
    monkeypatch.setattr(cli_value_stream_defs, "get_observations", get_observations)

    with pytest.raises(SystemExit) as error:
        cli_value_stream_defs.main()

    assert error.value.code == 2
    get_observations.assert_not_called()


@pytest.mark.parametrize("limit", [1, 500])
def test_observation_limit_boundaries_forward_unchanged(monkeypatch, capsys, limit):
    monkeypatch.setattr(sys, "argv", [
        "kokonut-value-streams", "observations", "stage-id", "--limit", str(limit),
    ])
    get_observations = Mock(return_value=[])
    monkeypatch.setattr(cli_value_stream_defs, "get_observations", get_observations)

    cli_value_stream_defs.main()

    get_observations.assert_called_once_with("stage-id", limit=limit)
    assert capsys.readouterr().out.strip() == "[]"


@pytest.mark.parametrize("limit", [True, 0, -1, 501, 1.5])
def test_service_rejects_invalid_observation_limit_before_opening_connection(
    monkeypatch, limit
):
    connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(value_stream_defs, "_conn", connection)

    with pytest.raises(ValueError, match="limit must be an integer between 1 and 500"):
        value_stream_defs.get_observations("stage-id", limit=limit)

    connection.assert_not_called()
