"""Stakeholder salience scores are checked before the CLI opens PostgreSQL."""

import sys
from unittest.mock import Mock

import pytest

from services.analytics import cli_stakeholders


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0.01", "10.01"])
def test_invalid_salience_score_fails_before_database(monkeypatch, value):
    monkeypatch.setattr(sys, "argv", [
        "kokonut-stakeholders", "salience", "party-id", "--rationale", "Test",
        "--power", value,
    ])
    get_db = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli_stakeholders, "get_db", get_db)

    with pytest.raises(SystemExit) as error:
        cli_stakeholders.main()

    assert error.value.code == 2
    get_db.assert_not_called()


@pytest.mark.parametrize("value", ["0", "10"])
def test_salience_score_boundaries_reach_service(monkeypatch, value):
    connection = Mock()
    get_db = Mock(return_value=connection)
    assess = Mock(return_value={"id": "assessment-id"})
    output = Mock()
    monkeypatch.setattr(sys, "argv", [
        "kokonut-stakeholders", "salience", "party-id", "--rationale", "Test",
        "--power", value,
    ])
    monkeypatch.setattr(cli_stakeholders, "get_db", get_db)
    monkeypatch.setattr(cli_stakeholders, "assess_salience", assess)
    monkeypatch.setattr(cli_stakeholders, "print_json", output)

    cli_stakeholders.main()

    assess.assert_called_once_with(
        connection,
        "party-id",
        interest_id=None,
        power=float(value),
        legitimacy=0,
        urgency=0,
        vulnerability=0,
        harm_exposure=0,
        representation=0,
        rationale="Test",
    )
    output.assert_called_once_with({"id": "assessment-id"})
    connection.close.assert_called_once_with()
