"""Public location IRI snapshots are opt-in and source from the governed view."""

import json
from unittest.mock import MagicMock

import pytest

from services.iri.resolver import generate_iri

LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def test_public_location_generation_snapshots_only_allowlisted_public_view_fields():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.side_effect = [
        {
            "location_name": "Published Farm",
            "country": "DO",
            "region": "North",
            "status": "active",
            "private_column": "must not be copied",
        },
        {"max_version": None},
    ]

    iri = generate_iri(
        connection,
        "location",
        LOCATION_ID,
        content={"private": "never returned by the public resolver"},
        publish_public_location=True,
    )

    insert_sql = next(
        sql
        for sql_call in connection.text.call_args_list
        if "INSERT INTO iri_registry" in (sql := sql_call.args[0])
    )
    assert "public_projection" in insert_sql
    parameters = connection.execute.call_args.args[1]
    assert iri == f"kokonut:location:{LOCATION_ID}:v1"
    assert json.loads(parameters["public_projection"]) == {
        "name": "Published Farm",
        "country": "DO",
        "region": "North",
        "status": "active",
    }
    public_view_query = next(
        sql_call.args[0]
        for sql_call in connection.text.call_args_list
        if "v_public_farm_summary" in sql_call.args[0]
    )
    assert "private_column" not in public_view_query


def test_public_location_generation_fails_before_mutation_when_not_public():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.return_value = None

    with pytest.raises(ValueError, match="not eligible for public IRI projection"):
        generate_iri(
            connection,
            "location",
            LOCATION_ID,
            publish_public_location=True,
        )

    statements = [call.args[0] for call in connection.text.call_args_list]
    assert any("v_public_farm_summary" in statement for statement in statements)
    assert not any("INSERT INTO iri_registry" in statement for statement in statements)
    assert not any("UPDATE iri_registry" in statement for statement in statements)


@pytest.mark.parametrize(
    ("entity_type", "entity_id", "message"),
    [
        ("credit_class", LOCATION_ID, "locations only"),
        ("location", "not-a-uuid", "UUID"),
    ],
)
def test_public_projection_scope_is_validated_before_database_access(entity_type, entity_id, message):
    connection = MagicMock()

    with pytest.raises(ValueError, match=message):
        generate_iri(
            connection,
            entity_type,
            entity_id,
            publish_public_location=True,
        )

    connection.execute.assert_not_called()


def test_public_projection_option_requires_a_boolean():
    with pytest.raises(TypeError, match="must be a boolean"):
        generate_iri(
            MagicMock(),
            "location",
            LOCATION_ID,
            publish_public_location="yes",
        )


def test_non_public_iri_generation_remains_private_by_default():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.side_effect = [
        None,
        {"max_version": None},
    ]

    generate_iri(connection, "location", LOCATION_ID, content={"name": "Private draft"})

    parameters = connection.execute.call_args.args[1]
    assert parameters["public_projection"] is None
    assert not any(
        "v_public_farm_summary" in call.args[0]
        for call in connection.text.call_args_list
    )
