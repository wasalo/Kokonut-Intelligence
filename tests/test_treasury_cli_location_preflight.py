"""Treasury commands validate location scopes before provisioning access."""

from typer.testing import CliRunner

from services.treasury import cli as treasury_cli

LOCATION_ID = "A0000000-0000-4000-8000-000000000001"
CANONICAL_LOCATION_ID = "a0000000-0000-4000-8000-000000000001"


def test_propose_rejects_invalid_location_before_provisioning(monkeypatch):
    from services.treasury import provisioning

    calls = []
    monkeypatch.setattr(provisioning, "cli_propose", lambda **kwargs: calls.append(kwargs))
    result = CliRunner().invoke(treasury_cli.app, ["propose", "not-a-uuid"])

    assert result.exit_code == 2
    assert "must be a valid UUID" in result.output
    assert calls == []


def test_propose_passes_canonical_location_to_provisioning(monkeypatch):
    from services.treasury import provisioning

    calls = []
    monkeypatch.setattr(provisioning, "cli_propose", lambda **kwargs: calls.append(kwargs))
    result = CliRunner().invoke(treasury_cli.app, ["propose", LOCATION_ID])

    assert result.exit_code == 0
    assert calls[0]["location_id"] == CANONICAL_LOCATION_ID


def test_farms_rejects_invalid_location_before_provisioning(monkeypatch):
    from services.treasury import provisioning

    calls = []
    monkeypatch.setattr(provisioning, "cli_list", lambda location_id: calls.append(location_id))
    result = CliRunner().invoke(treasury_cli.app, ["farms", "--location-id", "all"])

    assert result.exit_code == 2
    assert "must be a valid UUID" in result.output
    assert calls == []


def test_farms_canonicalizes_location_before_provisioning(monkeypatch):
    from services.treasury import provisioning

    calls = []
    monkeypatch.setattr(provisioning, "cli_list", lambda location_id: calls.append(location_id))
    result = CliRunner().invoke(
        treasury_cli.app, ["farms", "--location-id", LOCATION_ID]
    )

    assert result.exit_code == 0
    assert calls == [CANONICAL_LOCATION_ID]


def test_farms_without_location_preserves_global_list(monkeypatch):
    from services.treasury import provisioning

    calls = []
    monkeypatch.setattr(provisioning, "cli_list", lambda location_id: calls.append(location_id))
    result = CliRunner().invoke(treasury_cli.app, ["farms"])

    assert result.exit_code == 0
    assert calls == [None]
