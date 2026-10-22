"""Draft validation must happen before persistence in the AI summary runner."""

from __future__ import annotations

from unittest import mock

import pytest

from services.agents import ai_summary

LOCATION_ID = "a0000000-0000-4000-8000-000000000001"
REQUEST_ID = "a0000000-0000-4000-8000-000000000002"


def test_store_summary_rejects_malformed_location_before_cursor_access():
    conn = mock.Mock()
    with mock.patch.object(ai_summary, "assert_agent_action_allowed") as safety:
        with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
            ai_summary.store_summary(
                conn, "not-a-uuid", "operations", "draft", [], request_id=REQUEST_ID
            )

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
            request_id=REQUEST_ID,
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
            request_id=REQUEST_ID,
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
                request_id=REQUEST_ID,
            )

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    safety.assert_not_called()


def test_store_summary_propagates_signed_worker_failure_without_using_shared_connection():
    conn = mock.Mock()
    failure = RuntimeError("worker write failed")

    with mock.patch.object(ai_summary, "create_worker_ai_summary_draft", side_effect=failure) as writer:
        with pytest.raises(RuntimeError, match="worker write failed"):
            ai_summary.store_summary(
                conn,
                LOCATION_ID,
                "operations",
                "synthetic draft",
                ["harvest_event"],
                request_id=REQUEST_ID,
            )

    writer.assert_called_once()
    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_store_summary_uses_worker_identity_and_keeps_shared_connection_unused():
    conn = mock.Mock()

    with mock.patch.object(
        ai_summary,
        "create_worker_ai_summary_draft",
        return_value={"summary_id": "stored-id"},
    ) as writer:
        result = ai_summary.store_summary(
            conn,
            LOCATION_ID,
            "operations",
            "synthetic draft",
            ["harvest_event"],
            request_id=REQUEST_ID,
            source_references={
                "harvest_event": {"record_ids": [LOCATION_ID], "row_count": 1, "truncated": False}
            },
        )

    assert result == "stored-id"
    writer.assert_called_once_with(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        {
            "content": "synthetic draft",
            "source_tables": ["harvest_event"],
            "source_references": {
                "harvest_event": {"record_ids": [LOCATION_ID], "row_count": 1, "truncated": False}
            },
            "model_version": "rules-v1",
        },
    )
    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_run_ai_summary_store_uses_worker_path_before_shared_database(monkeypatch):
    saved = {
        "summary_id": "stored-id",
        "content": "synthetic summary",
        "source_tables": ["harvest_event"],
        "source_references": {},
        "replayed": False,
    }
    monkeypatch.setattr(
        ai_summary,
        "get_pg",
        lambda: pytest.fail("stored summary must use the signed worker path"),
    )
    from services.agents import worker_cli

    with mock.patch.object(worker_cli, "run_worker_summary", return_value=saved) as run_worker:
        result = ai_summary.run_ai_summary(
            LOCATION_ID, "operations", store=True, request_id=REQUEST_ID
        )

    run_worker.assert_called_once_with(LOCATION_ID, "operations", REQUEST_ID)
    assert result["ai_summary_id"] == "stored-id"
    assert result["summary"]["source_references"] == {}


def test_run_ai_summary_read_only_uses_signed_source_path_before_shared_database(monkeypatch):
    monkeypatch.setattr(
        ai_summary,
        "get_pg",
        lambda: pytest.fail("read-only summary must not use shared runtime DB"),
    )
    from services.agents import worker_cli

    expected = {"summary": {"content": "synthetic read-only summary"}}
    with mock.patch.object(worker_cli, "run_worker_summary", return_value=expected) as run_worker:
        result = ai_summary.run_ai_summary(LOCATION_ID, "operations", store=False)

    run_worker.assert_called_once_with(
        LOCATION_ID,
        "operations",
        None,
        persist_draft=False,
    )
    assert result is expected
