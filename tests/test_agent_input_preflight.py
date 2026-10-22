"""Agent task inputs are checked before database work starts."""

from unittest import mock

import pytest

from services.agents import (
    ai_summary,
    cids_agent,
    delphi_facilitator_agent,
    ebf_calibration_agent,
    ebf_scorecard_agent,
    worker_cli,
)


def test_ai_summary_rejects_malformed_location_before_database_access() -> None:
    with mock.patch.object(ai_summary, "get_pg", side_effect=AssertionError("database opened")):
        with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
            ai_summary.run_ai_summary("not-a-uuid")


def test_cids_export_rejects_malformed_location_before_database_access() -> None:
    with mock.patch.object(
        worker_cli, "get_worker_db", side_effect=AssertionError("database opened")
    ):
        with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
            cids_agent.run_cids_export("not-a-uuid")


def test_scorecard_rejects_invalid_period_before_processing() -> None:
    with pytest.raises(ValueError, match="Invalid task input format for field: period_start"):
        ebf_scorecard_agent.draft_scorecard(
            "a0000000-0000-4000-8000-000000000001", "2026-W01-1", "2026-12-31"
        )


def test_calibration_rejects_malformed_session_before_processing() -> None:
    with pytest.raises(ValueError, match="Invalid task input format for field: session_id"):
        ebf_calibration_agent.draft_calibration_memo("not-a-uuid")


def test_delphi_rejects_malformed_study_before_facilitator_creation() -> None:
    with mock.patch.object(
        delphi_facilitator_agent,
        "Facilitator",
        side_effect=AssertionError("facilitator initialized"),
    ) as facilitator:
        with pytest.raises(ValueError, match="Invalid task input format for field: study_id"):
            delphi_facilitator_agent.run_delphi_facilitation("not-a-uuid")
    facilitator.assert_not_called()
