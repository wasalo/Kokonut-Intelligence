"""Focused tests for header-backed backcast milestone DAG behavior."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from services.threatcasting.backcasting import Backcaster


def test_local_keys_build_valid_dag():
    ids, dependencies = Backcaster._prepare_milestones([
        {"key": "foundation", "order": 1, "description": "Foundation"},
        {"key": "delivery", "order": 2, "description": "Delivery", "depends_on": ["foundation"]},
        {"order": 3, "description": "Review", "dependencies": ["delivery"]},
    ])
    assert dependencies[ids[0]] == []
    assert dependencies[ids[1]] == [ids[0]]
    assert dependencies[ids[2]] == [ids[1]]


@pytest.mark.parametrize("milestones, message", [
    ([{"order": 1, "description": "A", "depends_on": ["missing"]}], "Unknown"),
    ([{"key": "a", "order": 1, "description": "A", "depends_on": ["a"]}], "itself"),
    ([{"key": "a", "order": 1, "description": "A", "depends_on": ["b"]},
      {"key": "b", "order": 2, "description": "B", "depends_on": ["a"]}], "cycle"),
    ([{"order": 1, "description": "A"}, {"order": 1, "description": "B"}], "unique"),
    ([{"order": 0, "description": "A"}], "positive"),
])
def test_invalid_dags_are_rejected(milestones, message):
    with pytest.raises(ValueError, match=message):
        Backcaster._prepare_milestones(milestones)


def test_readiness_topology_and_critical_path():
    milestones = [
        {"id": "a", "milestone_order": 1, "milestone_status": "completed", "milestone_target_date": date(2026, 1, 1)},
        {"id": "b", "milestone_order": 2, "milestone_status": "pending", "milestone_target_date": date(2026, 1, 3)},
        {"id": "c", "milestone_order": 3, "milestone_status": "pending", "milestone_target_date": date(2026, 1, 5)},
    ]
    dependencies = [
        {"milestone_id": "b", "depends_on_milestone_id": "a"},
        {"milestone_id": "c", "depends_on_milestone_id": "b"},
    ]
    order, blocked_by, ready, critical = Backcaster._graph_details(milestones, dependencies)
    assert order == ["a", "b", "c"]
    assert ready["b"] is True
    assert blocked_by["c"] == ["b"]
    assert critical == ["a", "b", "c"]


def test_resolver_rejects_ambiguous_narrative_and_closes_cursor():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"id": "p1"}, {"id": "p2"}]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    backcaster = Backcaster(conn)
    with pytest.raises(ValueError, match="multiple backcast plans"):
        backcaster._resolve_plan_id("narrative")
    cursor.close.assert_called_once()


def test_transition_guard_rolls_back_when_dependency_unmet():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": "m2", "milestone_status": "pending"}
    cursor.fetchall.return_value = [{"depends_on_milestone_id": "m1"}]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    with pytest.raises(ValueError, match="dependencies are unmet"):
        Backcaster(conn).update_milestone("m2", status="in_progress")
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()


def test_delete_uses_only_resolved_header():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"id": "p1"}]
    cursor.rowcount = 1
    conn = MagicMock()
    conn.cursor.return_value = cursor
    assert Backcaster(conn).delete_plan("n1") is True
    delete_sql, params = cursor.execute.call_args_list[-1].args
    assert "WHERE id = %s" in delete_sql
    assert params == ("p1",)
    conn.commit.assert_called_once()


def test_create_plan_rolls_back_all_writes():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"location_id": "loc"}, RuntimeError("write failed")]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    with pytest.raises(RuntimeError, match="write failed"):
        Backcaster(conn).create_plan("n1", "loc", "Plan", "Future", "Gap", [
            {"key": "a", "order": 1, "description": "A"},
        ])
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
