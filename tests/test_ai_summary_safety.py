"""Draft validation must happen before persistence in the AI summary runner."""

from __future__ import annotations

from unittest import mock

import pytest

from services.agents import ai_summary


def test_store_summary_rejects_malformed_location_before_cursor_access():
    conn = mock.Mock()
    with mock.patch.object(ai_summary, "assert_agent_action_allowed") as safety:
        with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
            ai_summary.store_summary(conn, "not-a-uuid", "operations", "draft", [])

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    safety.assert_not_called()


def test_store_summary_rejects_invalid_content_before_cursor_access():
    conn = mock.Mock()
    with pytest.raises(ValueError, match="non-empty string"):
        ai_summary.store_summary(
            conn,
            "a0000000-0000-4000-8000-000000000001",
            "operations",
            "   ",
            ["harvest_event"],
        )

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_store_summary_rejects_overlong_content_before_cursor_access():
    conn = mock.Mock()
    with pytest.raises(ValueError, match="at most 20000 characters"):
        ai_summary.store_summary(
            conn,
            "a0000000-0000-4000-8000-000000000001",
            "operations",
            "x" * 20_001,
            ["harvest_event"],
        )

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


@pytest.mark.parametrize(
    "source_tables",
    [
        [],
        [f"table_{index}" for index in range(21)],
        ["harvest_event", "not-valid"],
    ],
)
def test_store_summary_rejects_invalid_source_tables_before_cursor_access(source_tables):
    conn = mock.Mock()
    with mock.patch.object(ai_summary, "assert_agent_action_allowed") as safety:
        with pytest.raises(ValueError, match="source_tables must contain 1 to 20"):
            ai_summary.store_summary(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "operations",
                "synthetic draft",
                source_tables,
            )

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    safety.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["execute", "fetchone"])
def test_store_summary_closes_cursor_and_does_not_commit_on_persistence_failure(
    failure_stage,
):
    conn = mock.Mock()
    cursor = conn.cursor.return_value
    failure = RuntimeError(f"{failure_stage} failed")
    if failure_stage == "execute":
        cursor.execute.side_effect = failure
    else:
        cursor.fetchone.side_effect = failure

    with pytest.raises(RuntimeError, match=f"{failure_stage} failed"):
        ai_summary.store_summary(
            conn,
            "a0000000-0000-4000-8000-000000000001",
            "operations",
            "synthetic draft",
            ["harvest_event"],
        )

    cursor.close.assert_called_once_with()
    conn.commit.assert_not_called()


def test_store_summary_validates_and_commits_a_draft():
    conn = mock.Mock()
    conn.cursor.return_value.fetchone.return_value = ("stored-id",)

    result = ai_summary.store_summary(
        conn,
        "a0000000-0000-4000-8000-000000000001",
        "operations",
        "synthetic draft",
        ["harvest_event"],
    )

    assert result == "stored-id"
    conn.cursor.return_value.execute.assert_called_once()
    conn.commit.assert_called_once_with()


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
                                    ai_summary.run_ai_summary(
                                        "a0000000-0000-4000-8000-000000000001",
                                        "operations",
                                        store=True,
                                    )

    store.assert_not_called()
    conn.close.assert_called_once_with()
