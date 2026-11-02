"""Migration-backed stakeholder and cooperative views use fixed projections."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import services.analytics.cooperative_governance as cooperative_governance
import services.analytics.stakeholder_engagement as stakeholder_engagement

_ENGAGEMENT_COLUMNS = (
    "plan_id",
    "name",
    "status",
    "engagement_mode",
    "stakeholder_party_id",
    "stakeholder_name",
    "objective_count",
    "touchpoint_count",
    "commitment_count",
    "open_commitment_count",
    "fulfilled_commitment_count",
    "overdue_commitment_count",
    "outcome_count",
    "last_outcome_at",
    "scope_type",
    "scope_id",
)
_COMMITMENT_COLUMNS = (
    "commitment_id",
    "plan_id",
    "plan_name",
    "stakeholder_name",
    "owner_name",
    "title",
    "status",
    "due_at",
    "work_item_id",
    "work_item_status",
    "responsibility_id",
    "is_overdue",
    "outcome_count",
    "last_outcome_at",
)
_COOPERATIVE_COLUMNS = (
    "cooperative_id",
    "name",
    "active_member_count",
    "meeting_count",
    "open_proposal_count",
    "open_conflict_count",
    "pending_distribution_count",
)


def _connection(rows=(), row=None):
    connection = MagicMock()
    cursor_context = MagicMock()
    cursor = cursor_context.__enter__.return_value
    cursor.fetchall.return_value = list(rows)
    cursor.fetchone.return_value = row
    connection.cursor.return_value = cursor_context
    return connection, cursor


def _query(cursor):
    return " ".join(cursor.execute.call_args.args[0].split())


def _columns(query):
    projection = query.split(" FROM ", 1)[0].removeprefix("SELECT ")
    return tuple(column.strip() for column in projection.split(","))


def _engagement_row():
    plan_id = uuid4()
    party_id = uuid4()
    scope_id = uuid4()
    last_outcome_at = datetime(2026, 10, 29, 9, tzinfo=timezone.utc)
    row = {
        "plan_id": plan_id,
        "name": "Seasonal partner review",
        "status": "active",
        "engagement_mode": "collaborate",
        "stakeholder_party_id": party_id,
        "stakeholder_name": "Community group",
        "objective_count": 2,
        "touchpoint_count": 3,
        "commitment_count": 1,
        "open_commitment_count": 1,
        "fulfilled_commitment_count": 0,
        "overdue_commitment_count": 0,
        "outcome_count": 1,
        "last_outcome_at": last_outcome_at,
        "scope_type": "location",
        "scope_id": scope_id,
    }
    serialized = {
        **row,
        "plan_id": str(plan_id),
        "stakeholder_party_id": str(party_id),
        "scope_id": str(scope_id),
        "last_outcome_at": last_outcome_at.isoformat(),
    }
    return row, serialized


def _commitment_row():
    commitment_id = uuid4()
    plan_id = uuid4()
    work_item_id = uuid4()
    responsibility_id = uuid4()
    due_at = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    last_outcome_at = datetime(2026, 10, 29, 9, tzinfo=timezone.utc)
    row = {
        "commitment_id": commitment_id,
        "plan_id": plan_id,
        "plan_name": "Seasonal partner review",
        "stakeholder_name": "Community group",
        "owner_name": "Field coordinator",
        "title": "Share harvest estimate",
        "status": "open",
        "due_at": due_at,
        "work_item_id": work_item_id,
        "work_item_status": "in_progress",
        "responsibility_id": responsibility_id,
        "is_overdue": False,
        "outcome_count": 1,
        "last_outcome_at": last_outcome_at,
    }
    serialized = {
        **row,
        "commitment_id": str(commitment_id),
        "plan_id": str(plan_id),
        "work_item_id": str(work_item_id),
        "responsibility_id": str(responsibility_id),
        "due_at": due_at.isoformat(),
        "last_outcome_at": last_outcome_at.isoformat(),
    }
    return row, serialized, commitment_id, plan_id


@pytest.mark.parametrize(
    ("party_filter", "status_filter", "expected_params", "where"),
    [
        (None, None, [], ""),
        ("party-id", None, ["party-id"], " WHERE stakeholder_party_id = %s::uuid"),
        (None, "active", ["active"], " WHERE status = %s"),
        (
            "party-id",
            "active",
            ["party-id", "active"],
            " WHERE stakeholder_party_id = %s::uuid AND status = %s",
        ),
    ],
)
def test_engagement_summary_uses_migration_217_projection_and_filter_order(
    party_filter, status_filter, expected_params, where
):
    row, serialized = _engagement_row()
    connection, cursor = _connection(rows=[row])

    result = stakeholder_engagement.list_plans(
        connection, stakeholder_party_id=party_filter, status=status_filter
    )

    query = _query(cursor)
    assert _columns(query) == _ENGAGEMENT_COLUMNS
    assert query.endswith(f"FROM v_stakeholder_engagement_summary{where} ORDER BY name")
    assert cursor.execute.call_args.args[1] == expected_params
    assert result == [serialized]


def test_commitment_detail_uses_migration_216_projection_and_serializes_row():
    row, serialized, commitment_id, _plan_id = _commitment_row()
    connection, cursor = _connection(row=row)

    result = stakeholder_engagement.get_commitment(connection, str(commitment_id))

    query = _query(cursor)
    assert _columns(query) == _COMMITMENT_COLUMNS
    assert query.endswith(
        "FROM v_stakeholder_commitment_health WHERE commitment_id = %s::uuid"
    )
    assert cursor.execute.call_args.args[1] == (str(commitment_id),)
    assert result == serialized


@pytest.mark.parametrize(
    ("plan_filter", "overdue_only", "expected_params", "where"),
    [
        (None, False, [], ""),
        ("plan-id", False, ["plan-id"], " WHERE plan_id = %s::uuid"),
        (None, True, [], " WHERE is_overdue = TRUE"),
        (
            "plan-id",
            True,
            ["plan-id"],
            " WHERE plan_id = %s::uuid AND is_overdue = TRUE",
        ),
    ],
)
def test_commitment_health_list_uses_migration_216_projection_and_filters(
    plan_filter, overdue_only, expected_params, where
):
    row, serialized, _commitment_id, _plan_id = _commitment_row()
    connection, cursor = _connection(rows=[row])

    result = stakeholder_engagement.list_commitment_health(
        connection, plan_id=plan_filter, overdue_only=overdue_only
    )

    query = _query(cursor)
    assert _columns(query) == _COMMITMENT_COLUMNS
    assert query.endswith(
        f"FROM v_stakeholder_commitment_health{where} "
        "ORDER BY due_at NULLS LAST, title"
    )
    assert cursor.execute.call_args.args[1] == expected_params
    assert result == [serialized]


@pytest.mark.parametrize(
    ("cooperative_filter", "expected_params", "where"),
    [
        (None, [], ""),
        ("cooperative-id", ["cooperative-id"], " WHERE cooperative_id = %s::uuid"),
    ],
)
def test_cooperative_health_uses_migration_222_projection_and_scope(
    cooperative_filter, expected_params, where
):
    cooperative_id = uuid4()
    row = {
        "cooperative_id": cooperative_id,
        "name": "Kokonut growers cooperative",
        "active_member_count": 8,
        "meeting_count": 4,
        "open_proposal_count": 1,
        "open_conflict_count": 0,
        "pending_distribution_count": 2,
    }
    connection, cursor = _connection(rows=[row])

    result = cooperative_governance.governance_health(
        connection, cooperative_id=cooperative_filter
    )

    query = _query(cursor)
    assert _columns(query) == _COOPERATIVE_COLUMNS
    assert query.endswith(f"FROM v_cooperative_governance_health{where} ORDER BY name")
    assert cursor.execute.call_args.args[1] == expected_params
    assert result == [row]
