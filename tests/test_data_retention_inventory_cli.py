"""CLI coverage for bounded, read-only retention inventories."""

import json
from unittest.mock import MagicMock

from services.analytics import cli_data_governance


def test_retention_policy_inventory_cli_forwards_filters(monkeypatch, capsys):
    conn = MagicMock()
    inventory = MagicMock(return_value={"policies": [], "total": 0, "limit": 25})
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", lambda: conn)
    monkeypatch.setattr(cli_data_governance, "list_retention_policies", inventory)

    cli_data_governance.main([
        "retention-policies", "--status", "draft", "--data-category", "soil",
        "--jurisdiction-code", "us", "--purpose-code", "research",
        "--location-id", "a0000000-0000-0000-0000-000000000403",
        "--limit", "25",
    ])

    inventory.assert_called_once_with(
        conn,
        status="draft",
        data_category="soil",
        jurisdiction_code="us",
        purpose_code="research",
        location_id="a0000000-0000-0000-0000-000000000403",
        limit=25,
    )
    assert json.loads(capsys.readouterr().out)["total"] == 0
    conn.close.assert_called_once()


def test_retention_hold_inventory_defaults_to_active_only(monkeypatch, capsys):
    conn = MagicMock()
    inventory = MagicMock(return_value={"holds": [], "total": 0, "limit": 100})
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", lambda: conn)
    monkeypatch.setattr(cli_data_governance, "list_retention_legal_holds", inventory)

    cli_data_governance.main(["retention-holds", "--entity-type", "platform_event"])

    inventory.assert_called_once_with(
        conn,
        active_only=True,
        entity_type="platform_event",
        entity_id=None,
        limit=100,
    )
    assert json.loads(capsys.readouterr().out)["holds"] == []


def test_retention_hold_inventory_can_include_released(monkeypatch, capsys):
    conn = MagicMock()
    inventory = MagicMock(return_value={"holds": [], "total": 0, "limit": 10})
    monkeypatch.setattr(cli_data_governance.cli, "_connection_factory", lambda: conn)
    monkeypatch.setattr(cli_data_governance, "list_retention_legal_holds", inventory)

    cli_data_governance.main([
        "retention-holds", "--include-released", "--entity-type", "platform_event",
        "--entity-id", "a0000000-0000-0000-0000-000000000403", "--limit", "10",
    ])

    inventory.assert_called_once_with(
        conn,
        active_only=False,
        entity_type="platform_event",
        entity_id="a0000000-0000-0000-0000-000000000403",
        limit=10,
    )
    capsys.readouterr()
