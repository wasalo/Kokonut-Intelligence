"""Location UUIDs are preflighted before driver and sandbox DB access."""

import sys

import pytest

DRIVER_LOCATION = "A0000000-0000-4000-8000-000000000001"
CANONICAL_DRIVER_LOCATION = "a0000000-0000-4000-8000-000000000001"
SANDBOX_LOCATION = "B0000000-0000-4000-8000-000000000002"
CANONICAL_SANDBOX_LOCATION = "b0000000-0000-4000-8000-000000000002"


@pytest.mark.parametrize("location_id", ["bad-location", ""])
def test_driver_install_rejects_malformed_location_before_registry(
    monkeypatch, location_id
):
    from services.drivers.cli import main

    monkeypatch.setattr(
        "services.drivers.registry.DriverRegistry",
        lambda: pytest.fail("invalid location must fail before registry/DB access"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drivers",
            "--install",
            "--driver",
            "weather",
            "--instance-name",
            "farm-weather",
            "--location-id",
            location_id,
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_driver_install_canonicalizes_optional_location_before_registry(monkeypatch):
    from services.drivers.cli import main

    calls = []

    class Registry:
        def create_instance(self, **kwargs):
            calls.append(kwargs)
            return "instance-id"

    monkeypatch.setattr("services.drivers.registry.DriverRegistry", Registry)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drivers",
            "--install",
            "--driver",
            "weather",
            "--instance-name",
            "farm-weather",
            "--location-id",
            DRIVER_LOCATION,
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert calls == [{
        "driver_name": "weather",
        "instance_name": "farm-weather",
        "config": {},
        "location_id": CANONICAL_DRIVER_LOCATION,
    }]


def test_driver_install_keeps_location_scope_optional(monkeypatch):
    from services.drivers.cli import main

    calls = []

    class Registry:
        def create_instance(self, **kwargs):
            calls.append(kwargs)
            return "instance-id"

    monkeypatch.setattr("services.drivers.registry.DriverRegistry", Registry)
    monkeypatch.setattr(
        sys,
        "argv",
        ["drivers", "--install", "--driver", "weather", "--instance-name", "global"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert calls[0]["location_id"] is None


@pytest.mark.parametrize("location_id", ["bad-location", ""])
@pytest.mark.parametrize("command", ["--create", "--list"])
def test_sandbox_rejects_malformed_location_before_environment(
    monkeypatch, location_id, command
):
    from services.sandbox.cli import main

    monkeypatch.setattr(
        "services.sandbox.environment.AnalysisEnvironment",
        lambda: pytest.fail("invalid location must fail before environment/DB access"),
    )
    argv = ["sandbox", command, "--location-id", location_id]
    if command == "--create":
        argv.extend(["--env-type", "sandbox"])
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_sandbox_create_canonicalizes_location_before_environment(monkeypatch):
    from services.sandbox.cli import main

    calls = []

    class Environment:
        def create(self, location_id, *, env_type):
            calls.append((location_id, env_type))
            return "environment-id"

    monkeypatch.setattr(
        "services.sandbox.environment.AnalysisEnvironment", Environment
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["sandbox", "--create", "--location-id", SANDBOX_LOCATION],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert calls == [(CANONICAL_SANDBOX_LOCATION, "sandbox")]


def test_sandbox_list_without_location_retains_global_mode(monkeypatch):
    from services.sandbox.cli import main

    calls = []

    class Environment:
        def list_environments(self, *, location_id):
            calls.append(location_id)
            return []

    monkeypatch.setattr(
        "services.sandbox.environment.AnalysisEnvironment", Environment
    )
    monkeypatch.setattr(sys, "argv", ["sandbox", "--list"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert calls == [None]

