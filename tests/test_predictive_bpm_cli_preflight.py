"""Predictive BPM CLI numeric validation before database access."""

import sys
from unittest.mock import patch

import pytest

from services.analytics import predictive_bpm


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--age-hours", "nan"], "--age-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--age-hours", "inf"], "--age-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--age-hours", "-inf"], "--age-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--age-hours", "-1"], "--age-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--sla-target-hours", "nan"], "--sla-target-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--sla-target-hours", "-inf"], "--sla-target-hours"),
        (["predict", "--entity-type", "work_item", "--state", "submitted", "--sla-target-hours", "-1"], "--sla-target-hours"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "inf"], "--sla-target-hours"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "-1"], "--sla-target-hours"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "nan"], "--threshold"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "inf"], "--threshold"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "-0.1"], "--threshold"),
        (["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "1.1"], "--threshold"),
        (["persist", "--entity-type", "work_item", "--sla-target-hours", "nan"], "--sla-target-hours"),
        (["persist", "--entity-type", "work_item", "--sla-target-hours", "-1"], "--sla-target-hours"),
    ],
)
def test_invalid_numeric_inputs_fail_before_database(
    monkeypatch, arguments, message
):
    monkeypatch.setattr(sys, "argv", ["predictive-bpm", *arguments])

    with patch.object(predictive_bpm, "get_db") as get_db:
        with pytest.raises(SystemExit, match="2"):
            predictive_bpm.main()

    get_db.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            ["predict", "--entity-type", "work_item", "--state", "submitted", "--age-hours", "0", "--sla-target-hours", "0"],
            {"age_hours": 0.0, "sla_target_hours": 0.0},
        ),
        (
            ["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "0"],
            {"sla_target_hours": 0.0, "threshold": 0.0},
        ),
        (
            ["breaches", "--entity-type", "work_item", "--sla-target-hours", "0", "--threshold", "1"],
            {"sla_target_hours": 0.0, "threshold": 1.0},
        ),
        (
            ["persist", "--entity-type", "work_item", "--sla-target-hours", "0"],
            {"sla_target_hours": 0.0},
        ),
    ],
)
def test_valid_numeric_boundaries_dispatch(monkeypatch, arguments, expected):
    monkeypatch.setattr(sys, "argv", ["predictive-bpm", *arguments])

    with patch.object(predictive_bpm, "_cmd") as command:
        predictive_bpm.main()

    command.assert_called_once()
    parsed = command.call_args.args[0]
    for field, value in expected.items():
        assert getattr(parsed, field) == value
