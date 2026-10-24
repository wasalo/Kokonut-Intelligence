"""CLI-level fail-closed checks for destructive data retention."""

from unittest.mock import MagicMock

import pytest

from services.analytics import cli_data_governance


def test_enforcement_cli_blocks_before_database_connection(monkeypatch, capsys):
    monkeypatch.delenv("KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT", raising=False)
    connection_factory = MagicMock()
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", connection_factory)

    with pytest.raises(SystemExit) as exc_info:
        cli_data_governance.main(["enforce-retention", "--actor", "operator-1"])

    assert exc_info.value.code == 1
    assert "KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT=true" in capsys.readouterr().err
    connection_factory.assert_not_called()


def test_enforcement_cli_help_remains_available_when_disabled(monkeypatch):
    monkeypatch.delenv("KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT", raising=False)
    connection_factory = MagicMock()
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", connection_factory)

    with pytest.raises(SystemExit) as exc_info:
        cli_data_governance.main(["enforce-retention", "--help"])

    assert exc_info.value.code == 0
    connection_factory.assert_not_called()
