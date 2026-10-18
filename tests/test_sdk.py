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
    client.create_item.assert_called_once_with("export_log", {
        "export_type": "farm_data",
        "format": None,
        "entity_type": "location",
        "entity_ids": ["location-1"],
        "target_table": "harvest_event",
        "filters": {"status": "published"},
        "status": "pending",
        "requested_by": "sdk",
    })


if __name__ == "__main__":
    test_kokonut_client_import()
    test_kokonut_types_import()
    test_kokonut_methods_import()
    print("All SDK smoke tests passed ✓")
