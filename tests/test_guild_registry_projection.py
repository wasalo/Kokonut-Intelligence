"""Regression coverage for Guild Registry event projections."""

from unittest.mock import MagicMock

import pytest

from services.guilds.projections import project_protocol_event


@pytest.mark.parametrize(
    ("event_name", "event_fields", "sql_fragments", "expected_value"),
    [
        (
            "GuildMetadataUpdated",
            {"metadata_uri": "ipfs://registry-metadata"},
            ["jsonb_set(", "{_kgp_registry}", "'metadata_uri'"],
            "ipfs://registry-metadata",
        ),
        (
            "GuildStewardUpdated",
            {"steward": "0x0000000000000000000000000000000000000042"},
            ["'{_kgp_registry}'", "'steward'", "chain_projection = TRUE"],
            "0x0000000000000000000000000000000000000042",
        ),
        (
            "GuildStatusUpdated",
            {"status": 2},
            ["'{_kgp_registry}'", "'status'", "chain_projection = TRUE"],
            "deprecated",
        ),
    ],
)
def test_registry_mutation_events_update_the_guild_projection(
    event_name, event_fields, sql_fragments, expected_value
):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("guild-row-id",)
    cursor.rowcount = 1
    event = {
        "event_name": event_name,
        "guild_id": "0x" + "ab" * 32,
        "transaction_hash": "0x" + "cd" * 32,
        "block_number": 123,
        **event_fields,
    }

    projected = project_protocol_event(cursor, "deployment-id", event, "source-event-id")

    assert projected is True
    assert cursor.execute.call_count == 2
    update_sql, parameters = cursor.execute.call_args.args
    for fragment in sql_fragments:
        assert fragment in update_sql
    assert "SET steward_wallet =" not in update_sql
    assert "SET status =" not in update_sql
    assert "SET name =" not in update_sql
    assert "source_chain_event_id = %s" in update_sql
    assert "orphaned_at = NULL" in update_sql
    assert "updated_at = NOW()" in update_sql
    assert parameters[0] == expected_value
    assert parameters[1:] == ("source-event-id", "guild-row-id")


def test_registry_mutation_for_unknown_guild_remains_unprojected():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    projected = project_protocol_event(
        cursor,
        "deployment-id",
        {
            "event_name": "GuildStewardUpdated",
            "guild_id": "0x" + "ab" * 32,
            "transaction_hash": "0x" + "cd" * 32,
            "block_number": 123,
            "steward": "0x0000000000000000000000000000000000000042",
        },
        "source-event-id",
    )

    assert projected is False
    assert cursor.execute.call_count == 1


def test_registry_status_rejects_unknown_contract_enum_before_mutation():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("guild-row-id",)

    with pytest.raises(ValueError, match="Unknown protocol status"):
        project_protocol_event(
            cursor,
            "deployment-id",
            {
                "event_name": "GuildStatusUpdated",
                "guild_id": "0x" + "ab" * 32,
                "transaction_hash": "0x" + "cd" * 32,
                "block_number": 123,
                "status": 3,
            },
            "source-event-id",
        )

    assert cursor.execute.call_count == 1


def test_guild_creation_projects_contract_name_steward_and_active_status():
    cursor = MagicMock()
    cursor.rowcount = 1
    event = {
        "event_name": "GuildCreated",
        "guild_id": "0x" + "ab" * 32,
        "guild_key": "0x" + "ef" * 32,
        "guild_key_name": "kokonut-network",
        "name": "Kokonut Network",
        "steward": "0x0000000000000000000000000000000000000042",
        "transaction_hash": "0x" + "cd" * 32,
        "block_number": 123,
    }

    projected = project_protocol_event(cursor, "deployment-id", event, "source-event-id")

    assert projected is True
    statement, parameters = cursor.execute.call_args.args
    assert "'{_kgp_registry}'" in statement
    assert "'name', %s::text, 'steward', %s::text" in statement
    assert "SET steward_wallet =" not in statement
    assert "SET status =" not in statement
    assert "SET name =" not in statement
    assert "chain_projection = TRUE" in statement
    assert parameters == (
        event["guild_id"],
        event["guild_key"],
        event["name"],
        event["steward"],
        "source-event-id",
        event["guild_key"],
        event["guild_key_name"],
    )
