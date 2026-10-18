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


def test_list_options_preserve_exact_non_page_aligned_offset():
    from kokonut.types import ListOptions

    options = ListOptions(limit=25, offset=10)

    assert options.to_params() == {"limit": 25, "offset": 10}


def test_crop_cycle_sdk_type_exposes_schema_aligned_yield_fields():
    from kokonut.types import CropCycle

    cycle = CropCycle(
        id="cycle-1",
        plot_id="plot-1",
        crop_id="crop-1",
        location_id="location-1",
        actual_yield=215,
        actual_yield_unit="kg",
        schema_version="1.0",
    )

    assert cycle.location_id == "location-1"
    assert cycle.actual_yield == 215
    assert cycle.actual_yield_unit == "kg"
    assert cycle.schema_version == "1.0"


def test_harvest_event_sdk_type_exposes_schema_evidence_and_lineage_fields():
    from kokonut.types import HarvestEvent

    event = HarvestEvent(
        id="harvest-1",
        crop_cycle_id="cycle-1",
        plot_id="plot-1",
        location_id="location-1",
        harvest_date="2026-10-17",
        quantity=120,
        unit="kg",
        evidence_urls=["private://harvest/photo-1"],
        evidence_hashes=["sha256:abc123"],
        schema_version="1.0",
        source_system="field_collector",
        source_id="device-note-1",
        source_raw={"form_version": "1.2.0"},
        updated_at="2026-10-17T12:00:00Z",
    )

    assert event.evidence_hashes == ["sha256:abc123"]
    assert event.source_raw == {"form_version": "1.2.0"}
    assert event.updated_at == "2026-10-17T12:00:00Z"


def test_sales_event_sdk_type_exposes_schema_evidence_and_lineage_fields():
    from kokonut.types import SalesEvent

    event = SalesEvent(
        id="sale-1",
        location_id="location-1",
        sale_date="2026-10-17",
        quantity=80,
        unit="kg",
        total_amount=160,
        payment_date="2026-10-18",
        payment_method="bank_transfer",
        evidence_urls=["private://sales/invoice-1"],
        evidence_hashes=["sha256:def456"],
        source_raw={"batch_id": "import-1"},
        updated_at="2026-10-18T12:00:00Z",
    )

    assert event.payment_method == "bank_transfer"
    assert event.evidence_hashes == ["sha256:def456"]
    assert event.source_raw == {"batch_id": "import-1"}


def test_expense_event_sdk_type_exposes_schema_approval_and_lineage_fields():
    from kokonut.types import ExpenseEvent

    event = ExpenseEvent(
        id="expense-1",
        location_id="location-1",
        expense_date="2026-10-17",
        category="labor",
        amount=75,
        vendor_id="partner-1",
        allocation_weight=0.5,
        evidence_urls=["private://expenses/receipt-1"],
        receipt_hash="sha256:ghi789",
        approved_by="reviewer-1",
        approved_at="2026-10-18T12:00:00Z",
        rejection_reason=None,
        schema_version="1.0",
        source_raw={"batch_id": "import-2"},
    )

    assert event.vendor_id == "partner-1"
    assert event.allocation_weight == 0.5
    assert event.approved_by == "reviewer-1"
    assert event.source_raw == {"batch_id": "import-2"}


def test_location_farm_and_plot_types_expose_schema_geometry_and_metadata():
    from kokonut.types import Farm, Location, Plot

    geometry = {"type": "Point", "coordinates": [-69.9, 18.5]}
    location = Location(
        id="location-1",
        name="Test Location",
        slug="test-location",
        center=geometry,
        country="DO",
        created_by="operator-1",
    )
    farm = Farm(
        id="farm-1",
        location_id=location.id,
        name="Test Farm",
        slug="test-farm",
        boundary={"type": "Polygon", "coordinates": []},
        updated_by="operator-1",
    )
    plot = Plot(
        id="plot-1",
        farm_id=farm.id,
        name="North Plot",
        boundary={"type": "Polygon", "coordinates": []},
        center=geometry,
        elevation_m=42,
        metadata={"source": "fixture"},
    )

    assert location.center == geometry
    assert farm.boundary == {"type": "Polygon", "coordinates": []}
    assert plot.elevation_m == 42


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


def test_export_create_many_delegates_to_directus_batch_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    client.create_items = Mock(return_value=[{"id": "export-1"}, {"id": "export-2"}])
    requests = [
        {"export_type": "farm_data", "status": "pending"},
        {"export_type": "metric_data", "status": "pending"},
    ]

    result = client.exports.create_many(requests)

    assert result == [{"id": "export-1"}, {"id": "export-2"}]
    client.create_items.assert_called_once_with("export_log", requests)


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
