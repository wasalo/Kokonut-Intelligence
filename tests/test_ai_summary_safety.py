"""Draft validation must happen before persistence in the AI summary runner."""

from __future__ import annotations

from unittest import mock

import pytest

from services.agents import ai_summary


def test_run_ai_summary_does_not_store_invalid_output():
    conn = mock.Mock()
    generator = mock.Mock(
        return_value={
            "content": "synthetic summary",
            "source_tables": ["harvest_event"],
            "summary_type": "operations",
        }
    )
    with mock.patch.object(ai_summary, "get_pg", return_value=conn):
        with mock.patch.object(ai_summary, "validate_task_capabilities"):
            with mock.patch.object(ai_summary, "assert_agent_action_allowed"):
                with mock.patch.object(ai_summary, "_check_registry_backed", return_value=True):
                    with mock.patch.dict(ai_summary.GENERATORS, {"operations": generator}):
                        with mock.patch.object(
                            ai_summary, "validate_output", return_value=["bad summary"]
                        ):
                            with mock.patch.object(ai_summary, "store_summary") as store:
                                with pytest.raises(ValueError, match="bad summary"):
                                    ai_summary.run_ai_summary("location-1", "operations", store=True)

    store.assert_not_called()
    conn.close.assert_called_once_with()
