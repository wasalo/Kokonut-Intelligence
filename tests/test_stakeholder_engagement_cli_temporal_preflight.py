"""Mock-only CLI temporal validation before stakeholder-engagement DB access."""

import sys
from unittest.mock import Mock

import pytest

from services.analytics import cli_stakeholder_engagement as cli


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "argv",
    [
        ["add-objective", "plan", "Title", "Outcome", "--target-date", "not-a-date"],
        ["add-objective", "plan", "Title", "Outcome", "--target-date", "2023-02-29"],
        ["add-objective", "plan", "Title", "Outcome", "--target-date", "20261029"],
        ["schedule-touchpoint", "plan", "Purpose", "--scheduled-at", "not-a-time"],
        ["schedule-touchpoint", "plan", "Purpose", "--scheduled-at", "2026-02-30T12:00:00Z"],
        ["schedule-touchpoint", "plan", "Purpose", "--scheduled-at", "2026-10-29T12:00:00"],
        ["create-commitment", "plan", "Title", "--due-at", "not-a-time"],
        ["create-commitment", "plan", "Title", "--due-at", "2026-02-30T12:00:00Z"],
        ["create-commitment", "plan", "Title", "--due-at", "2026-10-29T12:00:00"],
    ],
)
def test_invalid_temporal_values_fail_before_database(monkeypatch, argv):
    database = Mock()
    monkeypatch.setattr(sys, "argv", ["stakeholder-engagement", *argv])
    monkeypatch.setattr(cli, "get_db", database)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    database.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "service_name", "expected_value"),
    [
        (
            ["add-objective", "plan", "Title", "Outcome", "--target-date", "2024-02-29"],
            "add_objective",
            "2024-02-29",
        ),
        (
            ["schedule-touchpoint", "plan", "Purpose", "--scheduled-at", "2026-10-29T12:30:00Z"],
            "schedule_touchpoint",
            "2026-10-29T12:30:00Z",
        ),
        (
            ["create-commitment", "plan", "Title", "--due-at", "2026-10-29T12:30:00-04:00"],
            "create_commitment",
            "2026-10-29T12:30:00-04:00",
        ),
    ],
)
def test_valid_temporal_values_are_forwarded_unchanged(
    monkeypatch, argv, service_name, expected_value
):
    database = _Connection()
    service = Mock(return_value={"ok": True})
    monkeypatch.setattr(sys, "argv", ["stakeholder-engagement", *argv])
    monkeypatch.setattr(cli, "get_db", lambda: database)
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(cli, service_name, service)

    cli.main()

    keyword = {
        "add_objective": "target_date",
        "schedule_touchpoint": "scheduled_at",
        "create_commitment": "due_at",
    }[service_name]
    assert service.call_args.kwargs[keyword] == expected_value
    assert database.closed


@pytest.mark.parametrize(
    ("argv", "service_name", "keyword"),
    [
        (["add-objective", "plan", "Title", "Outcome"], "add_objective", "target_date"),
        (["schedule-touchpoint", "plan", "Purpose"], "schedule_touchpoint", "scheduled_at"),
        (["create-commitment", "plan", "Title"], "create_commitment", "due_at"),
    ],
)
def test_omitted_optional_temporal_values_remain_none(
    monkeypatch, argv, service_name, keyword
):
    database = _Connection()
    service = Mock(return_value={"ok": True})
    monkeypatch.setattr(sys, "argv", ["stakeholder-engagement", *argv])
    monkeypatch.setattr(cli, "get_db", lambda: database)
    monkeypatch.setattr(cli, "_out", lambda _result: None)
    monkeypatch.setattr(cli, service_name, service)

    cli.main()

    assert service.call_args.kwargs[keyword] is None
    assert database.closed
