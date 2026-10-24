"""Offline standalone/unified CLI contracts for the HTTP sensor receiver."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import http_sensor_receiver


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], {"host": "0.0.0.0", "port": 8056}),
        (["--host", "127.0.0.1", "--port", "18056"], {"host": "127.0.0.1", "port": 18056}),
    ],
)
def test_standalone_and_unified_entrypoints_forward_bind_options(
    monkeypatch, arguments: list[str], expected: dict[str, object]
) -> None:
    calls = []
    monkeypatch.setattr(http_sensor_receiver, "run", lambda **kwargs: calls.append(kwargs))

    http_sensor_receiver.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["http_sensor_receiver", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == expected


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_non_integer_port_fails_before_server_start(monkeypatch, unified: bool) -> None:
    monkeypatch.setattr(
        http_sensor_receiver, "run", lambda **_kwargs: pytest.fail("server must not start")
    )
    arguments = ["--port", "invalid"]

    with pytest.raises(SystemExit) as error:
        if unified:
            ingestion_cli.main(["http_sensor_receiver", *arguments])
        else:
            http_sensor_receiver.main(arguments)

    assert error.value.code == 2


@pytest.mark.parametrize("port", ["0", "-1", "65536"])
@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_out_of_range_port_fails_before_server_start(
    monkeypatch, port: str, unified: bool
) -> None:
    monkeypatch.setattr(
        http_sensor_receiver, "run", lambda **_kwargs: pytest.fail("server must not start")
    )

    with pytest.raises(SystemExit) as error:
        if unified:
            ingestion_cli.main(["http_sensor_receiver", "--port", port])
        else:
            http_sensor_receiver.main(["--port", port])

    assert error.value.code == 2


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        http_sensor_receiver.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["http_sensor_receiver", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
