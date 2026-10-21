"""Offline standalone/unified parser contracts for mock sensor actions."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import mock_sensors


@pytest.mark.parametrize(
    ("arguments", "action", "expected"),
    [
        (["--setup"], "setup", None),
        (["--generate", "--count", "7", "--anomalies"], "generate", {"count": 7, "inject_anomalies": True}),
        (["--cleanup"], "cleanup", None),
    ],
)
@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_standalone_and_unified_entrypoints_dispatch_selected_action(
    monkeypatch, arguments: list[str], action: str, expected: dict[str, object] | None, unified: bool
) -> None:
    calls = []
    monkeypatch.setattr(mock_sensors, "setup_sensors", lambda: calls.append(("setup", None)))
    monkeypatch.setattr(
        mock_sensors,
        "generate_data",
        lambda **kwargs: calls.append(("generate", kwargs)),
    )
    monkeypatch.setattr(mock_sensors, "cleanup", lambda: calls.append(("cleanup", None)))

    if unified:
        ingestion_cli.main(["mock_sensors", *arguments])
    else:
        mock_sensors.main(arguments)

    assert calls == [(action, expected)]


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_no_action_prints_help_without_running_demo_operations(monkeypatch, capsys, unified: bool) -> None:
    monkeypatch.setattr(
        mock_sensors,
        "setup_sensors",
        lambda: pytest.fail("no-action invocation must not set up sensors"),
    )
    monkeypatch.setattr(
        mock_sensors,
        "generate_data",
        lambda **_kwargs: pytest.fail("no-action invocation must not generate data"),
    )
    monkeypatch.setattr(
        mock_sensors, "cleanup", lambda: pytest.fail("no-action invocation must not clean data")
    )

    if unified:
        ingestion_cli.main(["mock_sensors"])
    else:
        mock_sensors.main([])

    assert "usage:" in capsys.readouterr().out


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        mock_sensors.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["mock_sensors", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""


@pytest.mark.parametrize("count", ["0", "-1"])
@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_nonpositive_generation_count_fails_before_database_or_generation(
    monkeypatch, capsys, count: str, unified: bool
) -> None:
    monkeypatch.setattr(
        mock_sensors,
        "get_db",
        lambda: pytest.fail("invalid generation count must fail before database access"),
    )
    monkeypatch.setattr(
        mock_sensors,
        "generate_data",
        lambda **_kwargs: pytest.fail("invalid generation count must not be dispatched"),
    )

    with pytest.raises(SystemExit) as exc_info:
        if unified:
            ingestion_cli.main(["mock_sensors", "--generate", "--count", count])
        else:
            mock_sensors.main(["--generate", "--count", count])

    assert exc_info.value.code == 2
    assert "--count must be a positive integer" in capsys.readouterr().err


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_generate_data_validates_count_before_opening_database(monkeypatch, count) -> None:
    monkeypatch.setattr(
        mock_sensors,
        "get_db",
        lambda: pytest.fail("invalid generation count must fail before database access"),
    )

    with pytest.raises(ValueError, match="--count must be a positive integer"):
        mock_sensors.generate_data(count=count)
