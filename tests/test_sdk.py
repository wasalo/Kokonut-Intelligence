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
    assert client.loss_events is not None
    assert client.labor_events is not None
    assert client.field_notes is not None
    assert issubclass(AuthenticationError, KokonutError)


def test_kokonut_types_import():
    from kokonut.types import ListOptions

    opts = ListOptions(limit=10)
    assert opts.limit == 10


def test_organization_sdk_model_uses_schema_values_and_keeps_metadata_json_typed():
    from kokonut import Organization, OrganizationStatus, OrganizationType

    organization = Organization(
        id="org-1",
        org_key="kokonut-network",
        name="Kokonut Network",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        org_type="dao",
        status="active",
        metadata={"region": "Caribbean", "active": True},
    )

    assert organization.status == "active"
    assert organization.org_type == "dao"
    assert OrganizationStatus.__args__ == ("active", "inactive", "dissolved")
    assert OrganizationType.__args__ == (
        "cooperative", "nonprofit", "dao", "enterprise", "collective", "other"
    )


def test_organization_member_type_is_descriptive_not_an_access_grant():
    from kokonut import OrganizationMember, OrganizationMembershipType

    membership = OrganizationMember(
        id="membership-1",
        organization_id="org-1",
        location_id="location-1",
        join_date="2026-10-18",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        membership_type="owned",
        role="primary",
        status="active",
    )

    assert membership.membership_type == "owned"
    assert membership.status == "active"
    assert OrganizationMembershipType.__args__ == (
        "owned", "affiliated", "sponsored", "partner"
    )


def test_expense_category_type_exposes_shared_taxonomy_fields():
    from kokonut import ExpenseCategory

    category = ExpenseCategory(
        id="category-1",
        name="Seeds",
        code="SEEDS",
        is_direct=True,
        active=True,
        schema_version="common-data-schema-v1",
    )

    assert category.name == "Seeds"
    assert category.is_direct is True
    assert category.parent_id is None
    assert category.schema_version == "common-data-schema-v1"


def test_capital_source_type_exposes_funding_and_governance_metadata():
    from kokonut import CapitalSource

    source = CapitalSource(
        id="source-1",
        name="DAO Treasury",
        source_type="dao",
        amount=125000.5,
        currency="USD",
        status="active",
        metadata={"proposal_id": "42", "purpose": "farm infrastructure"},
    )

    assert source.amount == 125000.5
    assert source.status == "active"
    assert source.metadata["proposal_id"] == "42"


def test_financial_transaction_type_describes_recorded_facts_without_payment_action():
    from kokonut import FinancialTransaction

    transaction = FinancialTransaction(
        id="transaction-1",
        location_id="location-1",
        transaction_date="2026-10-18",
        transaction_type="capital_inflow",
        amount=1000.0,
        evidence_urls=["evidence://receipt-1"],
        source_raw={"import": "synthetic"},
    )

    assert transaction.amount == 1000.0
    assert transaction.reconciled is None
    assert transaction.source_raw == {"import": "synthetic"}


def test_value_flow_type_exposes_verification_and_attestation_references():
    from kokonut import ValueFlowEvent

    flow = ValueFlowEvent(
        id="flow-1",
        flow_date="2026-10-18",
        flow_type="public_goods",
        amount=500.0,
        location_id="location-1",
        attestation_uid="0xabc",
        is_excluded=False,
    )

    assert flow.attestation_uid == "0xabc"
    assert flow.verified is None
    assert flow.is_excluded is False


def test_excluded_value_event_type_preserves_reviewer_and_reason_context():
    from kokonut import ExcludedValueEvent

    exclusion = ExcludedValueEvent(
        id="exclusion-1",
        value_flow_id="flow-1",
        exclusion_type="returned_fund",
        amount=25.0,
        reason="Returned to funding source",
        excluded_by="reviewer-1",
    )

    assert exclusion.value_flow_id == "flow-1"
    assert exclusion.exclusion_type == "returned_fund"
    assert exclusion.reason == "Returned to funding source"


def test_crop_cost_allocation_type_describes_recorded_allocation():
    from kokonut import CropCostAllocation

    allocation = CropCostAllocation(
        id="allocation-1",
        crop_cycle_id="cycle-1",
        expense_id="expense-1",
        allocation_method="area_based",
        allocated_amount=125.5,
        allocation_ratio=0.25,
    )

    assert allocation.allocated_amount == 125.5
    assert allocation.allocation_ratio == 0.25


def test_metric_definition_type_exposes_governance_and_validation_metadata():
    from kokonut import MetricDefinition

    definition = MetricDefinition(
        id="metric-1",
        metric_key="value_flowed",
        display_name="Value Flowed",
        source_tables=["value_flow_event"],
        validation_tests=[{"test": "value >= 0", "description": "Nonnegative"}],
        report_usage=["portfolio_summary"],
        category="ecological",
        participatory=True,
    )

    assert definition.validation_tests[0]["description"] == "Nonnegative"
    assert definition.report_usage == ["portfolio_summary"]
    assert definition.category == "ecological"
    assert definition.participatory is True


def test_metric_version_type_preserves_change_reason_and_formula_snapshot():
    from kokonut import MetricVersion

    version = MetricVersion(
        id="version-2",
        metric_id="metric-1",
        version=2,
        formula="revenue - costs",
        changes="Added shared-cost allocation",
        change_reason="Approved methodology update",
    )

    assert version.version == 2
    assert version.formula == "revenue - costs"
    assert version.change_reason == "Approved methodology update"


def test_metric_value_type_keeps_computation_separate_from_verification():
    from kokonut import MetricValue

    result = MetricValue(
        id="value-1",
        metric_id="metric-1",
        location_id="location-1",
        value=42.5,
        source_record_ids=["record-1", "record-2"],
        verified=False,
    )

    assert result.value == 42.5
    assert result.verified is False
    assert len(result.source_record_ids) == 2


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


def test_sensor_reading_sdk_type_exposes_required_location_and_quality():
    from kokonut.types import SensorReading

    reading = SensorReading(
        id="reading-1",
        sensor_id="sensor-1",
        location_id="location-1",
        reading_date="2026-10-17",
        value=8.5,
        unit="percent",
        quality="bad",
    )

    assert reading.location_id == "location-1"
    assert reading.quality == "bad"


def test_sensor_registry_and_alert_types_expose_schema_fields():
    from kokonut.types import AlertRule, SensorAlert, SensorDevice, SensorType

    sensor_type = SensorType(id="type-1", name="soil_moisture", unit="%")
    device = SensorDevice(
        id="device-1",
        name="North Probe",
        slug="north-probe",
        sensor_type_id=sensor_type.id,
        location_id="location-1",
        calibration_interval_days=None,
    )
    rule = AlertRule(
        id="rule-1",
        name="Dry soil",
        sensor_type_id=sensor_type.id,
        metric="value",
        operator="lt",
        threshold_value=20,
        enabled=None,
    )
    alert = SensorAlert(
        id="alert-1",
        sensor_device_id=device.id,
        alert_rule_id=rule.id,
        severity="warning",
        message="Soil moisture below threshold",
        triggered_at="2026-10-17T12:00:00Z",
        reading_id=None,
        status=None,
    )

    assert device.location_id == "location-1"
    assert rule.threshold_value == 20
    assert alert.triggered_at == "2026-10-17T12:00:00Z"


def test_loss_labor_and_field_note_types_expose_operational_schema_fields():
    from kokonut.types import FieldNote, LaborEvent, LossEvent

    loss = LossEvent(
        id="loss-1",
        location_id="location-1",
        loss_date="2026-10-17",
        loss_type="weather",
        evidence_hashes=["sha256:loss"],
    )
    labor = LaborEvent(
        id="labor-1",
        location_id="location-1",
        work_date="2026-10-17",
        hours_worked=6,
        total_cost=48,
    )
    note = FieldNote(
        id="note-1",
        location_id="location-1",
        note_date="2026-10-17",
        content="Synthetic fixture",
        tags=["test"],
    )

    assert loss.evidence_hashes == ["sha256:loss"]
    assert labor.total_cost == 48
    assert note.tags == ["test"]


def test_wallet_profile_sdk_type_exposes_schema_metadata():
    from kokonut.types import WalletProfile

    wallet = WalletProfile(
        id="wallet-1",
        address="0x0000000000000000000000000000000000000001",
        chain="gnosis",
        chain_id=100,
        role="operations",
        label="Kokonut Operations",
        first_seen_date="2026-10-17",
        last_active_date="2026-10-18",
        metadata={"source": "fixture"},
    )

    assert wallet.role == "operations"
    assert wallet.chain_id == 100
    assert wallet.metadata == {"source": "fixture"}


def test_attestation_record_type_exposes_evidence_and_migrated_fields():
    from kokonut.types import AttestationRecord

    attestation = AttestationRecord(
        id="attestation-1",
        schema_id="schema-1",
        claim_data={"outcome": "verified"},
        evidence_cids=["bafy-test"],
        evidence_urls=["private://evidence/1"],
        schema_version="1.0",
        private_payload_hash="sha256:private",
        verdict="accepted",
        evidence_reviewed=["photo-1"],
        evaluator_id="reviewer-1",
    )

    assert attestation.schema_id == "schema-1"
    assert attestation.evidence_cids == ["bafy-test"]
    assert attestation.evaluator_id == "reviewer-1"


def test_report_snapshot_type_exposes_location_freeze_and_public_fields():
    from kokonut.types import ReportSnapshot

    report = ReportSnapshot(
        id="report-1",
        report_name="Quarterly farm report",
        report_data={"summary": "fixture"},
        location_id="location-1",
        created_by="operator-1",
        frozen=True,
        public_interest_summary="Public summary",
        negative_findings=[{"finding": "finding-1"}],
        expires_at="2027-10-17T00:00:00Z",
    )

    assert report.report_name == "Quarterly farm report"
    assert report.frozen is True
    assert report.negative_findings == [{"finding": "finding-1"}]


def test_export_log_type_exposes_canonical_export_table_fields():
    from kokonut.types import ExportLog

    export_log = ExportLog(
        id="export-1",
        export_type="farm_data",
        user_id="user-1",
        target_table="harvest_event",
        filters={"status": "published"},
        row_count=42,
        file_size_bytes=2048,
        file_url="private://exports/export-1.csv",
        status="generating",
    )

    assert export_log.user_id == "user-1"
    assert export_log.row_count == 42
    assert export_log.status == "generating"


def test_noi_snapshot_type_exposes_canonical_financial_fields():
    from kokonut.types import NoiSnapshot

    snapshot = NoiSnapshot(
        id="snapshot-1",
        crop_cycle_id="cycle-1",
        location_id="location-1",
        period_start="2026-01-01",
        period_end="2026-03-31",
        gross_revenue=1200.0,
        returns_and_discounts=None,
        noi=430.0,
        inputs={"sales_event_ids": ["sale-1"]},
    )

    assert snapshot.gross_revenue == 1200.0
    assert snapshot.returns_and_discounts is None
    assert snapshot.inputs == {"sales_event_ids": ["sale-1"]}


def test_location_scoped_operational_methods_force_scope_and_preserve_options():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    options = ListOptions(filter={"location_id": {"_eq": "other"}, "status": {"_eq": "verified"}}, limit=10)

    client.loss_events.list_by_location("location-1", options)
    client.labor_events.list_by_location("location-1", options)
    client.field_notes.list_by_location("location-1", options)

    assert client.list_items.call_args_list == [
        ( ("loss_event", ListOptions(filter={"location_id": {"_eq": "location-1"}, "status": {"_eq": "verified"}}, limit=10)), {}),
        ( ("labor_event", ListOptions(filter={"location_id": {"_eq": "location-1"}, "status": {"_eq": "verified"}}, limit=10)), {}),
        ( ("field_note", ListOptions(filter={"location_id": {"_eq": "location-1"}, "status": {"_eq": "verified"}}, limit=10)), {}),
    ]


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
