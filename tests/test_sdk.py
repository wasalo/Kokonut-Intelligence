"""SDK smoke tests — import and instantiate without network calls."""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add sdk/python to path for import
SDK_PATH = Path(__file__).resolve().parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))


def test_kokonut_client_import():
    from kokonut import KokonutClient
    from kokonut.client import AuthenticationError, KokonutError

    client = KokonutClient("http://localhost:8055")
    assert client.base_url == "http://localhost:8055"
    assert client.locations is not None
    assert client.farms is not None
    assert client.harvest_events is not None
    assert issubclass(AuthenticationError, KokonutError)


def test_kokonut_types_import():
    from kokonut.types import ListOptions

    opts = ListOptions(limit=10)
    assert opts.limit == 10


def test_kokonut_methods_import():
    from kokonut.methods import FarmMethods, HarvestEventMethods, LocationMethods

    assert LocationMethods is not None
    assert FarmMethods is not None
    assert HarvestEventMethods is not None


def test_export_creation_preserves_target_table_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    client.create_item = Mock(return_value={"id": "export-1"})

    result = client.exports.create_export(
        "farm_data",
        entity_type="location",
        entity_ids=["location-1"],
        target_table="harvest_event",
        filters={"status": "published"},
    )

    assert result == {"id": "export-1"}
    client.create_item.assert_called_once_with(
        "export_log",
        {
            "export_type": "farm_data",
            "format": None,
            "entity_type": "location",
            "entity_ids": ["location-1"],
            "target_table": "harvest_event",
            "filters": {"status": "published"},
            "status": "pending",
            "requested_by": "sdk",
        },
    )


def test_scoped_list_filter_wins_and_preserves_list_options_without_network_calls():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])

    client.farms.list_by_location(
        "location-1",
        ListOptions(
            filter={"location_id": {"_eq": "location-2"}, "status": {"_eq": "active"}},
            sort=["name"],
            fields=["id"],
            limit=25,
            offset=50,
            page=3,
            meta="total_count",
        ),
    )

    client.list_items.assert_called_once()
    collection, options = client.list_items.call_args.args
    assert collection == "farm"
    assert options.filter == {
        "location_id": {"_eq": "location-1"},
        "status": {"_eq": "active"},
    }
    assert options.sort == ["name"]
    assert options.fields == ["id"]
    assert options.limit == 25
    assert options.offset == 50
    assert options.page == 3
    assert options.meta == "total_count"


if __name__ == "__main__":
    test_kokonut_client_import()
    test_kokonut_types_import()
    test_kokonut_methods_import()
    test_scoped_list_filter_wins_and_preserves_list_options_without_network_calls()
    print("All SDK smoke tests passed ✓")
