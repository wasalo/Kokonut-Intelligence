"""Value-stream performance queries preserve migration-backed view shape."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import services.analytics.value_stream_defs as value_stream_defs


def test_stream_performance_uses_exact_projection_and_preserves_rows(monkeypatch):
    expected_columns = (
        "stream_id",
        "stream_name",
        "stakeholder_type",
        "trigger_event",
        "end_state",
        "stream_status",
        "stage_id",
        "stage_name",
        "sequence_order",
        "process_key",
        "target_lead_time_hours",
        "target_fty_pct",
        "observation_count",
        "avg_lead_time_hours",
        "avg_fty_pct",
        "last_observed_at",
    )
    stream_id = uuid4()
    stage_id = uuid4()
    observed_at = datetime(2026, 10, 28, 12, 30, tzinfo=timezone.utc)
    row = {
        "stream_id": stream_id,
        "stream_name": "Harvest-to-market",
        "stakeholder_type": "farmer",
        "trigger_event": "harvest_ready",
        "end_state": "produce_sold",
        "stream_status": "active",
        "stage_id": stage_id,
        "stage_name": "Harvest",
        "sequence_order": 1,
        "process_key": "harvest",
        "target_lead_time_hours": Decimal("12.0"),
        "target_fty_pct": Decimal("95.0"),
        "observation_count": 3,
        "avg_lead_time_hours": Decimal("10.5"),
        "avg_fty_pct": Decimal("97.2"),
        "last_observed_at": observed_at,
    }
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor_context = MagicMock()
    cursor = cursor_context.__enter__.return_value
    cursor.fetchall.return_value = [row]
    connection.cursor.return_value = cursor_context
    monkeypatch.setattr(value_stream_defs, "_conn", lambda: connection)

    result = value_stream_defs.get_stream_performance(str(stream_id))

    query, params = cursor.execute.call_args.args
    normalized_query = " ".join(query.split())
    projection = normalized_query.split(" FROM ", 1)[0].removeprefix("SELECT ")
    assert tuple(column.strip() for column in projection.split(",")) == expected_columns
    assert "FROM v_value_stream_performance" in normalized_query
    assert "WHERE stream_id = %s::uuid" in normalized_query
    assert "ORDER BY sequence_order" in normalized_query
    assert params == (str(stream_id),)
    assert result == [
        {
            **row,
            "stream_id": str(stream_id),
            "stage_id": str(stage_id),
            "last_observed_at": observed_at.isoformat(),
        }
    ]
    cursor.execute.assert_called_once_with(query, (str(stream_id),))
