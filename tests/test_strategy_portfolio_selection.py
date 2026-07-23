"""Tests for constrained strategic portfolio selection."""

import uuid

from services.planning.strategy_allocation import optimize_candidates


def test_optimizer_respects_budget_and_dependencies():
    first = str(uuid.uuid4())
    second = str(uuid.uuid4())
    third = str(uuid.uuid4())
    result = optimize_candidates([
        {"id": first, "status": "scored", "estimated_cost": 8, "required_capacity_hours": 2, "composite_score": 40, "dependencies": []},
        {"id": second, "status": "scored", "estimated_cost": 5, "required_capacity_hours": 2, "composite_score": 60, "dependencies": [first]},
        {"id": third, "status": "scored", "estimated_cost": 4, "required_capacity_hours": 1, "composite_score": 55, "dependencies": []},
    ], budget_limit=9, capacity_limit=4)
    assert result["selected_ids"] == [third]
    assert result["used_budget"] == 4


def test_optimizer_returns_empty_for_empty_input():
    result = optimize_candidates([], budget_limit=100, capacity_limit=100)
    assert result["selected_ids"] == []
    assert result["deferred_ids"] == []
    assert result["objective_score"] == 0.0


def test_optimizer_selects_all_when_within_limits():
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    result = optimize_candidates([
        {"id": a, "status": "scored", "estimated_cost": 3, "required_capacity_hours": 2, "composite_score": 50, "dependencies": []},
        {"id": b, "status": "scored", "estimated_cost": 2, "required_capacity_hours": 1, "composite_score": 70, "dependencies": []},
    ], budget_limit=10, capacity_limit=10)
    assert set(result["selected_ids"]) == {a, b}
    assert result["used_budget"] == 5.0


def test_optimizer_respects_capacity_limit():
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    result = optimize_candidates([
        {"id": a, "status": "scored", "estimated_cost": 2, "required_capacity_hours": 5, "composite_score": 90, "dependencies": []},
        {"id": b, "status": "scored", "estimated_cost": 2, "required_capacity_hours": 3, "composite_score": 70, "dependencies": []},
    ], budget_limit=10, capacity_limit=5)
    assert result["selected_ids"] == [a]
    assert result["used_capacity_hours"] == 5.0


def test_optimizer_skips_non_eligible_statuses():
    a = str(uuid.uuid4())
    result = optimize_candidates([
        {"id": a, "status": "draft", "estimated_cost": 1, "required_capacity_hours": 1, "composite_score": 95, "dependencies": []},
    ], budget_limit=100, capacity_limit=100)
    assert result["selected_ids"] == []


def test_optimizer_chains_multi_level_dependencies():
    root = str(uuid.uuid4())
    mid = str(uuid.uuid4())
    leaf = str(uuid.uuid4())
    result = optimize_candidates([
        {"id": root, "status": "scored", "estimated_cost": 1, "required_capacity_hours": 1, "composite_score": 30, "dependencies": []},
        {"id": mid, "status": "scored", "estimated_cost": 1, "required_capacity_hours": 1, "composite_score": 50, "dependencies": [root]},
        {"id": leaf, "status": "scored", "estimated_cost": 1, "required_capacity_hours": 1, "composite_score": 80, "dependencies": [mid]},
    ], budget_limit=10, capacity_limit=10)
    assert set(result["selected_ids"]) == {root, mid, leaf}
