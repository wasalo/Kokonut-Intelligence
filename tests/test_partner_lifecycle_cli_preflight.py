"""Partner scorecard date inputs fail closed before database acquisition."""

import sys
from unittest.mock import Mock

import pytest

from services.analytics import partner_lifecycle


def _scorecard_argv(period_start: str, period_end: str) -> list[str]:
    return [
        "partner-lifecycle",
        "scorecard",
        "--lifecycle-id",
        "lifecycle-1",
        "--partner-id",
        "partner-1",
        "--period-start",
        period_start,
        "--period-end",
        period_end,
    ]


@pytest.mark.parametrize(
    "period_start",
    ["not-a-date", "2026-1-01", "20261001", "2026-02-30", "2026-13-01"],
)
def test_scorecard_rejects_noncanonical_or_impossible_start_before_database(
    monkeypatch, capsys, period_start
):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(partner_lifecycle, "get_db", get_db)
    monkeypatch.setattr(
        sys, "argv", _scorecard_argv(period_start, "2026-10-31")
    )

    with pytest.raises(SystemExit) as error:
        partner_lifecycle.main()

    assert error.value.code == 2
    assert "--period-start" in capsys.readouterr().err
    get_db.assert_not_called()


@pytest.mark.parametrize(
    "period_end",
    ["not-a-date", "2026-1-31", "20261031", "2026-02-30", "2026-13-01"],
)
def test_scorecard_rejects_noncanonical_or_impossible_end_before_database(
    monkeypatch, capsys, period_end
):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(partner_lifecycle, "get_db", get_db)
    monkeypatch.setattr(
        sys, "argv", _scorecard_argv("2026-10-01", period_end)
    )

    with pytest.raises(SystemExit) as error:
        partner_lifecycle.main()

    assert error.value.code == 2
    assert "--period-end" in capsys.readouterr().err
    get_db.assert_not_called()


def test_scorecard_rejects_reversed_period_before_database(monkeypatch, capsys):
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(partner_lifecycle, "get_db", get_db)
    monkeypatch.setattr(
        sys, "argv", _scorecard_argv("2026-11-01", "2026-10-31")
    )

    with pytest.raises(SystemExit) as error:
        partner_lifecycle.main()

    assert error.value.code == 2
    assert "period-start must be on or before --period-end" in capsys.readouterr().err
    get_db.assert_not_called()


def test_scorecard_passes_valid_period_dates_unchanged(monkeypatch):
    connection = Mock()
    get_db = Mock(return_value=connection)
    create_scorecard = Mock(return_value={"id": "scorecard-1"})
    print_json = Mock()
    monkeypatch.setattr(partner_lifecycle, "get_db", get_db)
    monkeypatch.setattr(partner_lifecycle, "create_scorecard", create_scorecard)
    monkeypatch.setattr(partner_lifecycle, "print_json", print_json)
    monkeypatch.setattr(
        sys, "argv", _scorecard_argv("2026-10-01", "2026-10-31")
    )

    partner_lifecycle.main()

    args, kwargs = create_scorecard.call_args
    assert args[:5] == (
        connection,
        "lifecycle-1",
        "partner-1",
        "2026-10-01",
        "2026-10-31",
    )
    assert kwargs == {
        "deliveries_on_time_pct": 0,
        "quality_score": 0,
        "responsiveness_score": 0,
        "cost_competitiveness": 0,
        "innovation_score": 0,
        "incidents": 0,
        "notes": None,
        "graded_by": None,
    }
    print_json.assert_called_once_with({"id": "scorecard-1"})
    connection.close.assert_called_once_with()


def test_non_scorecard_command_still_uses_its_existing_path(monkeypatch):
    connection = Mock()
    get_db = Mock(return_value=connection)
    get_lifecycle = Mock(return_value={"id": "lifecycle-1"})
    print_json = Mock()
    monkeypatch.setattr(partner_lifecycle, "get_db", get_db)
    monkeypatch.setattr(partner_lifecycle, "get_lifecycle", get_lifecycle)
    monkeypatch.setattr(partner_lifecycle, "print_json", print_json)
    monkeypatch.setattr(
        sys,
        "argv",
        ["partner-lifecycle", "get", "--lifecycle-id", "lifecycle-1"],
    )

    partner_lifecycle.main()

    get_db.assert_called_once_with()
    get_lifecycle.assert_called_once_with(connection, "lifecycle-1")
    print_json.assert_called_once_with({"id": "lifecycle-1"})
    connection.close.assert_called_once_with()
