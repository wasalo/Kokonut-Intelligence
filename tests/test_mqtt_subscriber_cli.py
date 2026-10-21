"""Offline standalone/unified CLI contracts for the MQTT sensor subscriber."""

from __future__ import annotations

import pytest

from services.ingestion import cli as ingestion_cli
from services.ingestion import mqtt_subscriber


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], {"broker": mqtt_subscriber.DEFAULT_BROKER, "port": mqtt_subscriber.DEFAULT_PORT}),
        (["--broker", "mqtt.synthetic", "--port", "18883"], {"broker": "mqtt.synthetic", "port": 18883}),
    ],
)
def test_standalone_and_unified_entrypoints_forward_broker_options(
    monkeypatch, arguments: list[str], expected: dict[str, object]
) -> None:
    calls = []
    monkeypatch.setattr(mqtt_subscriber, "run", lambda **kwargs: calls.append(kwargs))

    mqtt_subscriber.main(arguments)
    standalone_call = calls.pop()
    ingestion_cli.main(["mqtt_subscriber", *arguments])

    assert calls == [standalone_call]
    assert standalone_call == expected


@pytest.mark.parametrize("unified", [False, True], ids=["standalone", "unified"])
def test_non_integer_port_fails_before_subscriber_start(monkeypatch, unified: bool) -> None:
    monkeypatch.setattr(
        mqtt_subscriber, "run", lambda **_kwargs: pytest.fail("subscriber must not start")
    )

    with pytest.raises(SystemExit) as error:
        if unified:
            ingestion_cli.main(["mqtt_subscriber", "--port", "invalid"])
        else:
            mqtt_subscriber.main(["--port", "invalid"])

    assert error.value.code == 2


def test_standalone_and_unified_help_output_matches(capsys) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        mqtt_subscriber.main(["--help"])
    standalone = capsys.readouterr()

    with pytest.raises(SystemExit) as unified_exit:
        ingestion_cli.main(["mqtt_subscriber", "--help"])
    unified = capsys.readouterr()

    assert standalone_exit.value.code == unified_exit.value.code == 0
    assert unified.out == standalone.out
    assert unified.err == standalone.err == ""
