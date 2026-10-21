"""Offline contract checks for the signed AI-summary worker entry point."""

import json
import sys
from unittest.mock import MagicMock

import pytest

from services.agents import worker_cli

LOCATION_ID = "00000000-0000-0000-0000-000000000123"
REQUEST_ID = "00000000-0000-0000-0000-000000000456"


def test_worker_cli_replays_before_opening_source_database():
    prior = {"summary_id": "saved-id", "replayed": True}
    connection_factory = MagicMock(side_effect=AssertionError("source DB must not open"))
    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "combined",
        REQUEST_ID,
        connection_factory=connection_factory,
        existing_reader=lambda *_args: prior,
    )

    assert result is prior
    connection_factory.assert_not_called()


def test_worker_cli_reads_only_and_sends_lineage_through_signed_writer():
    cursor = MagicMock()
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    summary = {
        "content": "Synthetic summary",
        "source_tables": ["harvest_event"],
        "source_references": {
            "harvest_event": {"record_ids": [LOCATION_ID], "row_count": 1, "truncated": False}
        },
    }
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})

    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        connection_factory=lambda: connection,
        summary_builder=lambda *_args: summary,
        existing_reader=lambda *_args: None,
        draft_writer=writer,
    )

    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    writer.assert_called_once_with(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        {**summary, "model_version": "rules-v1"},
    )
    assert result == {"summary_id": "saved-id", "replayed": False}


def test_worker_cli_does_not_write_after_source_generation_failure():
    connection = MagicMock()
    writer = MagicMock()

    with pytest.raises(RuntimeError, match="source query failed"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "combined",
            REQUEST_ID,
            connection_factory=lambda: connection,
            summary_builder=MagicMock(side_effect=RuntimeError("source query failed")),
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    connection.close.assert_called_once_with()
    connection.rollback.assert_called_once_with()
    writer.assert_not_called()


def test_cli_output_does_not_print_summary_content_or_source_references(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--summary-type",
            "operations",
            "--request-id",
            REQUEST_ID,
        ],
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary",
        lambda *_args: {
            "summary_id": "saved-id",
            "resulting_status": "draft",
            "replayed": False,
            "content": "private farm summary",
            "source_references": {"harvest_event": {"record_ids": [LOCATION_ID]}},
        },
    )

    worker_cli.main()

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "summary_id": "saved-id",
        "resulting_status": "draft",
        "replayed": False,
    }
    assert "private farm summary" not in output
    assert LOCATION_ID not in output
