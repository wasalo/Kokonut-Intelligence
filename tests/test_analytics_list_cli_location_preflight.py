"""Location-filtered cooperative and traceability lists preflight UUID scope."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from services.analytics import cli_cooperative, cli_traceability

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = str(UUID(LOCATION_ID))


@pytest.mark.parametrize(
    ("module", "command"),
    [
        (cli_cooperative, ["list"]),
        (cli_traceability, ["list"]),
    ],
)
@pytest.mark.parametrize("location_id", ["not-a-uuid", "", "all"])
def test_list_rejects_malformed_location_before_database(monkeypatch, module, command, location_id):
    monkeypatch.setattr(
        module.cli,
        "_connection_factory",
        lambda: pytest.fail("invalid location must fail before database access"),
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main([*command, "--location-id", location_id])

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("module", "command", "handler_name"),
    [
        (cli_cooperative, ["list"], "list_cooperatives"),
        (cli_traceability, ["list"], "list_batches"),
    ],
)
@pytest.mark.parametrize("option", ["--location-id", "--location-id="])
def test_list_canonicalizes_supplied_location_before_handler(
    monkeypatch, module, command, handler_name, option
):
    calls = []
    connection = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(module.cli, "_connection_factory", lambda: connection)
    monkeypatch.setattr(
        module,
        handler_name,
        lambda _conn, location_id, **_kwargs: calls.append(location_id) or [],
    )
    location_tokens = [option, LOCATION_ID] if option == "--location-id" else [f"{option}{LOCATION_ID}"]

    module.main([*command, *location_tokens, "--json"])

    assert calls == [CANONICAL_LOCATION_ID]


def test_traceability_list_without_location_preserves_global_listing(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_traceability.cli,
        "_connection_factory",
        lambda: SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(
        cli_traceability,
        "list_batches",
        lambda _conn, *, location_id, status, limit: calls.append((location_id, status, limit)) or [],
    )

    cli_traceability.main(["list", "--json"])

    assert calls == [(None, None, 50)]
