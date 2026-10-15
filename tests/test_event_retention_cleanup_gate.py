"""Event pruning remains unavailable until retention is explicitly approved."""

import sys
from unittest.mock import MagicMock

import pytest

from services.events import cli


def test_cleanup_cli_requires_explicit_retention_window(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["services.events", "--cleanup"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2


@pytest.mark.parametrize("days", ["0", "-1"])
def test_cleanup_cli_rejects_nonpositive_retention_before_event_store(monkeypatch, days):
    monkeypatch.setenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "true")
    monkeypatch.setattr(sys, "argv", ["services.events", "--cleanup", "--days", days])
    store_factory = MagicMock()
    monkeypatch.setattr("services.events.backend.get_event_store", store_factory)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    store_factory.assert_not_called()


def test_disabled_cleanup_cli_stops_before_opening_event_store(monkeypatch, capsys):
    monkeypatch.delenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", raising=False)
    monkeypatch.setattr(sys, "argv", ["services.events", "--cleanup", "--days", "30"])
    store_factory = MagicMock()
    monkeypatch.setattr("services.events.backend.get_event_store", store_factory)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    assert "KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP=true" in capsys.readouterr().err
    store_factory.assert_not_called()


def test_enabled_cleanup_cli_uses_only_the_explicit_window(monkeypatch):
    monkeypatch.setenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "true")
    monkeypatch.setattr(sys, "argv", ["services.events", "--cleanup", "--days", "90"])
    bus = MagicMock()
    bus.cleanup_old_events.return_value = 2
    monkeypatch.setattr("services.events.backend.get_event_store", lambda: bus)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    bus.cleanup_old_events.assert_called_once_with(days=90)
    bus.close.assert_called_once()
