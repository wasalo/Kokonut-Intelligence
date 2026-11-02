"""Security CLI location scopes are validated before capability DB access."""

import sys

import pytest

from services.security import cli as security_cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


def _verify_argv(*location_args: str) -> list[str]:
    return [
        "security",
        "--verify",
        "--token",
        "synthetic-token",
        "--resource",
        "harvest_event",
        "--action",
        "read",
        *location_args,
    ]


@pytest.mark.parametrize("location_id", ["not-a-uuid", "", "all"])
def test_verify_rejects_malformed_location_before_manager_or_database(
    monkeypatch, location_id
):
    monkeypatch.setattr(
        "services.security.capabilities.CapabilityManager",
        lambda: pytest.fail("malformed location must fail before manager/DB access"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _verify_argv("--location-id", location_id),
    )

    with pytest.raises(SystemExit) as exc_info:
        security_cli.main()

    assert exc_info.value.code == 2


def test_verify_canonicalizes_location_before_capability_check(monkeypatch):
    calls = []

    class Manager:
        def verify(self, token, resource, action, location_id):
            calls.append((token, resource, action, location_id))
            return {"holder": "test-operator"}

    monkeypatch.setattr("services.security.capabilities.CapabilityManager", Manager)
    monkeypatch.setattr(
        sys,
        "argv",
        _verify_argv("--location-id", LOCATION_ID),
    )

    with pytest.raises(SystemExit) as exc_info:
        security_cli.main()

    assert exc_info.value.code == 0
    assert calls == [
        ("synthetic-token", "harvest_event", "read", CANONICAL_LOCATION_ID)
    ]


def test_verify_without_location_remains_global(monkeypatch):
    calls = []

    class Manager:
        def verify(self, token, resource, action, location_id):
            calls.append((token, resource, action, location_id))
            return {"holder": "test-operator"}

    monkeypatch.setattr("services.security.capabilities.CapabilityManager", Manager)
    monkeypatch.setattr(sys, "argv", _verify_argv())

    with pytest.raises(SystemExit) as exc_info:
        security_cli.main()

    assert exc_info.value.code == 0
    assert calls == [("synthetic-token", "harvest_event", "read", None)]
