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
