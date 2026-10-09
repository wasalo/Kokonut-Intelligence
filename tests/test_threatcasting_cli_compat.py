"""Focused CLI and model compatibility tests for canonical backcast plans."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.threatcasting import cli
from services.threatcasting.models import BackcastMilestone, BackcastPlan, BackcastPlanHeader


def test_create_backcast_exposes_plan_id_and_preserves_milestones(capsys):
    milestone = {"id": "milestone-1", "plan_id": "plan-1", "milestone_order": 1}
    backcaster = MagicMock()
    backcaster.create_plan.return_value = [milestone]
    with patch("services.threatcasting.backcasting.Backcaster", return_value=backcaster), patch.object(
        cli, "_get_conn", return_value=MagicMock()
    ), patch.object(
        sys, "argv", ["threatcasting", "create-backcast", "--narrative-id", "n1", "--location-id", "l1",
        "--name", "Plan", "--future-state", "Future", "--gaps", "Gap", "--milestones",
        '[{"order":1,"description":"First"}]']
    ):
        cli.main()
    assert json.loads(capsys.readouterr().out) == {"plan_id": "plan-1", "milestones": [milestone]}


@pytest.mark.parametrize("option", ["--plan-id", "--narrative-id"])
def test_backcast_progress_accepts_one_identifier(option, capsys):
    backcaster = MagicMock()
    backcaster.get_progress.return_value = {"plan_id": "plan-1"}
    with patch("services.threatcasting.backcasting.Backcaster", return_value=backcaster), patch.object(
        cli, "_get_conn", return_value=MagicMock()
    ), patch.object(
        sys, "argv", ["threatcasting", "backcast-progress", option, "identifier"]
    ):
        cli.main()
    backcaster.get_progress.assert_called_once_with("identifier")
    assert json.loads(capsys.readouterr().out)["plan_id"] == "plan-1"


@pytest.mark.parametrize("arguments", [[], ["--plan-id", "p1", "--narrative-id", "n1"]])
def test_backcast_progress_requires_exactly_one_identifier(arguments):
    with patch.object(sys, "argv", ["threatcasting", "backcast-progress", *arguments]):
        with pytest.raises(SystemExit):
            cli.main()


def test_normalized_models_coexist_with_flattened_model():
    header = BackcastPlanHeader(narrative_id="n1", location_id="l1", plan_name="Plan",
                                future_state_description="Future", current_gap_analysis="Gap")
    milestone = BackcastMilestone(plan_id=header.id, milestone_order=1, milestone_description="First")
    flattened = BackcastPlan(narrative_id="n1", location_id="l1", plan_name="Plan",
                             future_state_description="Future", current_gap_analysis="Gap",
                             milestone_order=1, milestone_description="First")
    assert milestone.plan_id == header.id
    assert flattened.milestone_status == "pending"
