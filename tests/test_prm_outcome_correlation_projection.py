"""PRM outcome-correlation view reads retain an explicit migration-backed shape."""

from __future__ import annotations

from unittest.mock import MagicMock

import services.analytics.prm_metrics as prm_metrics


def test_outcome_correlation_uses_exact_projection_and_preserves_rows(monkeypatch):
    expected_columns = (
        "process_key",
        "process_name",
        "maturity_level",
        "maturity_name",
        "metric_count",
        "avg_metric_value",
        "location_count",
        "scope",
    )
    maturity_row = {
        "process_key": "soil-restoration",
        "process_name": "Soil restoration",
        "maturity_level": 3,
        "maturity_name": "Established",
        "metric_count": None,
        "avg_metric_value": None,
        "location_count": None,
        "scope": "process_maturity",
    }
    portfolio_row = {
        "process_key": None,
        "process_name": None,
        "maturity_level": None,
        "maturity_name": "Portfolio-wide verified metrics",
        "metric_count": 4,
        "avg_metric_value": None,
        "location_count": 2,
        "scope": "portfolio_metrics",
    }
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor_context = MagicMock()
    cursor = cursor_context.__enter__.return_value
    cursor.fetchall.return_value = [maturity_row, portfolio_row]
    connection.cursor.return_value = cursor_context
    monkeypatch.setattr(prm_metrics, "_conn", lambda: connection)

    result = prm_metrics.outcome_correlation()

    sql = " ".join(cursor.execute.call_args.args[0].split())
    projection = sql.split(" FROM ", 1)[0].removeprefix("SELECT ")
    assert tuple(column.strip() for column in projection.split(",")) == expected_columns
    assert "FROM v_process_outcome_correlation" in sql
    assert "ORDER BY CASE scope" in sql
    assert "process_key NULLS LAST, maturity_level NULLS LAST" in sql
    assert result == [maturity_row, portfolio_row]
    assert result[0]["scope"] == "process_maturity"
    assert result[0]["metric_count"] is None
    assert result[0]["avg_metric_value"] is None
    assert result[1]["scope"] == "portfolio_metrics"
    assert result[1]["avg_metric_value"] is None
    cursor.execute.assert_called_once_with(cursor.execute.call_args.args[0])
