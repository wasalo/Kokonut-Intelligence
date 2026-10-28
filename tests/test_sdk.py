"""SDK smoke tests — import and instantiate without network calls."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

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
    assert client.financial_transactions is not None
    assert client.cash_flow_snapshots is not None
    assert client.loss_events is not None
    assert client.labor_events is not None
    assert client.field_notes is not None
    assert issubclass(AuthenticationError, KokonutError)


def test_kokonut_types_import():
    from kokonut.types import ListOptions

    opts = ListOptions(limit=10)
    assert opts.limit == 10


def test_carbon_credit_ledger_types_are_read_models_with_sql_lifecycles():
    from decimal import Decimal

    from kokonut import (
        CarbonCredit,
        CarbonCreditStatus,
        CreditAdjustment,
        CreditAdjustmentStatus,
        CreditAdjustmentTriggerSource,
        CreditAdjustmentType,
        CreditRetirement,
        CreditRetirementStatus,
        CreditTransfer,
        CreditTransferStatus,
        CreditTransferType,
    )

    credit = CarbonCredit(
        id="credit-1",
        location_id="location-1",
        credit_code="KKNT-2026-TEST-0001",
        vintage_year=2026,
        methodology="IPCC 2006 Tier 2",
        initial_sequestration_tonnes=Decimal("12.3456"),
        current_sequestration_tonnes=Decimal("12.3456"),
        issuable_tonnes=Decimal("9.8765"),
        status="verified",
        metadata={"source": "reviewed"},
    )
    adjustment = CreditAdjustment(
        id="adjustment-1",
        credit_id=credit.id,
        location_id=credit.location_id,
        adjustment_type="measurement_update",
        previous_sequestration_tonnes=Decimal("12.3456"),
        new_sequestration_tonnes=Decimal("12.3000"),
        delta_tonnes=Decimal("-0.0456"),
        delta_pct=Decimal("-0.3695"),
        trigger_source="soil_carbon_measurement",
        within_margin=True,
        requires_review=False,
    )
    retirement = CreditRetirement(
        id="retirement-1",
        credit_id=credit.id,
        location_id=credit.location_id,
        retirement_reason="voluntary_retirement",
        retired_tonnes=Decimal("1.0000"),
        status="submitted",
    )
    transfer = CreditTransfer(
        id="transfer-1",
        credit_id=credit.id,
        location_id=credit.location_id,
        transfer_type="allocation",
        transferred_tonnes=Decimal("2.0000"),
        status="draft",
    )

    assert credit.current_sequestration_tonnes == Decimal("12.3456")
    assert adjustment.requires_review is False
    assert retirement.status == "submitted"
    assert transfer.transfer_type == "allocation"
    assert CarbonCreditStatus.__args__ == (
        "draft", "submitted", "verified", "published", "retired", "revoked", "rejected"
    )
    assert CreditAdjustmentStatus.__args__ == (
        "draft", "submitted", "verified", "published", "rejected"
    )
    assert CreditAdjustmentType.__args__ == (
        "measurement_update", "methodology_change", "reversal", "correction"
    )
    assert CreditAdjustmentTriggerSource.__args__ == (
        "tree_inventory", "soil_carbon_measurement", "ghg_emissions_inventory",
        "climate_impact_summary", "remote_sensing", "manual_override",
    )
    assert CreditRetirementStatus.__args__ == (
        "draft", "submitted", "verified", "published", "rejected", "cancelled"
    )
    assert CreditTransferStatus.__args__ == (
        "draft", "submitted", "verified", "published", "rejected"
    )
    assert CreditTransferType.__args__ == (
        "allocation", "sale", "grant", "internal_rebalance"
    )


def test_logout_clears_local_auth_when_remote_request_fails():
    import requests
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055", token="synthetic-token")
    client.session.post = Mock(side_effect=requests.ConnectionError("offline"))

    client.logout()

    assert "Authorization" not in client.session.headers
    client.session.post.assert_called_once_with("http://localhost:8055/auth/logout")


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


def test_protocol_sdk_model_is_a_passive_web3_catalog_record():
    from kokonut import Protocol

    protocol = Protocol(
        id="protocol-1",
        name="Celo Attestation Service",
        slug="celo-eas",
        chain="celo",
        protocol_type="attestation",
        category="governance",
        metadata={"read_only": True, "source": "catalog"},
    )

    assert protocol.slug == "celo-eas"
    assert protocol.chain == "celo"
    assert protocol.metadata == {"read_only": True, "source": "catalog"}


def test_attestation_schema_model_preserves_stored_eas_definition():
    from kokonut import AttestationSchema

    schema = AttestationSchema(
        id="schema-1",
        schema_uid="0xabc123",
        name="Farm Activity",
        chain="celo",
        schema_text="string activityType,uint256 activityDate",
        resolver_address="0x0000000000000000000000000000000000000001",
        version=2,
        active=True,
    )

    assert schema.schema_uid == "0xabc123"
    assert schema.version == 2
    assert schema.active is True
    assert "activityType" in schema.schema_text


def test_farm_activity_model_preserves_review_scope_and_source_option_metadata():
    from typing import get_type_hints

    from kokonut import ActivityTypeSourceOption, FarmActivity

    activity = FarmActivity(
        id="activity-1",
        location_id="location-1",
        activity_type="irrigation",
        activity_date="2026-10-18",
        farm_id="farm-1",
        duration_minutes=45,
        status="draft",
        materials_used={"items": ["water"]},
        activity_type_source_options=[{"option_id": 71, "label": "Irrigation"}],
    )

    assert activity.duration_minutes == 45
    assert activity.status == "draft"
    assert activity.materials_used == {"items": ["water"]}
    assert activity.activity_type_source_options == [
        {"option_id": 71, "label": "Irrigation"}
    ]
    assert get_type_hints(ActivityTypeSourceOption) == {"option_id": int, "label": str}


def test_farm_task_model_preserves_sql_constrained_planning_values():
    from kokonut import FarmTask, FarmTaskCategory, FarmTaskPriority, FarmTaskStatus

    task = FarmTask(
        id="task-1",
        location_id="location-1",
        task_name="Irrigate north plot",
        category="irrigation",
        priority="high",
        status="in_progress",
        farm_id="farm-1",
        duration_days=2,
        metadata={"plan": "morning rotation"},
        source_raw="legacy task payload",
    )

    assert task.category == "irrigation"
    assert task.priority == "high"
    assert task.status == "in_progress"
    assert task.metadata == {"plan": "morning rotation"}
    assert FarmTaskCategory.__args__ == (
        "planting", "weeding", "irrigation", "spraying", "harvesting",
        "maintenance", "training", "reporting", "other",
    )
    assert FarmTaskPriority.__args__ == ("low", "medium", "high", "critical")
    assert FarmTaskStatus.__args__ == ("pending", "in_progress", "completed", "cancelled")


def test_farm_task_relationship_models_preserve_composite_keys_and_source_identity():
    from kokonut import FarmTaskDependency, FarmTaskFrameworkStep, FarmTaskWeeklyPlan

    dependency = FarmTaskDependency(
        task_id="task-1",
        prerequisite_task_id="task-0",
        source_system="baserow",
        source_database_id=4,
        source_table_id=12,
        source_row_id=71,
        source_related_table_id=12,
        source_related_row_id=70,
    )
    framework_step = FarmTaskFrameworkStep(
        task_id="task-1", framework_step_id="step-1", source_system="baserow"
    )
    weekly_plan = FarmTaskWeeklyPlan(
        task_id="task-1", weekly_plan_id="week-1", source_system="baserow"
    )

    assert (dependency.task_id, dependency.prerequisite_task_id) == ("task-1", "task-0")
    assert dependency.source_related_row_id == 70
    assert (framework_step.task_id, framework_step.framework_step_id) == ("task-1", "step-1")
    assert (weekly_plan.task_id, weekly_plan.weekly_plan_id) == ("task-1", "week-1")


def test_crop_model_preserves_reference_metadata_and_schema_version():
    from kokonut import Crop

    crop = Crop(
        id="crop-1",
        name="Cacao",
        scientific_name="Theobroma cacao",
        variety="Trinitario",
        crop_category="tree",
        growing_season_days=180,
        expected_yield_per_ha=0.8,
        expected_yield_unit="tonnes_per_ha",
        water_needs="high",
        metadata={"origin": "reference catalog"},
        schema_version="common-data-schema-v1",
    )

    assert crop.scientific_name == "Theobroma cacao"
    assert crop.expected_yield_per_ha == 0.8
    assert crop.metadata == {"origin": "reference catalog"}
    assert crop.schema_version == "common-data-schema-v1"


def test_cash_flow_snapshot_preserves_inputs_without_claiming_calculation():
    from kokonut import CashFlowSnapshot

    snapshot = CashFlowSnapshot(
        id="cash-flow-1",
        location_id="location-1",
        period_start="2026-01-01",
        period_end="2026-03-31",
        total_inflows=12000.0,
        total_outflows=8500.0,
        net_cash_flow=3500.0,
        running_balance=7200.0,
        calculation_version="1.0",
        inputs={"currency": "USD", "source_snapshot": "quarterly-close"},
    )

    assert snapshot.net_cash_flow == 3500.0
    assert snapshot.inputs == {"currency": "USD", "source_snapshot": "quarterly-close"}


def test_infrastructure_asset_preserves_inventory_and_constrained_lifecycle_status():
    from kokonut import InfrastructureAsset

    asset = InfrastructureAsset(
        id="asset-1",
        location_id="location-1",
        name="North well pump",
        asset_type="pump",
        condition_status="good",
        capacity=4.5,
        capacity_unit="kW",
        status="maintenance",
        metadata={"inspection_source": "field register"},
        schema_version="common-data-schema-v1",
    )

    assert asset.asset_type == "pump"
    assert asset.condition_status == "good"
    assert asset.status == "maintenance"
    assert asset.metadata == {"inspection_source": "field register"}


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


def test_price_observation_model_preserves_consensus_and_review_as_stored_fields():
    from kokonut import PriceAggregationMethod, PriceObservation

    observation = PriceObservation(
        id="price-1",
        price_date="2026-10-18",
        commodity_code="CACAO",
        price_per_unit=4.25,
        currency="USD",
        source_count=3,
        aggregation_method="median_consensus",
        source_metadata={"sources_used": ["source-a", "source-b", "source-c"]},
        verified=False,
    )

    assert observation.price_per_unit == 4.25
    assert observation.aggregation_method == "median_consensus"
    assert observation.source_metadata == {
        "sources_used": ["source-a", "source-b", "source-c"]
    }
    assert observation.verified is False
    assert PriceAggregationMethod.__args__ == (
        "single", "median_consensus", "weighted_average", "on_chain_attested"
    )


def test_oracle_price_log_keeps_attestation_reference_separate_from_submission():
    from kokonut import OraclePriceLog

    entry = OraclePriceLog(
        id="oracle-price-1",
        commodity="cacao",
        price=4.25,
        price_timestamp="2026-10-18T12:00:00Z",
        source="synthetic-feed",
        aggregation_method="weighted_average",
        attestation_uid="0xsynthetic",
        chain="celo",
        metadata={"round": 17},
    )

    assert entry.attestation_uid == "0xsynthetic"
    assert entry.chain == "celo"
    assert entry.metadata == {"round": 17}


def test_actuation_log_keeps_approval_state_and_command_as_stored_data():
    from kokonut import ActuationLog, ActuationLogStatus

    log = ActuationLog(
        id="actuation-1",
        actuator_type="irrigation",
        actuator_command="open_valve",
        command_payload={"duration_seconds": 30},
        trigger_source="sensor_alert",
        status="requires_approval",
        human_approval_required=True,
        source_alert_event_id="event-1",
    )

    assert log.status == "requires_approval"
    assert log.human_approval_required is True
    assert log.source_alert_event_id == "event-1"
    assert ActuationLogStatus.__args__ == (
        "pending", "requires_approval", "approved", "sent", "acknowledged",
        "executed", "failed", "cancelled"
    )


def test_sensor_anomaly_effect_exposes_durable_receipt_without_detection_behavior():
    from kokonut import SensorAnomalyEffect, SensorAnomalyEffectOutcome

    effect = SensorAnomalyEffect(
        source_reading_id="reading-1",
        alert_rule_id="rule-1",
        source_event_id="event-1",
        outcome="alert_created",
        created_at="2026-10-18T12:00:00Z",
        updated_at="2026-10-18T12:00:00Z",
        sensor_alert_id="alert-1",
        location_id="location-1",
    )

    assert effect.outcome == "alert_created"
    assert effect.sensor_alert_id == "alert-1"
    assert SensorAnomalyEffectOutcome.__args__ == ("no_match", "cooldown", "alert_created")


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


def test_weather_observation_type_preserves_stored_measurements_without_ingestion():
    from kokonut import WeatherObservation

    observation = WeatherObservation(
        id="weather-1",
        location_id="location-1",
        observation_date="2026-10-18",
        source="station",
        temperature_c=28.5,
        rainfall_mm=12.4,
        metadata={"station_code": "synthetic-1"},
        source_raw={"provider_record": "synthetic"},
        schema_version="1.0",
    )

    assert observation.temperature_c == 28.5
    assert observation.rainfall_mm == 12.4
    assert observation.metadata == {"station_code": "synthetic-1"}
    assert observation.source_raw == {"provider_record": "synthetic"}
    assert observation.schema_version == "1.0"


def test_soil_sample_type_preserves_measurements_and_source_lineage():
    from kokonut import SoilSample

    sample = SoilSample(
        id="sample-1",
        plot_id="plot-1",
        location_id="location-1",
        sample_date="2026-10-18",
        ph=6.4,
        organic_carbon_pct=2.15,
        lab_name="Synthetic Lab",
        source_system="lab_import",
        source_raw={"report": "synthetic"},
        schema_version="1.0",
        status="submitted",
        lab_accredited=True,
        point_geometry={"type": "Point", "coordinates": [-69.9, 18.5]},
    )

    assert sample.ph == 6.4
    assert sample.organic_carbon_pct == 2.15
    assert sample.source_raw == {"report": "synthetic"}
    assert sample.schema_version == "1.0"
    assert sample.status == "submitted"
    assert sample.lab_accredited is True
    assert sample.point_geometry == {"type": "Point", "coordinates": [-69.9, 18.5]}


def test_soil_carbon_measurement_type_preserves_evidence_and_review_state():
    from kokonut import SoilCarbonMeasurement

    measurement = SoilCarbonMeasurement(
        id="carbon-1",
        plot_id="plot-1",
        location_id="location-1",
        measurement_date="2026-10-18",
        carbon_pct=2.15,
        organic_carbon_stock=42.8,
        evidence_urls=["https://example.invalid/lab-report"],
        status="submitted",
        source_raw={"lab_batch": "synthetic"},
    )

    assert measurement.carbon_pct == 2.15
    assert measurement.evidence_urls == ["https://example.invalid/lab-report"]
    assert measurement.status == "submitted"
    assert measurement.source_raw == {"lab_batch": "synthetic"}


def test_environmental_baseline_type_preserves_value_evidence_and_lineage():
    from kokonut import EnvironmentalBaseline

    baseline = EnvironmentalBaseline(
        id="baseline-1",
        location_id="location-1",
        metric_name="soil_carbon",
        baseline_value=42.8,
        unit="tC/ha",
        evidence_urls=["https://example.invalid/baseline"],
        source_system="field_survey",
        source_raw={"survey": "synthetic"},
    )

    assert baseline.baseline_value == 42.8
    assert baseline.evidence_urls == ["https://example.invalid/baseline"]
    assert baseline.source_raw == {"survey": "synthetic"}


def test_species_observation_type_preserves_constrained_ecology_and_lifecycle():
    from kokonut import SpeciesObservation

    observation = SpeciesObservation(
        id="species-1",
        location_id="location-1",
        observation_date="2026-10-18",
        species_name="Synthetic species",
        evidence_urls=["https://example.invalid/observation"],
        trophic_level="producer",
        conservation_status="least_concern",
        status="submitted",
    )

    assert observation.trophic_level == "producer"
    assert observation.conservation_status == "least_concern"
    assert observation.status == "submitted"


def test_remote_sensing_type_preserves_nullable_plot_and_spatial_shapes():
    from kokonut import RemoteSensingObservation

    observation = RemoteSensingObservation(
        id="remote-1",
        location_id="location-1",
        observation_date="2026-10-18",
        plot_id=None,
        ndvi=0.72,
        bbox={"type": "Polygon", "coordinates": [[[-70.0, 18.0], [-69.9, 18.0], [-69.9, 18.1], [-70.0, 18.0]]]},
        centroid={"type": "Point", "coordinates": [-69.95, 18.05]},
        band_nir=0.61,
        source_raw={"asset": "synthetic"},
    )

    assert observation.plot_id is None
    assert observation.ndvi == 0.72
    assert observation.bbox["type"] == "Polygon"
    assert observation.centroid["type"] == "Point"
    assert observation.band_nir == 0.61


def test_mrv_claim_and_verification_review_keep_attestation_and_review_separate():
    from kokonut import MrvClaim, VerificationReview

    claim = MrvClaim(
        id="claim-1",
        location_id="location-1",
        claim_type="soil_carbon_change",
        claim_date="2026-10-18",
        claim_data={"change_pct": 4.2},
        source_record_ids=["measurement-1"],
        status="submitted",
        attestation_uid="0x" + "a" * 64,
        evidence_maturity=5,
    )
    review = VerificationReview(
        id="review-1",
        claim_id=claim.id,
        reviewer_id="reviewer-1",
        review_date="2026-10-18",
        result="approved",
        evidence_urls=["https://example.invalid/review"],
    )

    assert claim.status == "submitted"
    assert claim.attestation_uid.startswith("0x")
    assert claim.source_record_ids == ["measurement-1"]
    assert review.result == "approved"
    assert review.claim_id == claim.id


def test_forecast_scenario_type_exposes_assumptions_without_running_engine():
    from kokonut import ForecastScenario

    scenario = ForecastScenario(
        id="scenario-1",
        name="Base case",
        assumptions={"rainfall_mm": 1200},
        price_assumptions={"cocoa_usd_per_tonne": 4200},
        status="draft",
    )

    assert scenario.assumptions["rainfall_mm"] == 1200
    assert scenario.price_assumptions["cocoa_usd_per_tonne"] == 4200


def test_forecast_output_type_exposes_results_and_confidence_inputs():
    from kokonut import ForecastOutput

    output = ForecastOutput(
        id="forecast-1",
        scenario_id="scenario-1",
        metric_name="crop_noi",
        value=5200.0,
        confidence_low=4700.0,
        confidence_high=5700.0,
        confidence_level=0.9,
        inputs={"source": "synthetic"},
    )

    assert output.value == 5200.0
    assert output.confidence_level == 0.9
    assert output.inputs["source"] == "synthetic"


def test_ai_summary_type_preserves_lineage_and_review_as_distinct_fields():
    from kokonut import AiSummary

    summary = AiSummary(
        id="summary-1",
        subject_type="location",
        subject_id="location-1",
        content="Synthetic draft summary",
        source_record_ids=["record-1"],
        source_tables=["metric_value"],
        model_version="rules-v1",
        confidence=0.75,
        status="draft",
        created_by_worker_id="worker-1",
    )

    assert summary.source_record_ids == ["record-1"]
    assert summary.source_tables == ["metric_value"]
    assert summary.status == "draft"
    assert summary.reviewed_by is None
    assert summary.created_by_worker_id == "worker-1"


def test_dashboard_dataset_type_uses_registered_query_and_preserves_legacy_sql():
    from kokonut import DashboardDataset

    dataset = DashboardDataset(
        id="dataset-1",
        name="Synthetic farm metrics",
        query_id="public_farm_summary_count",
        query_sql="SELECT 1 AS value",
        refresh_interval_minutes=60,
        status="published",
        metadata={"audience": "community"},
    )

    assert dataset.query_id == "public_farm_summary_count"
    # The SDK keeps the archived field representable, but execution is
    # selected by query_id and the Kernel never runs this SQL text.
    assert dataset.query_sql == "SELECT 1 AS value"
    assert dataset.status == "published"
    assert dataset.metadata["audience"] == "community"


def test_time_series_forecast_and_accuracy_types_preserve_stored_values():
    from kokonut import ForecastAccuracy, TimeSeriesForecast, VariogramModel

    forecast = TimeSeriesForecast(
        id="forecast-1",
        metric_key="soil_moisture",
        location_id="location-1",
        model_params={"order": [1, 0, 1]},
        forecast_values=[12.5, 13.0],
        prediction_intervals={"confidence": 0.95, "points": []},
        forecast_horizon=2,
        time_unit="day",
        training_points=30,
        forecast_at="2026-10-18T00:00:00Z",
        status="active",
        created_at="2026-10-18T00:00:00Z",
    )
    accuracy = ForecastAccuracy(
        id="accuracy-1",
        forecast_id=forecast.id,
        actual_timestamp="2026-10-19T00:00:00Z",
        predicted_value=12.5,
        actual_value=12.0,
        error_abs=0.5,
        error_squared=0.25,
        computed_at="2026-10-19T00:00:00Z",
        created_at="2026-10-19T00:00:00Z",
    )

    assert forecast.forecast_values == [12.5, 13.0]
    assert forecast.model_type == "arima"
    assert accuracy.error_abs == 0.5
    assert accuracy.is_within_ci is None

    variogram = VariogramModel(
        id="variogram-1",
        property_key="soil_carbon",
        model_type="matern",
        sill=1.5,
        range=30.0,
        nugget=0.1,
        fitted_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
    )
    assert variogram.model_type == "matern"
    assert variogram.location_id is None
    assert variogram.partial_sill is None


def test_geostatistics_models_preserve_stored_results_and_literals():
    from typing import get_args

    from kokonut import (
        GeostatCVResult,
        GeostatCVStrategy,
        GeostatRealization,
        GeostatRealizationPoint,
        GeostatSimulationMethod,
        KrigingMethod,
        KrigingPoint,
        KrigingPrediction,
        SensorNetworkDesign,
        SpatialAutocorrelation,
        SpatialAutocorrelationMetric,
        SpatialWeightsType,
    )

    prediction = KrigingPrediction(
        id="prediction-1",
        location_id="location-1",
        variogram_model_id="variogram-1",
        property_key="soil_carbon",
        n_points=3,
        method="ordinary",
        created_at="2026-10-18T00:00:00Z",
    )
    prediction_point = KrigingPoint(
        id="kriging-point-1",
        prediction_id=prediction.id,
        point_geometry={"type": "Point", "coordinates": [-69.9, 18.5]},
        predicted_value=14.2,
    )
    realization = GeostatRealization(
        id="realization-1",
        location_id="location-1",
        variogram_model_id="variogram-1",
        property_key="soil_carbon",
        realization_number=1,
        n_points=3,
        method="sgs",
        created_at="2026-10-18T00:00:00Z",
    )
    realization_point = GeostatRealizationPoint(
        id="realization-point-1",
        realization_id=realization.id,
        point_geometry={"type": "Point", "coordinates": [-69.9, 18.5]},
        simulated_value=13.8,
    )
    autocorrelation = SpatialAutocorrelation(
        id="autocorrelation-1",
        location_id="location-1",
        property_key="soil_carbon",
        metric="morans_i",
        statistic_value=0.42,
        n_samples=30,
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
        spatial_weights_type="knn",
    )
    cv_result = GeostatCVResult(
        id="cv-1",
        location_id="location-1",
        property_key="soil_carbon",
        cv_strategy="spatial_block",
        n_folds=4,
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
        fold_results=[{"fold": 1, "rmse": 0.8}],
    )
    network_design = SensorNetworkDesign(
        id="network-design-1",
        location_id="location-1",
        property_key="soil_carbon",
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
        recommended_n_sensors=12,
    )

    assert prediction.method == "ordinary"
    assert prediction_point.point_geometry["coordinates"] == [-69.9, 18.5]
    assert realization.method == "sgs"
    assert realization_point.simulated_value == 13.8
    assert autocorrelation.spatial_weights_type == "knn"
    assert cv_result.fold_results == [{"fold": 1, "rmse": 0.8}]
    assert network_design.recommended_n_sensors == 12
    assert get_args(KrigingMethod) == ("ordinary", "simple", "indicator")
    assert get_args(GeostatSimulationMethod) == ("sgs", "sis", "turning_bands")
    assert get_args(SpatialAutocorrelationMetric) == ("morans_i", "gearys_c", "join_count")
    assert get_args(SpatialWeightsType) == ("queen", "rook", "distance", "knn")
    assert get_args(GeostatCVStrategy) == ("spatial_block", "leave_one_out", "k_fold")


def test_demand_forecast_type_keeps_estimate_provenance_and_review_state():
    from kokonut import DemandForecast

    forecast = DemandForecast(
        id="demand-1",
        location_id="location-1",
        forecast_type="buyer_pipeline",
        forecast_period_start="2026-11-01",
        forecast_period_end="2026-11-30",
        predicted_quantity=250.0,
        unit="kg",
        status="draft",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        inputs={"pipeline_records": 3},
        source_raw={"fixture": "synthetic"},
    )

    assert forecast.predicted_quantity == 250.0
    assert forecast.inputs["pipeline_records"] == 3
    assert forecast.status == "draft"
    assert forecast.verified_by is None


def test_market_size_and_demand_trend_types_preserve_scoped_measures():
    from kokonut import DemandTrend, MarketSizeEstimate

    market = MarketSizeEstimate(
        id="market-1",
        location_id="location-1",
        market_scope="regional",
        status="draft",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        tam_value=100000.0,
        metadata={"currency": "USD"},
    )
    trend = DemandTrend(
        id="trend-1",
        location_id="location-1",
        analysis_type="seasonal_pattern",
        period_start="2026-01-01",
        period_end="2026-12-31",
        status="draft",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        peak_month=10,
        inputs={"months_observed": 12},
    )

    assert market.market_scope == "regional"
    assert market.tam_value == 100000.0
    assert trend.analysis_type == "seasonal_pattern"
    assert trend.peak_month == 10


def test_buyer_signal_and_market_match_types_keep_intent_separate_from_supply():
    from kokonut import BuyerDemandSignal, ProductionMarketMatch

    signal = BuyerDemandSignal(
        id="signal-1",
        location_id="location-1",
        signal_type="written_order",
        signal_date="2026-10-18",
        currency="USD",
        recurring=False,
        status="submitted",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        commitment_level="probable",
        metadata={"source": "synthetic"},
    )
    match = ProductionMarketMatch(
        id="match-1",
        location_id="location-1",
        period_start="2026-11-01",
        period_end="2026-11-30",
        status="draft",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        pipeline_demand_tonnes=4.0,
        supply_demand_gap_tonnes=1.5,
    )

    assert signal.commitment_level == "probable"
    assert signal.verified_by is None
    assert match.pipeline_demand_tonnes == 4.0
    assert match.supply_demand_gap_tonnes == 1.5


def test_buyer_segment_type_exposes_stored_criteria_and_measures():
    from kokonut import BuyerSegment

    segment = BuyerSegment(
        id="segment-1",
        location_id="location-1",
        segment_name="Repeat regional buyers",
        segment_type="behavior_based",
        criteria={"minimum_orders": 3},
        status="draft",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
        buyer_count=12,
        segment_value="high_value",
    )

    assert segment.criteria["minimum_orders"] == 3
    assert segment.buyer_count == 12
    assert segment.segment_value == "high_value"


def test_trend_estimate_smoothing_and_change_point_types_store_results_only():
    from kokonut import ChangePoint, TrendEstimate, TrendSmoothing

    estimate = TrendEstimate(
        id="trend-1",
        metric_key="soil_carbon",
        location_id="location-1",
        period_start="2025-01-01T00:00:00Z",
        period_end="2026-01-01T00:00:00Z",
        data_points=12,
        slope=0.4,
        intercept=1.2,
        r_squared=0.82,
        standard_error=0.1,
        direction="improving",
        confidence_level="moderate",
        time_unit="month",
        computed_at="2026-10-18T00:00:00Z",
        computed_by="synthetic",
        created_at="2026-10-18T00:00:00Z",
    )
    smooth = TrendSmoothing(
        id="smooth-1",
        metric_key="soil_carbon",
        location_id="location-1",
        smoothing_type="moving_average",
        original_value=10.0,
        smoothed_value=9.5,
        timestamp="2026-10-18T00:00:00Z",
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
    )
    point = ChangePoint(
        id="change-1",
        metric_key="soil_carbon",
        location_id="location-1",
        detection_method="cusum",
        change_point_index=8,
        magnitude=0.7,
        direction="increase",
        confidence=0.9,
        segment_count=2,
        status="detected",
        detected_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
    )

    assert estimate.direction == "improving"
    assert smooth.smoothed_value == 9.5
    assert point.status == "detected"


def test_seasonal_decomposition_and_trend_dashboard_preserve_outputs():
    from kokonut import SeasonalDecomposition, TrendDashboardMetric

    decomposition = SeasonalDecomposition(
        id="decomposition-1",
        metric_key="rainfall",
        location_id="location-1",
        period=12,
        trend_component=[1.0, 1.5],
        seasonal_component=[0.2, -0.1],
        residual_component=[0.05, -0.02],
        data_points=24,
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
    )
    dashboard = TrendDashboardMetric(
        id="dashboard-1",
        metric_key="rainfall",
        location_id="location-1",
        computed_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
        change_point_count=2,
        forecast_accuracy_mae=0.3,
    )

    assert decomposition.decomposition_method == "classical"
    assert decomposition.trend_component == [1.0, 1.5]
    assert dashboard.change_point_count == 2


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
    from dataclasses import fields

    from kokonut.types import ExportLog

    assert {field.name for field in fields(ExportLog)} == {
        "id", "user_id", "export_type", "target_table", "filters",
        "row_count", "file_size_bytes", "file_url", "status", "created_at",
    }

    export_log = ExportLog(
        id="export-1",
        export_type="csv",
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


def test_export_get_forwards_requested_fields_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    client.get_item = Mock(return_value={"id": "export-1", "status": "completed"})

    result = client.exports.get("export-1", fields=["id", "status"])

    assert result == {"id": "export-1", "status": "completed"}
    client.get_item.assert_called_once_with("export_log", "export-1", ["id", "status"])


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


def test_location_read_methods_are_typed_location_scoped_reads_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "credit-1"})
    collections = [
        (client.carbon_credits, "carbon_credit"),
        (client.credit_adjustments, "credit_adjustment"),
        (client.credit_retirements, "credit_retirement"),
        (client.credit_transfers, "credit_transfer"),
        (client.financial_transactions, "financial_transaction"),
        (client.cash_flow_snapshots, "cash_flow_snapshot"),
        (client.weather_observations, "weather_observation"),
        (client.sensor_devices, "sensor_device"),
        (client.sensor_alerts, "sensor_alert"),
        (client.variogram_models, "variogram_model"),
        (client.kriging_predictions, "kriging_prediction"),
        (client.geostat_realizations, "geostat_realization"),
        (client.spatial_autocorrelations, "spatial_autocorrelation"),
        (client.geostat_cv_results, "geostat_cv_result"),
        (client.sensor_network_designs, "sensor_network_design"),
        (client.organic_certification_records, "organic_certification_record"),
        (client.organic_transition_plans, "organic_transition_plan"),
        (client.prohibited_substance_records, "prohibited_substance_record"),
        (client.buffer_zones, "buffer_zone"),
        (client.organic_input_audits, "organic_input_audit"),
        (client.harvest_handling_records, "harvest_handling_record"),
        (client.organic_compliance_checklists, "organic_compliance_checklist"),
        (client.organic_readiness_assessments, "organic_readiness_assessment"),
        (client.system_variables, "system_variable"),
        (client.stock_flow_runs, "stock_flow_run"),
        (client.system_archetypes, "system_archetype"),
        (client.leverage_assessments, "leverage_assessment"),
        (client.structural_assumptions, "structural_assumption"),
        (client.soil_samples, "soil_sample"),
        (client.soil_carbon_measurements, "soil_carbon_measurement"),
        (client.environmental_baselines, "environmental_baseline"),
        (client.species_observations, "species_observation"),
        (client.remote_sensing_observations, "remote_sensing_observation"),
        (client.mrv_claims, "mrv_claim"),
        (client.metric_values, "metric_value"),
        (client.forecast_scenarios, "forecast_scenario"),
        (client.forecast_outputs, "forecast_output"),
        (client.time_series_forecasts, "time_series_forecast"),
        (client.demand_forecasts, "demand_forecast"),
        (client.market_size_estimates, "market_size_estimate"),
        (client.price_observations, "price_observation"),
        (client.demand_trends, "demand_trend"),
        (client.buyer_demand_signals, "buyer_demand_signal"),
        (client.production_market_matches, "production_market_match"),
        (client.buyer_segments, "buyer_segment"),
        (client.value_flow_events, "value_flow_event"),
        (client.trend_estimates, "trend_estimate"),
        (client.trend_smoothing, "trend_smoothing"),
        (client.change_points, "change_point"),
        (client.seasonal_decompositions, "seasonal_decomposition"),
        (client.trend_dashboard_metrics, "trend_dashboard_metric"),
        (client.infrastructure_assets, "infrastructure_asset"),
        (client.farm_tasks, "farm_task"),
    ]
    options = ListOptions(
        filter={"location_id": {"_eq": "other"}, "status": {"_eq": "verified"}},
        sort=["created_at"],
        fields=["id", "location_id"],
        limit=20,
    )

    for methods, collection in collections:
        assert methods.list(options) == []
        client.list_items.assert_called_with(collection, options)
        assert methods.get("credit-1", ["id"]) == {"id": "credit-1"}
        client.get_item.assert_called_with(collection, "credit-1", ["id"])
        assert methods.list_by_location("location-1", options) == []
        _, scoped_options = client.list_items.call_args.args
        assert scoped_options.filter == {
            "location_id": {"_eq": "location-1"},
            "status": {"_eq": "verified"},
        }
        assert scoped_options.sort == ["created_at"]
        assert scoped_options.fields == ["id", "location_id"]
        assert scoped_options.limit == 20
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))


def test_forecast_accuracy_read_methods_are_scoped_to_parent_forecast_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "accuracy-1"})
    methods = client.forecast_accuracies
    options = ListOptions(
        filter={"forecast_id": {"_eq": "other-forecast"}, "is_within_ci": {"_eq": True}},
        sort=["actual_timestamp"],
        fields=["id", "forecast_id", "error_abs"],
        limit=10,
        offset=5,
    )

    assert methods.list(options) == []
    client.list_items.assert_called_with("forecast_accuracy", options)
    assert methods.get("accuracy-1", ["id"]) == {"id": "accuracy-1"}
    client.get_item.assert_called_with("forecast_accuracy", "accuracy-1", ["id"])
    assert methods.list_by_forecast("forecast-1", options) == []
    _, scoped_options = client.list_items.call_args.args
    assert scoped_options.filter == {
        "forecast_id": {"_eq": "forecast-1"},
        "is_within_ci": {"_eq": True},
    }
    assert scoped_options.sort == ["actual_timestamp"]
    assert scoped_options.fields == ["id", "forecast_id", "error_abs"]
    assert scoped_options.limit == 10
    assert scoped_options.offset == 5
    assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))


def test_geostat_point_reads_are_scoped_to_their_parent_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "point-1"})
    options = ListOptions(
        filter={
            "prediction_id": {"_eq": "other-prediction"},
            "realization_id": {"_eq": "other-realization"},
            "quality": {"_eq": "good"},
        },
        sort=["id"],
        fields=["id", "point_geometry"],
        limit=15,
        offset=30,
    )

    assert client.kriging_points.list_by_prediction("prediction-1", options) == []
    _, prediction_options = client.list_items.call_args.args
    assert client.list_items.call_args.args[0] == "kriging_point"
    assert prediction_options.filter == {
        "realization_id": {"_eq": "other-realization"},
        "prediction_id": {"_eq": "prediction-1"},
        "quality": {"_eq": "good"},
    }
    assert prediction_options.sort == ["id"]
    assert prediction_options.fields == ["id", "point_geometry"]
    assert prediction_options.limit == 15
    assert prediction_options.offset == 30
    assert client.geostat_realization_points.list_by_realization("realization-1", options) == []
    _, realization_options = client.list_items.call_args.args
    assert client.list_items.call_args.args[0] == "geostat_realization_point"
    assert realization_options.filter == {
        "prediction_id": {"_eq": "other-prediction"},
        "realization_id": {"_eq": "realization-1"},
        "quality": {"_eq": "good"},
    }
    assert realization_options.sort == ["id"]
    assert realization_options.fields == ["id", "point_geometry"]
    assert realization_options.limit == 15
    assert realization_options.offset == 30
    for methods in (client.kriging_points, client.geostat_realization_points):
        assert methods.get("point-1", ["id"]) == {"id": "point-1"}
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))
        assert not hasattr(methods, "list_by_location")


def test_reference_read_methods_are_typed_catalog_reads_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "catalog-1"})
    collections = [
        (client.crops, "crop"),
        (client.protocols, "protocol"),
        (client.sensor_types, "sensor_type"),
        (client.attestation_schemas, "attestation_schema"),
        (client.causal_loops, "causal_loop"),
        (client.stock_flow_models, "stock_flow_model"),
        (client.time_delays, "time_delay"),
    ]
    options = ListOptions(limit=25, fields=["id", "name"], sort=["name"])

    for methods, collection in collections:
        assert methods.list(options) == []
        client.list_items.assert_called_with(collection, options)
        assert methods.get("catalog-1", ["id"]) == {"id": "catalog-1"}
        client.get_item.assert_called_with(collection, "catalog-1", ["id"])
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))


def test_causal_links_are_read_only_and_scoped_to_the_parent_loop():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "link-1"})
    options = ListOptions(
        filter={"loop_id": {"_eq": "other-loop"}, "polarity": {"_eq": "+"}},
        fields=["id", "loop_id", "source_variable"],
        limit=12,
        offset=24,
    )

    assert client.causal_links.list(options) == []
    client.list_items.assert_called_with("causal_link", options)
    assert client.causal_links.list_by_loop("loop-1", options) == []
    _, scoped_options = client.list_items.call_args.args
    assert scoped_options.filter == {
        "loop_id": {"_eq": "loop-1"},
        "polarity": {"_eq": "+"},
    }
    assert scoped_options.fields == ["id", "loop_id", "source_variable"]
    assert scoped_options.limit == 12
    assert scoped_options.offset == 24
    assert client.causal_links.get("link-1", ["id"]) == {"id": "link-1"}
    client.get_item.assert_called_with("causal_link", "link-1", ["id"])
    assert not any(
        hasattr(client.causal_links, name) for name in ("create", "update", "delete")
    )
    assert not hasattr(client.causal_links, "list_by_location")


def test_ooda_reads_are_location_and_assessment_scoped_and_read_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "assessment-1"})
    options = ListOptions(
        filter={"location_id": {"_eq": "other-location"}, "status": {"_eq": "verified"}},
        fields=["id", "location_id", "status"],
        sort=["-created_at"],
        limit=12,
        offset=24,
    )

    for methods, collection in (
        (client.situation_assessments, "situation_assessment"),
        (client.ooda_cycle_logs, "ooda_cycle_log"),
    ):
        assert methods.list(options) == []
        client.list_items.assert_called_with(collection, options)
        assert methods.get("record-1", ["id"]) == {"id": "assessment-1"}
        client.get_item.assert_called_with(collection, "record-1", ["id"])
        assert methods.list_by_location("location-1", options) == []
        _, scoped = client.list_items.call_args.args
        assert scoped.filter == {
            "location_id": {"_eq": "location-1"},
            "status": {"_eq": "verified"},
        }
        assert scoped.fields == options.fields
        assert scoped.sort == options.sort
        assert scoped.limit == 12
        assert scoped.offset == 24
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))

    for methods, collection in (
        (client.assessment_signals, "assessment_signal"),
        (client.assessment_dimensions, "assessment_dimension"),
    ):
        assert methods.list(options) == []
        client.list_items.assert_called_with(collection, options)
        assert methods.get("evidence-1", ["id"]) == {"id": "assessment-1"}
        client.get_item.assert_called_with(collection, "evidence-1", ["id"])
        assert methods.list_by_assessment("assessment-1", options) == []
        _, scoped = client.list_items.call_args.args
        assert scoped.filter == {
            "location_id": {"_eq": "other-location"},
            "assessment_id": {"_eq": "assessment-1"},
            "status": {"_eq": "verified"},
        }
        assert scoped.fields == options.fields
        assert scoped.sort == options.sort
        assert scoped.limit == 12
        assert scoped.offset == 24
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))


def test_ooda_read_models_preserve_canonical_literals_and_shapes():
    from kokonut import (
        AssessmentDimension,
        AssessmentSignal,
        OodaCycleLog,
        SituationAssessment,
    )

    assessment = SituationAssessment(
        id="assessment-1", location_id="location-1", assessment_type="full",
        situation_grade="stable", composite_score=0.8, confidence_level="moderate",
        evidence_maturity=3, anomaly_count=1, critical_anomaly_count=0,
        metric_trend_summary={"soil": "improving"}, dimension_summaries={"ecology": {}},
        recommendations=[{"action": "review"}], period_start="2026-01-01",
        period_end="2026-01-31", assessed_at="2026-02-01", assessed_by="reviewer",
        methodology_version="v1.0", status="verified", created_at="2026-02-01",
        updated_at="2026-02-01",
    )
    signal = AssessmentSignal(
        id="signal-1", assessment_id=assessment.id, signal_type="metric_trend",
        signal_key="soil_carbon", signal_direction="positive", weight=1.0,
        created_at="2026-02-01",
    )
    dimension = AssessmentDimension(
        id="dimension-1", assessment_id=assessment.id, dimension_key="ecology",
        dimension_name="Ecology", risk_score=0.2, trend="improving", signal_count=1,
        confidence_level="high", created_at="2026-02-01",
    )
    cycle = OodaCycleLog(
        id="cycle-1", correlation_id="correlation-1", location_id="location-1",
        cycle_type="manual", decision_type="review", observe_sources=["metrics"],
        orient_frameworks_used=["CRISP"], status="completed", created_at="2026-02-01",
        updated_at="2026-02-01", outcome_type="effective",
    )

    assert assessment.recommendations == [{"action": "review"}]
    assert signal.signal_direction == "positive"
    assert dimension.trend == "improving"
    assert cycle.outcome_type == "effective"


def test_crisp_assessment_reads_are_location_or_assessment_scoped_and_read_only():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    client.get_item = Mock(return_value={"id": "crisp-1"})
    options = ListOptions(
        filter={
            "location_id": {"_eq": "other-location"},
            "assessment_id": {"_eq": "other-assessment"},
            "status": {"_eq": "verified"},
        },
        fields=["id", "location_id", "assessment_id", "status"],
        sort=["-created_at"],
        limit=12,
        offset=24,
    )

    assert client.crisp_risk_assessments.list(options) == []
    client.list_items.assert_called_with("crisp_risk_assessment", options)
    assert client.crisp_risk_assessments.get("crisp-1", ["id"]) == {"id": "crisp-1"}
    client.get_item.assert_called_with("crisp_risk_assessment", "crisp-1", ["id"])
    assert client.crisp_risk_assessments.list_by_location("location-1", options) == []
    _, scoped = client.list_items.call_args.args
    assert scoped.filter == {
        "location_id": {"_eq": "location-1"},
        "assessment_id": {"_eq": "other-assessment"},
        "status": {"_eq": "verified"},
    }

    details = (
        (client.crisp_carbon_yield_risks, "crisp_carbon_yield_risk"),
        (client.crisp_climate_risks, "crisp_climate_risk"),
        (client.crisp_policy_risks, "crisp_policy_risk"),
        (client.crisp_financial_risks, "crisp_financial_risk"),
        (client.crisp_implementation_risks, "crisp_implementation_risk"),
    )
    for methods, collection in details:
        assert methods.list(options) == []
        client.list_items.assert_called_with(collection, options)
        assert methods.get("dimension-1", ["id"]) == {"id": "crisp-1"}
        client.get_item.assert_called_with(collection, "dimension-1", ["id"])
        assert methods.list_by_location("location-1", options) == []
        _, location_scope = client.list_items.call_args.args
        assert location_scope.filter == {
            "location_id": {"_eq": "location-1"},
            "assessment_id": {"_eq": "other-assessment"},
            "status": {"_eq": "verified"},
        }
        assert methods.list_by_assessment("assessment-1", options) == []
        _, assessment_scope = client.list_items.call_args.args
        assert assessment_scope.filter == {
            "location_id": {"_eq": "other-location"},
            "assessment_id": {"_eq": "assessment-1"},
            "status": {"_eq": "verified"},
        }
        for scoped in (location_scope, assessment_scope):
            assert scoped.fields == options.fields
            assert scoped.sort == options.sort
            assert scoped.limit == 12
            assert scoped.offset == 24
        assert not any(hasattr(methods, name) for name in ("create", "update", "delete"))

    assert not any(
        hasattr(client.crisp_risk_assessments, name) for name in ("create", "update", "delete")
    )


def test_crisp_read_models_expose_saved_scores_and_dimension_payloads():
    from kokonut import (
        CrispCarbonYieldRisk,
        CrispClimateRisk,
        CrispFinancialRisk,
        CrispImplementationRisk,
        CrispPolicyRisk,
        CrispRiskAssessment,
    )

    assessment = CrispRiskAssessment(
        id="assessment-1", location_id="location-1", period_start="2026-01-01",
        period_end="2026-01-31", methodology_version="v1.0", composite_score=72.5,
        rating="A", confidence_level="moderate", status="verified",
        metadata={"weights": {"climate": 0.2}},
    )
    carbon = CrispCarbonYieldRisk(
        id="carbon-1", assessment_id=assessment.id, location_id=assessment.location_id,
        risk_score=20.0, carbon_pool_breakdown={"above_ground": 12.5},
    )
    climate = CrispClimateRisk(
        id="climate-1", assessment_id=assessment.id, location_id=assessment.location_id,
        ssp_scenario="SSP2", historical_events=[{"type": "drought"}], risk_score=35.0,
    )
    policy = CrispPolicyRisk(
        id="policy-1", assessment_id=assessment.id, location_id=assessment.location_id,
        risk_score=30.0, policy_indicators={"article_6": "reviewed"},
    )
    financial = CrispFinancialRisk(
        id="financial-1", assessment_id=assessment.id, location_id=assessment.location_id,
        financial_snapshot={"currency": "USD"}, risk_score=40.0,
    )
    implementation = CrispImplementationRisk(
        id="implementation-1", assessment_id=assessment.id,
        location_id=assessment.location_id, implementation_evidence={"team": "recorded"},
    )

    assert assessment.rating == "A"
    assert carbon.carbon_pool_breakdown == {"above_ground": 12.5}
    assert climate.ssp_scenario == "SSP2"
    assert policy.policy_indicators == {"article_6": "reviewed"}
    assert financial.financial_snapshot == {"currency": "USD"}
    assert implementation.implementation_evidence == {"team": "recorded"}


def test_systems_thinking_models_preserve_stored_fields_and_literals():
    from typing import get_args

    from kokonut import (
        CausalLink,
        CausalLinkPolarity,
        CausalLoop,
        CausalLoopType,
        LeverageAssessment,
        StockFlowModel,
        StockFlowRun,
        StockFlowRunStatus,
        StructuralAssumption,
        StructuralAssumptionStatus,
        SystemArchetype,
        SystemArchetypeStatus,
        SystemsDomain,
        SystemVariable,
        SystemVariableType,
        TimeDelay,
    )

    loop = CausalLoop(
        id="loop-1",
        loop_name="soil-carbon-cycle",
        loop_type="reinforcing",
        description="Organic inputs build soil carbon.",
        domain="ecological",
        is_enabled=True,
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
    )
    link = CausalLink(
        id="link-1",
        loop_id=loop.id,
        source_variable="organic_inputs",
        target_variable="soil_carbon",
        polarity="+",
        strength=0.8,
        created_at="2026-10-18T00:00:00Z",
    )
    variable = SystemVariable(
        id="variable-1",
        variable_name="soil_carbon",
        variable_type="stock",
        location_id="location-1",
        current_value=52.4,
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
    )
    model = StockFlowModel(
        id="model-1",
        model_name="soil-carbon",
        description="Synthetic model",
        equations={"soil_carbon": "INTEG(inputs - losses, 50)"},
        initial_conditions={"soil_carbon": 50},
        parameters={"decomposition_rate": 0.02},
        time_unit="day",
        is_enabled=True,
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
    )
    run = StockFlowRun(
        id="run-1",
        model_id=model.id,
        location_id="location-1",
        scenario_name="baseline",
        parameters={},
        start_date="2026-01-01",
        end_date="2026-12-31",
        time_step_days=1,
        results={"final_soil_carbon": 55.2},
        trajectory=[{"day": 0, "soil_carbon": 50.0}],
        status="completed",
        run_at="2026-10-18T00:00:00Z",
        run_by="synthetic",
    )
    archetype = SystemArchetype(
        id="archetype-1",
        archetype_name="limits_to_growth",
        location_id="location-1",
        confidence=0.7,
        evidence={"source": "synthetic"},
        active_variables=["soil_carbon"],
        status="active",
        detected_at="2026-10-18T00:00:00Z",
        created_at="2026-10-18T00:00:00Z",
    )
    assessment = LeverageAssessment(
        id="assessment-1",
        location_id="location-1",
        leverage_point=6,
        point_name="information flows",
        impact_score=0.6,
        data_sources=["metric_value"],
        assessed_at="2026-10-18T00:00:00Z",
        assessed_by="synthetic",
        created_at="2026-10-18T00:00:00Z",
    )
    delay = TimeDelay(
        id="delay-1",
        action_type="cover_crop",
        effect_type="soil_carbon",
        expected_delay_hours=720,
        domain="ecological",
        is_enabled=True,
        created_at="2026-10-18T00:00:00Z",
    )
    assumption = StructuralAssumption(
        id="assumption-1",
        assumption_text="Synthetic assumption",
        location_id="location-1",
        domain="farm",
        status="challenged",
        created_at="2026-10-18T00:00:00Z",
        updated_at="2026-10-18T00:00:00Z",
    )

    assert link.loop_id == loop.id
    assert variable.current_value == 52.4
    assert run.trajectory == [{"day": 0, "soil_carbon": 50.0}]
    assert archetype.evidence == {"source": "synthetic"}
    assert assessment.data_sources == ["metric_value"]
    assert delay.expected_delay_hours == 720
    assert assumption.status == "challenged"
    assert get_args(CausalLoopType) == ("reinforcing", "balancing", "archetype")
    assert get_args(SystemsDomain) == (
        "farm", "ecological", "financial", "social", "governance"
    )
    assert get_args(CausalLinkPolarity) == ("+", "-")
    assert get_args(SystemVariableType) == ("stock", "flow", "auxiliary", "constant")
    assert get_args(StockFlowRunStatus) == ("pending", "running", "completed", "failed")
    assert get_args(SystemArchetypeStatus) == ("active", "resolved", "dismissed")
    assert get_args(StructuralAssumptionStatus) == (
        "active", "challenged", "validated", "deprecated"
    )
    assert get_args(CausalLoopType) == ("reinforcing", "balancing", "archetype")
    assert get_args(SystemsDomain) == (
        "farm", "ecological", "financial", "social", "governance"
    )
    assert get_args(CausalLinkPolarity) == ("+", "-")
    assert get_args(SystemVariableType) == ("stock", "flow", "auxiliary", "constant")
    assert get_args(StockFlowRunStatus) == ("pending", "running", "completed", "failed")
    assert get_args(SystemArchetypeStatus) == ("active", "resolved", "dismissed")
    assert get_args(StructuralAssumptionStatus) == (
        "active", "challenged", "validated", "deprecated"
    )


def test_kokonut_methods_import():
    from kokonut.methods import FarmMethods, HarvestEventMethods, LocationMethods

    assert LocationMethods is not None
    assert FarmMethods is not None
    assert HarvestEventMethods is not None


def test_export_methods_expose_only_read_access_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[{"id": "export-1"}])
    client.get_item = Mock(return_value={"id": "export-1", "status": "completed"})

    assert client.exports.list() == [{"id": "export-1"}]
    assert client.exports.get("export-1", fields=["id", "status"]) == {
        "id": "export-1", "status": "completed"
    }
    client.list_items.assert_called_once_with("export_log", None)
    client.get_item.assert_called_once_with("export_log", "export-1", ["id", "status"])

    assert not hasattr(client.exports, "create")
    assert not hasattr(client.exports, "create_many")
    assert not hasattr(client.exports, "update")
    assert not hasattr(client.exports, "delete")


def test_login_returns_directus_auth_payload_and_stores_access_token_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "data": {
            "access_token": "synthetic-access-token",
            "refresh_token": "synthetic-refresh-token",
            "expires": 900,
            "expires_at": 1_800_000_000_000,
        }
    }
    client.session.post = Mock(return_value=response)

    result = client.login("operator@example.invalid", "synthetic-password")

    assert result == response.json.return_value["data"]
    assert client.session.headers["Authorization"] == "Bearer synthetic-access-token"


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (400, "ValidationError"),
        (401, "AuthenticationError"),
        (403, "ForbiddenError"),
        (404, "NotFoundError"),
        (422, "KokonutError"),
    ],
)
def test_directus_http_errors_map_status_and_preserve_server_message(status, error_type):
    from kokonut import KokonutClient
    from kokonut.client import (
        AuthenticationError,
        ForbiddenError,
        KokonutError,
        NotFoundError,
        ValidationError,
    )

    client = KokonutClient("http://localhost:8055")
    error_classes = {
        "AuthenticationError": AuthenticationError,
        "ForbiddenError": ForbiddenError,
        "KokonutError": KokonutError,
        "NotFoundError": NotFoundError,
        "ValidationError": ValidationError,
    }
    response = Mock()
    response.ok = False
    response.status_code = status
    response.text = "fallback response text"
    response.json.return_value = {"errors": [{"message": "synthetic Directus error"}]}
    client.session.get = Mock(return_value=response)

    with pytest.raises(error_classes[error_type], match="synthetic Directus error") as raised:
        client.get_item("location", "missing-location")

    assert raised.value.status_code == status
    assert raised.value.response is response


@pytest.mark.parametrize(
    "body",
    [
        ["unexpected JSON array"],
        {"errors": {"message": "unexpected object"}},
        {"errors": [{"message": None}]},
        {"errors": []},
    ],
)
def test_directus_http_errors_fall_back_for_malformed_error_envelopes(body):
    from kokonut import KokonutClient
    from kokonut.client import NotFoundError

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = False
    response.status_code = 404
    response.text = "fallback response text"
    response.json.return_value = body
    client.session.get = Mock(return_value=response)

    with pytest.raises(NotFoundError, match="fallback response text"):
        client.get_item("location", "missing-location")


def test_directus_http_errors_fall_back_for_invalid_json():
    from kokonut import KokonutClient
    from kokonut.client import NotFoundError

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = False
    response.status_code = 404
    response.text = "not json"
    response.json.side_effect = ValueError("invalid json")
    client.session.get = Mock(return_value=response)

    with pytest.raises(NotFoundError, match="not json"):
        client.get_item("location", "missing-location")


def test_aggregate_query_serializes_options_and_returns_data_without_network_calls():
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": [{"location_id": "location-1", "count": {"*": 2}}]}
    client.session.get = Mock(return_value=response)

    result = client.aggregate(
        "harvest_event",
        aggregate={"count": "*"},
        groupBy=["location_id"],
    )

    assert result == response.json.return_value["data"]
    client.session.get.assert_called_once_with(
        "http://localhost:8055/items/harvest_event",
        params={"aggregate": '{"count": "*"}', "groupBy": "location_id"},
    )


def test_list_items_preserves_extra_directus_query_parameters_without_network_calls():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": []}
    client.session.get = Mock(return_value=response)

    client.list_items(
        "harvest_event",
        ListOptions(limit=25, offset=10, fields=["id", "location_id"], sort=["-created_at"]),
        search="coconut",
        aggregate={"count": "*"},
        groupBy=["location_id"],
    )

    client.session.get.assert_called_once_with(
        "http://localhost:8055/items/harvest_event",
        params={
            "limit": 25,
            "offset": 10,
            "fields": "id,location_id",
            "sort": "-created_at",
            "search": "coconut",
            "aggregate": '{"count": "*"}',
            "groupBy": "location_id",
        },
    )


def test_list_items_normalizes_pagination_precedence_like_javascript_sdk():
    from unittest.mock import call

    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": []}
    client.session.get = Mock(return_value=response)

    client.list_items("farm", offset=10)
    client.list_items("farm", offset=10, page=3)
    client.list_items("farm", limit=25, offset=10, page=3)
    with pytest.raises(ValueError, match="non-zero limit"):
        client.list_items("farm", limit=0, offset=10)

    assert client.session.get.call_args_list == [
        call("http://localhost:8055/items/farm", params={}),
        call("http://localhost:8055/items/farm", params={"page": 3}),
        call("http://localhost:8055/items/farm", params={"limit": 25, "offset": 10}),
    ]


def test_generic_crud_helpers_use_directus_item_routes_and_unwrap_data_without_network_calls():
    from unittest.mock import call

    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")

    def response(data):
        result = Mock()
        result.ok = True
        result.json.return_value = {"data": data}
        return result

    detail = {"id": "location-1", "name": "Synthetic Location"}
    created = {"id": "location-2", "name": "Synthetic Location"}
    created_batch = [{"id": "farm-1", "name": "Synthetic Farm"}]
    updated = {"id": "location-1", "country": "DO"}
    client.session.get = Mock(return_value=response(detail))
    client.session.post = Mock(side_effect=[response(created), response(created_batch)])
    client.session.patch = Mock(return_value=response(updated))
    client.session.delete = Mock(return_value=response(None))

    assert client.get_item("location", "location-1", ["id", "name"]) == detail
    assert client.create_item(
        "location", {"name": "Synthetic Location", "slug": "synthetic-location"}
    ) == created
    assert client.create_items("farm", [{"name": "Synthetic Farm"}]) == created_batch
    assert client.update_item("location", "location-1", {"country": "DO"}) == updated
    assert client.delete_item("location", "location-1") is None

    client.session.get.assert_called_once_with(
        "http://localhost:8055/items/location/location-1",
        params={"fields": "id,name"},
    )
    assert client.session.post.call_args_list == [
        call(
            "http://localhost:8055/items/location",
            json={"name": "Synthetic Location", "slug": "synthetic-location"},
        ),
        call("http://localhost:8055/items/farm", json=[{"name": "Synthetic Farm"}]),
    ]
    client.session.patch.assert_called_once_with(
        "http://localhost:8055/items/location/location-1", json={"country": "DO"}
    )
    client.session.delete.assert_called_once_with(
        "http://localhost:8055/items/location/location-1"
    )


def test_generic_crud_helpers_encode_untrusted_path_segments_before_request():
    from unittest.mock import call

    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": []}
    client.session.get = Mock(return_value=response)
    client.session.post = Mock(return_value=response)
    client.session.patch = Mock(return_value=response)
    client.session.delete = Mock(return_value=response)

    client.list_items("farm/../../auth")
    client.get_item("location", "farm/../../auth?token=x#fragment%")
    client.create_item("farm/../../auth", {})
    client.create_items("farm/../../auth", [])
    client.update_item("location", "farm/../../auth", {})
    client.delete_item("location", "farm/../../auth")
    client.aggregate("farm/../../auth", aggregate={"count": "*"})

    collection_url = "http://localhost:8055/items/farm%2F..%2F..%2Fauth"
    item_url = "http://localhost:8055/items/location/farm%2F..%2F..%2Fauth"
    query_item_url = (
        "http://localhost:8055/items/location/"
        "farm%2F..%2F..%2Fauth%3Ftoken%3Dx%23fragment%25"
    )
    assert client.session.get.call_args_list == [
        call(collection_url, params={}),
        call(query_item_url, params={}),
        call(collection_url, params={"aggregate": '{"count": "*"}'}),
    ]
    assert client.session.post.call_args_list == [
        call(collection_url, json={}),
        call(collection_url, json=[]),
    ]
    client.session.patch.assert_called_once_with(item_url, json={})
    client.session.delete.assert_called_once_with(item_url)


@pytest.mark.parametrize("segment", ["", ".", ".."])
def test_generic_crud_helpers_reject_empty_and_dot_path_segments_before_request(segment):
    from kokonut import KokonutClient

    client = KokonutClient("http://localhost:8055")
    client.session.get = Mock()

    with pytest.raises(ValueError, match="path segment"):
        client.get_item("location", segment)
    with pytest.raises(ValueError, match="path segment"):
        client.list_items(segment)

    client.session.get.assert_not_called()


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


def test_specialized_methods_use_explicit_directus_equality_filters():
    from kokonut import KokonutClient
    from kokonut.types import ListOptions

    client = KokonutClient("http://localhost:8055")
    client.list_items = Mock(return_value=[])
    cases = [
        (client.farms.list_by_location, "location-1", "location_id", "farm"),
        (client.plots.list_by_farm, "farm-1", "farm_id", "plot"),
        (client.crop_cycles.list_by_plot, "plot-1", "plot_id", "crop_cycle"),
        (client.harvest_events.list_by_crop_cycle, "cycle-1", "crop_cycle_id", "harvest_event"),
        (client.sales_events.list_by_crop_cycle, "cycle-1", "crop_cycle_id", "sales_event"),
        (client.expense_events.list_by_crop_cycle, "cycle-1", "crop_cycle_id", "expense_event"),
        (client.loss_events.list_by_location, "location-1", "location_id", "loss_event"),
        (client.labor_events.list_by_location, "location-1", "location_id", "labor_event"),
        (client.field_notes.list_by_location, "location-1", "location_id", "field_note"),
        (client.sensor_readings.list_by_device, "device-1", "sensor_id", "sensor_reading"),
        (client.sensor_readings.list_by_plot, "plot-1", "plot_id", "sensor_reading"),
        (client.reports.list_by_type, "impact", "report_type", "report_snapshot"),
        (client.noi.list_by_crop_cycle, "cycle-1", "crop_cycle_id", "noi_snapshot"),
    ]

    for method, value, field, collection in cases:
        options = ListOptions(
            filter={field: {"_eq": "other"}, "status": {"_eq": "verified"}}
        )
        method(value, options)
        actual_collection, actual_options = client.list_items.call_args.args
        assert actual_collection == collection
        assert actual_options.filter == {
            field: {"_eq": value},
            "status": {"_eq": "verified"},
        }

    client.attestations.list_by_entity("location", "location-1")
    assert client.list_items.call_args.args == (
        "attestation_record",
        ListOptions(
            filter={
                "subject_type": {"_eq": "location"},
                "subject_id": {"_eq": "location-1"},
            }
        ),
    )

    operator_cases = [
        (
            lambda: client.crop_cycles.list_active(
                ListOptions(filter={"status": {"_eq": "archived"}})
            ),
            "crop_cycle",
            {"status": {"_in": ["planted", "growing"]}},
        ),
        (
            lambda: client.sales_events.list_unpaid(
                ListOptions(filter={"payment_status": {"_eq": "paid"}})
            ),
            "sales_event",
            {"payment_status": {"_in": ["pending", "partial"]}},
        ),
        (
            lambda: client.expense_events.list_pending_approval(
                ListOptions(filter={"status": {"_eq": "draft"}})
            ),
            "expense_event",
            {"status": {"_eq": "submitted"}},
        ),
        (
            lambda: client.sensor_readings.list_anomalies(
                ListOptions(filter={"quality": {"_eq": "good"}})
            ),
            "sensor_reading",
            {"quality": {"_eq": "suspect"}},
        ),
        (
            lambda: client.attestations.list_pending(
                ListOptions(filter={"status": {"_eq": "published"}})
            ),
            "attestation_record",
            {"status": {"_in": ["draft", "submitted"]}},
        ),
    ]
    for invoke, collection, expected_filter in operator_cases:
        invoke()
        actual_collection, actual_options = client.list_items.call_args.args
        assert actual_collection == collection
        assert actual_options.filter == expected_filter

    client.wallet_profiles.find_by_address("0xwallet")
    assert client.list_items.call_args.args == (
        "wallet_profile",
        ListOptions(filter={"address": {"_eq": "0xwallet"}}, limit=1),
    )


def test_organic_compliance_read_models_preserve_sql_literals_and_evidence_shapes():
    from kokonut import (
        BufferOperationalStatus,
        BufferZone,
        OrganicCertificationRecord,
        OrganicReadinessAssessment,
    )

    certification = OrganicCertificationRecord(
        id="cert-1",
        location_id="location-1",
        standard="USDA NOP",
        certification_type="renewal",
        status="certified",
        created_at="2026-10-18T12:00:00Z",
        updated_at="2026-10-18T12:00:00Z",
        scope="partial",
        evidence_urls=["https://example.invalid/certificate"],
    )
    readiness = OrganicReadinessAssessment(
        id="readiness-1",
        location_id="location-1",
        assessment_date="2026-10-18",
        standard="IFOAM",
        overall_score=82.5,
        created_at="2026-10-18T12:00:00Z",
        updated_at="2026-10-18T12:00:00Z",
        recommendations=[{"dimension": "buffer_zone", "action": "review"}],
    )
    buffer = BufferZone(
        id="buffer-1",
        location_id="location-1",
        buffer_name="North hedgerow",
        buffer_type="hedgerow",
        width_m=5.0,
        condition_status="adequate",
        created_at="2026-10-18T12:00:00Z",
        updated_at="2026-10-18T12:00:00Z",
        status="maintenance_needed",
    )

    assert certification.status == "certified"
    assert readiness.recommendations == [{"dimension": "buffer_zone", "action": "review"}]
    assert buffer.status == "maintenance_needed"
    assert BufferOperationalStatus.__args__ == ("active", "inactive", "maintenance_needed")


if __name__ == "__main__":
    test_kokonut_client_import()
    test_kokonut_types_import()
    test_kokonut_methods_import()
    test_scoped_list_filter_wins_and_preserves_list_options_without_network_calls()
    print("All SDK smoke tests passed ✓")
