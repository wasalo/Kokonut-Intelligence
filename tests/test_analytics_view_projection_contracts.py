"""Stable analytics view projections match their defining migrations."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import services.analytics.coordination as coordination
import services.analytics.value_stream_defs as value_stream_defs


def _connection_with_rows(rows):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor_context = MagicMock()
    cursor = cursor_context.__enter__.return_value
    cursor.fetchall.return_value = rows
    connection.cursor.return_value = cursor_context
    return connection, cursor


def _projection(query):
    normalized = " ".join(query.split())
    projection = normalized.split(" FROM ", 1)[0].removeprefix("SELECT ")
    return normalized, tuple(column.strip() for column in projection.split(","))


def test_value_stream_summary_uses_migration_210_projection_and_serializes_rows(
    monkeypatch,
):
    expected_columns = (
        "stream_id",
        "stream_name",
        "stakeholder_type",
        "status",
        "stage_count",
        "total_target_lead_time_hours",
        "avg_actual_lead_time_hours",
        "avg_fty_pct",
        "created_at",
        "updated_at",
    )
    stream_id = uuid4()
    created_at = datetime(2026, 10, 28, 12, 30, tzinfo=timezone.utc)
    updated_at = datetime(2026, 10, 29, 8, 15, tzinfo=timezone.utc)
    row = {
        "stream_id": stream_id,
        "stream_name": "Harvest-to-market",
        "stakeholder_type": "farmer",
        "status": "active",
        "stage_count": 4,
        "total_target_lead_time_hours": Decimal("24.0"),
        "avg_actual_lead_time_hours": Decimal("20.5"),
        "avg_fty_pct": Decimal("96.0"),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    connection, cursor = _connection_with_rows([row])
    monkeypatch.setattr(value_stream_defs, "_conn", lambda: connection)

    result = value_stream_defs.get_stream_summary()

    (query,) = cursor.execute.call_args.args
    normalized, columns = _projection(query)
    assert columns == expected_columns
    assert "FROM v_value_stream_summary ORDER BY stream_name" in normalized
    assert cursor.execute.call_args.kwargs == {}
    assert result == [
        {
            **row,
            "stream_id": str(stream_id),
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
        }
    ]


def test_coordination_health_uses_migration_235_projection_and_optional_scope(
    monkeypatch,
):
    expected_columns = (
        "alliance_id",
        "name",
        "coordination_type",
        "status",
        "active_participant_count",
        "active_objective_count",
        "contribution_count",
        "benefit_count",
        "open_risk_count",
        "completed_exchange_count",
        "latest_review_end",
    )
    alliance_id = uuid4()
    latest_review_end = date(2026, 10, 29)
    row = {
        "alliance_id": alliance_id,
        "name": "Regional learning network",
        "coordination_type": "alliance",
        "status": "active",
        "active_participant_count": 6,
        "active_objective_count": 3,
        "contribution_count": 5,
        "benefit_count": 2,
        "open_risk_count": 1,
        "completed_exchange_count": 4,
        "latest_review_end": latest_review_end,
    }
    connection, cursor = _connection_with_rows([row])
    monkeypatch.setattr(coordination, "_conn", lambda: connection)

    result = coordination.get_coordination_health(str(alliance_id))

    query, params = cursor.execute.call_args.args
    normalized, columns = _projection(query)
    assert columns == expected_columns
    assert "FROM v_coordination_health WHERE alliance_id = %s::uuid " in normalized
    assert normalized.endswith("ORDER BY name")
    assert params == [str(alliance_id)]
    assert result == [{**row, "alliance_id": str(alliance_id), "latest_review_end": str(latest_review_end)}]


def test_coordination_health_preserves_unfiltered_empty_result(monkeypatch):
    connection, cursor = _connection_with_rows([])
    monkeypatch.setattr(coordination, "_conn", lambda: connection)

    result = coordination.get_coordination_health()

    query, params = cursor.execute.call_args.args
    normalized, _columns = _projection(query)
    assert "FROM v_coordination_health ORDER BY name" in normalized
    assert "WHERE" not in normalized
    assert params == []
    assert result == []
