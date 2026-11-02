"""Migration-backed query contract for operating capacity gaps."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.management import capacity_signals

EXPECTED_COLUMNS = (
    "scope_type",
    "scope_id",
    "work_type",
    "period_start",
    "period_end",
    "available_hours",
    "required_hours",
    "net_hours",
    "coverage_status",
    "priority_rank",
)


def _connection_with_rows(rows):
    connection = MagicMock()
    cursor_context = MagicMock()
    cursor = cursor_context.__enter__.return_value
    cursor.fetchall.return_value = rows
    connection.cursor.return_value = cursor_context
    return connection, cursor_context, cursor


@pytest.mark.parametrize(
    ("scope_type", "scope_id", "where", "params"),
    [
        (None, None, "", ()),
        ("internal", None, " WHERE scope_type = %s", ("internal",)),
        (
            None,
            "00000000-0000-0000-0000-000000002501",
            " WHERE scope_id = %s::uuid",
            ("00000000-0000-0000-0000-000000002501",),
        ),
        (
            "adelphi",
            "00000000-0000-0000-0000-000000002502",
            " WHERE scope_type = %s AND scope_id = %s::uuid",
            ("adelphi", "00000000-0000-0000-0000-000000002502"),
        ),
    ],
)
def test_list_gaps_uses_migration_251_projection_filters_and_order(
    scope_type, scope_id, where, params
):
    connection, cursor_context, cursor = _connection_with_rows([])

    result = capacity_signals.list_gaps(
        connection, scope_type=scope_type, scope_id=scope_id
    )

    assert result == []
    query, bound_params = cursor.execute.call_args.args
    normalized = " ".join(query.split())
    projection = normalized.split(" FROM ", 1)[0].removeprefix("SELECT ")
    assert tuple(column.strip() for column in projection.split(",")) == EXPECTED_COLUMNS
    assert normalized == (
        "SELECT "
        "scope_type, scope_id, work_type, period_start, period_end, "
        "available_hours, required_hours, net_hours, coverage_status, "
        f"priority_rank FROM v_operating_capacity_gap{where} "
        "ORDER BY period_start, priority_rank DESC, work_type"
    )
    assert bound_params == list(params)
    cursor_context.__exit__.assert_called_once_with(None, None, None)


def test_list_gaps_preserves_rows_and_serializes_scope_uuid():
    scope_id = uuid4()
    row = {
        "scope_type": "adelphi",
        "scope_id": scope_id,
        "work_type": "evidence_review",
        "period_start": date(2026, 7, 1),
        "period_end": date(2026, 7, 31),
        "available_hours": 14,
        "required_hours": 18,
        "net_hours": -4,
        "coverage_status": "gap",
        "priority_rank": 3,
    }
    connection, cursor_context, cursor = _connection_with_rows([row])

    result = capacity_signals.list_gaps(connection, scope_id=str(scope_id))

    assert result == [{**row, "scope_id": str(scope_id)}]
    assert cursor.execute.call_args.args[1] == [str(scope_id)]
    cursor_context.__exit__.assert_called_once_with(None, None, None)
