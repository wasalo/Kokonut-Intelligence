"""Authorization and transaction contract for Comprehensive Status reads."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import comprehensive_status_reads as reads
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
COMPREHENSIVE_STATUS_SECTIONS = (
    "farm_summary",
    "crop_noi",
    "environmental",
    "climate_impact",
    "financial_sustainability",
    "capital_efficiency",
    "holistic_wellbeing",
    "community_governance",
    "gnh_alignment",
    "training_impact",
    "regenerative_outcomes",
    "foundational_wellbeing",
    "stakeholder_outcomes",
    "capital_accounting",
)


def _comprehensive_status_payload(location_id=LOCATION_ID):
    sections = {section: {} for section in COMPREHENSIVE_STATUS_SECTIONS}
    sections["farm_summary"] = _farm_summary_section(location_id)
    sections["crop_noi"] = {
        "report_type": "crop_noi",
        "location_id": location_id,
        "crop_cycles": [
            {
                "cycle_id": str(uuid4()),
                "cycle_name": "Wet season",
                "crop_name": "Plantain",
                "plot_name": "North plot",
                "status": "completed",
                "planting_date": "2026-01-01",
                "actual_harvest_date": "2026-06-01",
                "expected_yield": 100.0,
                "actual_yield": 90.0,
                "expected_revenue": 1400.0,
                "actual_revenue": 1150.0,
                "allocated_cost": 400.0,
                "gross_revenue": 1200.0,
                "returns_and_discounts": 50.0,
                "net_revenue": 1150.0,
                "direct_crop_costs": 300.0,
                "allocated_shared_costs": 100.0,
                "total_costs": 400.0,
                "crop_noi": 750.0,
                "operating_margin_pct": 65.2174,
                "loss_rate_pct": 5.0,
            }
        ],
        "summary": {
            "total_revenue": 1150.0,
            "total_gross_revenue": 1200.0,
            "total_returns_and_discounts": 50.0,
            "total_direct_crop_costs": 300.0,
            "total_allocated_shared_costs": 100.0,
            "total_cost": 400.0,
            "total_noi": 750.0,
            "overall_margin_pct": 750 / 1150 * 100,
        },
        "generated_at": "2026-10-28T00:00:00+00:00",
    }
    sections["environmental"] = _environmental_section(location_id)
    sections["climate_impact"] = _climate_impact_section(location_id)
    sections["financial_sustainability"] = _financial_sustainability_section(location_id)
    sections["regenerative_outcomes"] = _regenerative_outcomes_section(location_id)
    sections["gnh_alignment"] = _gnh_alignment_section(location_id)
    sections["capital_efficiency"] = _capital_efficiency_section(location_id)
    return {
        "report_type": "comprehensive_status",
        "scope": "selected_locations",
        "selected_location_ids": [location_id],
        "period_start": None,
        "period_end": None,
        "ecosystem_overview": {
            "total_locations": 1,
            "locations_with_financial_data": 1,
            "total_revenue_usd": 1200.0,
            "total_expenses_usd": 750.0,
            "net_income_usd": 450.0,
            "total_harvest_quantity": 12.0,
            "total_harvest_quantity_unit": "kg",
            "total_harvest_quantity_by_unit": {"kg": 12.0},
        },
        "locations": [
            {
                "location_id": location_id,
                "name": "Kokonut Adelphi",
                "slug": "kokonut-adelphi",
                "country": "DO",
                "region": "North",
                "sections": sections,
            }
        ],
        "limitations": ["Composite of canonical per-location generators."],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _farm_summary_section(location_id=LOCATION_ID):
    farm_id = str(uuid4())
    plot_id = str(uuid4())
    crop_cycle_id = str(uuid4())
    return {
        "report_type": "farm_summary",
        "location": {
            "id": location_id,
            "name": "Kokonut Adelphi",
            "slug": "kokonut-adelphi",
            "description": None,
            "country": "DO",
            "region": "North",
            "sub_region": None,
            "timezone": "America/Santo_Domingo",
            "latitude": 18.5,
            "longitude": -69.9,
            "baseline_revenue": None,
            "baseline_asset_value": None,
            "baseline_cash_flow": None,
            "baseline_cost": None,
            "baseline_assumptions": {},
            "baseline_source": None,
            "baseline_date": None,
            "status": "active",
            "metadata": {"profile": "synthetic"},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "created_by": None,
            "updated_by": None,
            "project_url": None,
            "project_start_date": None,
            "project_end_date": None,
            "bioregion": [],
            "biome_type": [],
            "watershed": None,
            "sub_watershed": None,
            "schema_version": "common-data-schema-v1",
            "organization_id": None,
            "baseline_recorded_at": None,
        },
        "farms": [
            {
                "id": farm_id,
                "location_id": location_id,
                "name": "Adelphi Farm",
                "slug": "adelphi-farm",
                "description": None,
                "farm_type": "agroforestry",
                "total_area": 10.0,
                "area_unit": "hectares",
                "boundary": {"type": "Polygon", "coordinates": []},
                "center": None,
                "status": "active",
                "metadata": {"profile": "synthetic"},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
                "created_by": None,
                "updated_by": None,
                "property_id": None,
                "schema_version": "common-data-schema-v1",
                "logo_url": None,
                "logo_file_id": None,
                "traditional_name": None,
                "languages": [],
                "global_standard_certifications": [],
                "economic_sectors": [],
                "credits_registries": [],
                "data_privacy_status": "internal_review",
                "data_privacy_standard": None,
                "data_privacy_criteria": {},
            }
        ],
        "plots": [
            {
                "id": plot_id,
                "farm_id": farm_id,
                "name": "North plot",
                "slug": "north-plot",
                "description": None,
                "area": 2.5,
                "area_unit": "hectares",
                "boundary": None,
                "center": {"type": "Point", "coordinates": [-69.9, 18.5]},
                "soil_type": "loam",
                "water_source": None,
                "elevation_m": None,
                "slope_pct": None,
                "aspect": None,
                "status": "active",
                "metadata": {},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
                "created_by": None,
                "updated_by": None,
                "schema_version": "common-data-schema-v1",
                "bed_count": None,
                "bed_area_sqm": None,
                "farm_name": "Adelphi Farm",
            }
        ],
        "crop_cycles": [
            {
                "id": crop_cycle_id,
                "plot_id": plot_id,
                "crop_id": str(uuid4()),
                "location_id": location_id,
                "cycle_name": "Wet season",
                "season": "wet",
                "planting_date": "2026-01-01",
                "expected_harvest_date": None,
                "actual_harvest_date": None,
                "expected_yield": 100.0,
                "expected_yield_unit": "kg",
                "actual_yield": None,
                "actual_yield_unit": None,
                "expected_price_per_unit": None,
                "expected_revenue": 1200.0,
                "actual_revenue": None,
                "planting_density": None,
                "planting_density_unit": None,
                "area_planted": 1.0,
                "area_unit": "hectares",
                "status": "active",
                "failure_reason": None,
                "metadata": {},
                "schema_version": "common-data-schema-v1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
                "created_by": None,
                "updated_by": None,
                "crop_name": "Plantain",
                "plot_name": "North plot",
            }
        ],
        "harvest_summary": {
            "total_harvests": 0,
            "total_quantity": 0.0,
            "avg_harvest_size": 0.0,
            "cycles_with_harvest": 0,
            "quantity_unit": None,
            "total_quantity_by_unit": {},
        },
        "financial_summary": {
            "total_revenue": 0.0,
            "total_expenses": 0.0,
            "net_income": 0.0,
        },
        "expense_breakdown": [],
        "attestation_coverage": {"total_records": 0, "attested": 0, "draft": 0},
        "farm_activity_summary": {
            "published_activity_count": 0,
            "reported_labor_hours": 0.0,
            "reported_labor_hours_unit": "hours",
            "by_activity_type": [],
        },
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _environmental_section(location_id=LOCATION_ID):
    return {
        "report_type": "environmental",
        "location_id": location_id,
        "soil_carbon": [
            {
                "measurement_date": "2026-06-01",
                "carbon_tonnes_per_ha": Decimal("18.75"),
                "measurement_method": "lab_analysis",
                "depth_cm": 30.0,
            }
        ],
        "species_observations": [
            {
                "observation_date": "2026-06-02",
                "count": 3,
                "habitat_type": "forest_edge",
                "notes": "Synthetic observation note",
            }
        ],
        "remote_sensing": [
            {
                "observation_date": "2026-06-03",
                "ndvi": 0.72,
                "ndre": 0.44,
                "cloud_cover_pct": 5.0,
            }
        ],
        "loss_events": [
            {
                "loss_date": "2026-06-04",
                "loss_type": "drought",
                "quantity": 2.0,
                "unit": "kg",
                "cause": "Synthetic drought loss",
            }
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _financial_sustainability_section(location_id=LOCATION_ID):
    return {
        "report_type": "financial_sustainability",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "plans": [
            {
                "id": str(uuid4()),
                "location_id": location_id,
                "farm_id": None,
                "plan_name": "Public operating plan",
                "farm_model": "blended",
                "plan_period_start": "2026-01-01",
                "plan_period_end": None,
                "revenue_streams": ["produce", "training"],
                "grant_dependency_pct": Decimal("25.0000"),
                "reinvestment_pct": Decimal("40.0000"),
                "public_goods_allocation_pct": Decimal("10.0000"),
                "break_even_month": 9,
                "runway_months": Decimal("12.50"),
                "projected_annual_revenue_usd": Decimal("125000.00"),
                "projected_annual_operating_cost_usd": Decimal("90000.00"),
                "projected_annual_noi_usd": Decimal("35000.00"),
                "sustainability_status": "transitioning",
                "public_summary": "Synthetic public plan summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Substantiated",
                "metadata": {"public_tag": "synthetic", "labels": ["reviewed"]},
            }
        ],
        "limitations": [
            "This report summarizes published financial sustainability plans only.",
            "Projected revenue, NOI, runway, and grant dependency are planning signals, not guarantees.",
            "Private financial terms and draft capital discussions are excluded.",
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _climate_impact_section(location_id=LOCATION_ID):
    return {
        "report_type": "climate_impact",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "reporting_year": 2025,
        "carbon_balance": {
            "location_id": location_id,
            "reporting_year": 2025,
            "above_ground_carbon_tonnes": 10.25,
            "below_ground_carbon_tonnes": 2.5,
            "total_sequestration_tonnes_co2e": 12.75,
            "total_emissions_tonnes_co2e": 4.0,
            "net_climate_impact_tonnes_co2e": 8.75,
            "carbon_position": "net_sequester",
        },
        "ghg_emissions": {
            "location_id": location_id,
            "period_start": None,
            "period_end": None,
            "categories": [
                {
                    "category": "transport",
                    "record_count": 2,
                    "total_co2e_kg": 4000.0,
                    "total_co2e_tonnes": 4.0,
                }
            ],
            "summary": {
                "total_co2e_kg": 4000.0,
                "total_co2e_tonnes": 4.0,
                "record_count": 2,
            },
        },
        "tree_carbon": {
            "location_id": location_id,
            "species": [
                {
                    "species_name": "Mango",
                    "total_trees": 12,
                    "total_biomass_kg": 1000.0,
                    "total_carbon_tonnes": 0.47,
                    "total_co2e_tonnes": 1.7249,
                    "survey_count": 2,
                }
            ],
            "summary": {
                "total_trees": 12,
                "total_carbon_tonnes": 0.47,
                "total_co2e_tonnes": 1.7249,
                "species_count": 1,
            },
        },
        "regenerative_score": {
            "location_id": location_id,
            "principles": [
                {
                    "principle_key": "diversity",
                    "principle_name": "Increase diversity",
                    "score": 4,
                    "max_score": 5,
                    "assessment_date": "2025-11-12",
                    "evidence_path": "private://evidence/diversity.pdf",
                    "notes": "Reviewer notes are preserved by the current report.",
                }
            ],
            "summary": {
                "total_score": 4,
                "max_score": 25,
                "score_pct": 16.0,
                "principles_assessed": 1,
                "last_assessment_date": "2025-11-12",
            },
        },
        "framework_phases": [
            {
                "framework_key": "regeneration",
                "phase": "monitoring",
                "phase_status": "active",
                "phase_start_date": "2025-02-01",
                "review_cadence": "quarterly",
            }
        ],
        "operations_protocols": [
            {
                "title": "Soil Protocol",
                "section": "soil_management",
                "version": "1.0",
            }
        ],
        "stored_summary": {
            "id": str(uuid4()),
            "location_id": location_id,
            "reporting_year": 2025,
            "above_ground_carbon_tonnes": Decimal("10.2500"),
            "below_ground_carbon_tonnes": Decimal("2.5000"),
            "total_sequestration_tonnes_co2e": Decimal("12.7500"),
            "transport_emissions_tonnes_co2e": Decimal("4.0000"),
            "machinery_emissions_tonnes_co2e": None,
            "input_emissions_tonnes_co2e": None,
            "total_emissions_tonnes_co2e": Decimal("4.0000"),
            "net_climate_impact_tonnes_co2e": Decimal("8.7500"),
            "species_count": 8,
            "shannon_index": Decimal("1.2500"),
            "regenerative_score_total": 20,
            "methodology_version": "v1",
            "data_quality_score": Decimal("85.00"),
            "status": "draft",
            "reviewed_by": str(uuid4()),
            "reviewed_at": "2025-12-01T12:00:00+00:00",
            "notes": "Synthetic stored-summary note.",
            "source_system": "manual",
            "source_id": "source-2025-adelphi",
            "created_at": "2025-12-01T12:00:00+00:00",
            "updated_at": "2025-12-02T12:00:00+00:00",
        },
        "limitations": [
            "Active operations protocols are shared platform reference metadata, not location-specific evidence."
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _regenerative_outcomes_section(location_id=LOCATION_ID):
    return {
        "report_type": "regenerative_outcomes",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "outcomes": [
            {
                "id": str(uuid4()),
                "location_id": location_id,
                "farm_id": str(uuid4()),
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "summary_name": "Synthetic annual outcome",
                "hectares_restored": Decimal("1.2500"),
                "baseline_species_count": 8,
                "latest_species_count": 12,
                "species_diversity_delta": Decimal("4.0000"),
                "baseline_soil_carbon_t_ha": Decimal("21.5000"),
                "latest_soil_carbon_t_ha": Decimal("23.0000"),
                "soil_carbon_delta_t_ha": Decimal("1.5000"),
                "trees_planted_count": 100,
                "trees_surviving_count": 92,
                "tree_survival_rate_pct": Decimal("92.0000"),
                "regenerative_score": Decimal("84.50"),
                "jobs_or_roles_supported_count": 4,
                "training_hours": Decimal("32.5000"),
                "beneficiary_count": 18,
                "evidence_confidence": "high",
                "public_summary": "Published synthetic outcome summary.",
                "evidence_maturity": 4,
                "evidence_maturity_label": "Evidence-linked record",
                "metadata": {"public_tag": "synthetic", "labels": ["reviewed"]},
            }
        ],
        "total_hectares_restored": 1.25,
        "limitations": [
            "Regenerative outcome summaries consolidate source evidence for reviewers; source tables remain canonical.",
            "Moderate or low confidence outcomes should not be treated as external certification.",
            "Carbon-credit or biodiversity-credit claims require separate maturity and verification gates.",
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _gnh_alignment_section(location_id=LOCATION_ID):
    return {
        "report_type": "gnh_alignment",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "assessments": [
            {
                "id": str(uuid4()),
                "location_id": location_id,
                "farm_id": str(uuid4()),
                "assessment_date": "2025-11-12",
                "gnh_domain": "community_vitality",
                "principle_refs": ["community_participation", "shared_benefit"],
                "alignment_score": Decimal("8.50"),
                "strengths": ["Local stewardship council is active."],
                "gaps": ["Youth representation needs review."],
                "safeguards": ["Participation remains voluntary."],
                "public_summary": "Synthetic published GNH assessment.",
                "evidence_maturity": 4,
                "evidence_maturity_label": "Evidence-linked record",
                "metadata": {"public_tag": "synthetic", "labels": ["reviewed"]},
            }
        ],
        "average_alignment_score": 8.5,
        "limitations": [
            "GNH alignment is a reviewer-assessed evidence signal, not Bhutan readiness certification.",
            "Local cultural review is required before adapting claims to a Bhutanese context.",
            "Domain scores summarize published evidence and should be interpreted with listed gaps and safeguards.",
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


def _capital_efficiency_section(location_id=LOCATION_ID):
    return {
        "report_type": "capital_efficiency",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "scenarios": [
            {
                "id": str(uuid4()),
                "location_id": location_id,
                "farm_id": None,
                "scenario_name": "Public goods loop",
                "scenario_type": "public_goods_loop",
                "period_start": "2025-01-01",
                "period_end": None,
                "capital_deployed_usd": Decimal("10000.00"),
                "gross_output_value_usd": Decimal("15000.00"),
                "net_output_value_usd": Decimal("-250.00"),
                "public_goods_value_usd": Decimal("4000.00"),
                "capital_leverage_ratio": Decimal("1.5000"),
                "public_summary": "Published synthetic capital scenario.",
                "evidence_maturity": 4,
                "evidence_maturity_label": "Evidence-linked record",
                "metadata": {"public_tag": "synthetic", "labels": ["reviewed"]},
            }
        ],
        "regenerative_efficiency": [
            {
                "id": str(uuid4()),
                "location_id": location_id,
                "farm_id": str(uuid4()),
                "practice_event_id": None,
                "observation_date": "2025-09-15",
                "practice_type": "mulching",
                "baseline_cost_usd": Decimal("100.00"),
                "observed_cost_usd": Decimal("125.00"),
                "cost_savings_pct": Decimal("-25.0000"),
                "incremental_output_value_usd": Decimal("-10.00"),
                "implementation_cost_usd": Decimal("25.00"),
                "payback_months": Decimal("6.00"),
                "public_summary": "Published synthetic regenerative efficiency observation.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
                "metadata": {"public_tag": "synthetic"},
            }
        ],
        "limitations": [
            "Capital efficiency and payback values are scenario evidence, not guaranteed returns.",
            "Private capital terms and draft financial assumptions are excluded.",
            "Regenerative savings should be recalculated as additional verified expense, output, and practice records mature.",
        ],
        "generated_at": "2026-10-28T00:00:00+00:00",
    }


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.rolled_back = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))


def test_read_sets_tenant_context_before_generating_one_location_report():
    connection = _Connection()
    operations = connection.operations
    report = {"report_type": "comprehensive_status", "locations": []}

    def set_context(conn, **kwargs):
        assert conn is connection
        operations.append(("tenant_context", kwargs))

    def generate(conn, **kwargs):
        assert conn is connection
        operations.append(("generate", kwargs))
        return report

    with (
        patch.object(reads, "set_operator_tenant_context", set_context),
        patch("services.export.reports.state.generate_comprehensive_status", generate),
    ):
        result = reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            period_start="2026-01-01",
            period_end="2026-06-30",
            connection_factory=lambda: connection,
        )

    assert result is report
    assert operations[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert operations[3] == (
        "tenant_context",
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "comprehensive_status",
            "action": "read",
        },
    )
    assert operations[4] == (
        "generate",
        {
            "location_id": LOCATION_ID,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
        },
    )
    assert connection.rolled_back == 1
    assert connection.closed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"operator_id": "bad", "location_id": LOCATION_ID},
        {"operator_id": OPERATOR_ID, "location_id": "bad"},
        {"operator_id": OPERATOR_ID, "location_id": LOCATION_ID, "period_start": "2026-1-1"},
        {"operator_id": OPERATOR_ID, "location_id": LOCATION_ID, "period_end": "not-a-date"},
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "period_start": "2026-06-01",
            "period_end": "2026-05-31",
        },
    ],
)
def test_invalid_identity_or_period_fails_before_database_access(kwargs):
    with pytest.raises(reads.ComprehensiveStatusReadInvalid):
        reads.get_location_comprehensive_status(
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


def test_tenant_denial_prevents_report_generation_and_closes_connection():
    connection = _Connection()

    with (
        patch.object(reads, "set_operator_tenant_context", side_effect=TenantContextDenied("denied")),
        patch("services.export.reports.state.generate_comprehensive_status") as generate,
        pytest.raises(TenantContextDenied),
    ):
        reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    generate.assert_not_called()
    assert connection.rolled_back == 2
    assert connection.closed


def test_oversized_report_is_rejected_and_connection_is_closed(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(reads, "MAX_COMPREHENSIVE_STATUS_BYTES", 8)
    monkeypatch.setattr(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.export.reports.state.generate_comprehensive_status",
        lambda *_args, **_kwargs: {"large": "payload"},
    )

    with pytest.raises(reads.ComprehensiveStatusPayloadTooLarge):
        reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    assert connection.closed


def test_route_policy_requires_exact_location_comprehensive_status_read():
    path = f"/operator/api/comprehensive-status/{LOCATION_ID}"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "comprehensive_status",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/all", enabled=True) is None


def test_http_route_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: _comprehensive_status_payload(),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["report_type"] == "comprehensive_status"
    assert response.json()["locations"][0]["location_id"] == LOCATION_ID
    plan = response.json()["locations"][0]["sections"]["financial_sustainability"]["plans"][0]
    assert plan["public_summary"] == "Synthetic public plan summary."
    assert plan["metadata"] == {"public_tag": "synthetic", "labels": ["reviewed"]}
    climate = response.json()["locations"][0]["sections"]["climate_impact"]
    assert climate["operations_protocols"] == [
        {"title": "Soil Protocol", "section": "soil_management", "version": "1.0"}
    ]
    assert climate["regenerative_score"]["principles"][0]["evidence_path"] == (
        "private://evidence/diversity.pdf"
    )
    assert climate["regenerative_score"]["principles"][0]["notes"].startswith("Reviewer notes")
    assert climate["stored_summary"]["status"] == "draft"
    assert climate["stored_summary"]["reviewed_by"]
    assert climate["stored_summary"]["notes"] == "Synthetic stored-summary note."
    regenerative = response.json()["locations"][0]["sections"]["regenerative_outcomes"]
    assert regenerative["outcomes"][0]["public_summary"] == (
        "Published synthetic outcome summary."
    )
    assert regenerative["outcomes"][0]["metadata"] == {
        "public_tag": "synthetic",
        "labels": ["reviewed"],
    }
    assert regenerative["total_hectares_restored"] == 1.25
    gnh = response.json()["locations"][0]["sections"]["gnh_alignment"]
    assert gnh["assessments"][0]["public_summary"] == (
        "Synthetic published GNH assessment."
    )
    assert gnh["assessments"][0]["strengths"] == [
        "Local stewardship council is active."
    ]
    assert gnh["assessments"][0]["metadata"] == {
        "public_tag": "synthetic",
        "labels": ["reviewed"],
    }
    assert gnh["average_alignment_score"] == 8.5
    capital = response.json()["locations"][0]["sections"]["capital_efficiency"]
    assert capital["scenarios"][0]["public_summary"] == (
        "Published synthetic capital scenario."
    )
    assert capital["scenarios"][0]["metadata"] == {
        "public_tag": "synthetic",
        "labels": ["reviewed"],
    }
    assert capital["scenarios"][0]["net_output_value_usd"] == -250.0
    assert capital["regenerative_efficiency"][0]["cost_savings_pct"] == -25.0
    assert capital["regenerative_efficiency"][0]["incremental_output_value_usd"] == -10.0

    response_schema = app.openapi()["paths"][
        "/operator/api/comprehensive-status/{location_id}"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {
        "$ref": "#/components/schemas/ComprehensiveStatusResponse"
    }
    schemas = app.openapi()["components"]["schemas"]
    assert schemas["ComprehensiveStatusResponse"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusLocation"]["additionalProperties"] is False
    section_schema = schemas["ComprehensiveStatusSections"]
    assert section_schema["additionalProperties"] is False
    assert set(section_schema["properties"]) == set(COMPREHENSIVE_STATUS_SECTIONS)
    crop_noi_schema = section_schema["properties"]["crop_noi"]
    assert len(crop_noi_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusCropNoiReport"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusCropNoiCycle"]["additionalProperties"] is False
    farm_summary_schema = section_schema["properties"]["farm_summary"]
    assert len(farm_summary_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusFarmSummary"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusFarmLocation"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusFarmRecord"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusFarmPlot"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusFarmCropCycle"]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusFarmSummary"]["properties"]) == {
        "report_type",
        "location",
        "farms",
        "plots",
        "crop_cycles",
        "harvest_summary",
        "financial_summary",
        "expense_breakdown",
        "attestation_coverage",
        "farm_activity_summary",
        "generated_at",
    }
    environmental_schema = section_schema["properties"]["environmental"]
    assert len(environmental_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusEnvironmental"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusEnvironmentalSoilCarbon"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusEnvironmentalSpecies"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusEnvironmentalRemoteSensing"][
        "additionalProperties"
    ] is False
    assert schemas["ComprehensiveStatusEnvironmentalLoss"]["additionalProperties"] is False
    assert set(
        schemas["ComprehensiveStatusEnvironmental"]["properties"]
    ) == {
        "report_type",
        "location_id",
        "soil_carbon",
        "species_observations",
        "remote_sensing",
        "loss_events",
        "generated_at",
    }
    financial_schema = section_schema["properties"]["financial_sustainability"]
    assert len(financial_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusFinancialSustainability"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusFinancialSustainabilityPlan"]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusFinancialSustainabilityPlan"]["properties"]) == {
        "id",
        "location_id",
        "farm_id",
        "plan_name",
        "farm_model",
        "plan_period_start",
        "plan_period_end",
        "revenue_streams",
        "grant_dependency_pct",
        "reinvestment_pct",
        "public_goods_allocation_pct",
        "break_even_month",
        "runway_months",
        "projected_annual_revenue_usd",
        "projected_annual_operating_cost_usd",
        "projected_annual_noi_usd",
        "sustainability_status",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    }
    climate_schema = section_schema["properties"]["climate_impact"]
    assert len(climate_schema["anyOf"]) == 2
    for model_name in (
        "ComprehensiveStatusClimateImpact",
        "ComprehensiveStatusClimateCarbonBalance",
        "ComprehensiveStatusClimateGhgEmissions",
        "ComprehensiveStatusClimateGhgCategory",
        "ComprehensiveStatusClimateTreeCarbon",
        "ComprehensiveStatusClimateTreeSpecies",
        "ComprehensiveStatusClimateRegenerativeScore",
        "ComprehensiveStatusClimatePrinciple",
        "ComprehensiveStatusClimateFrameworkPhase",
        "ComprehensiveStatusClimateOperationsProtocol",
        "ComprehensiveStatusClimateStoredSummary",
    ):
        assert schemas[model_name]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusClimateImpact"]["properties"]) == {
        "report_type",
        "location_id",
        "location_name",
        "reporting_year",
        "carbon_balance",
        "ghg_emissions",
        "tree_carbon",
        "regenerative_score",
        "framework_phases",
        "operations_protocols",
        "stored_summary",
        "limitations",
        "generated_at",
    }
    assert set(schemas["ComprehensiveStatusClimateStoredSummary"]["properties"]) == {
        "id",
        "location_id",
        "reporting_year",
        "above_ground_carbon_tonnes",
        "below_ground_carbon_tonnes",
        "total_sequestration_tonnes_co2e",
        "transport_emissions_tonnes_co2e",
        "machinery_emissions_tonnes_co2e",
        "input_emissions_tonnes_co2e",
        "total_emissions_tonnes_co2e",
        "net_climate_impact_tonnes_co2e",
        "species_count",
        "shannon_index",
        "regenerative_score_total",
        "methodology_version",
        "data_quality_score",
        "status",
        "reviewed_by",
        "reviewed_at",
        "notes",
        "source_system",
        "source_id",
        "created_at",
        "updated_at",
    }
    regenerative_schema = section_schema["properties"]["regenerative_outcomes"]
    assert len(regenerative_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusRegenerativeOutcomes"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusRegenerativeOutcome"]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusRegenerativeOutcomes"]["properties"]) == {
        "report_type",
        "location_id",
        "location_name",
        "outcomes",
        "total_hectares_restored",
        "limitations",
        "generated_at",
    }
    assert set(schemas["ComprehensiveStatusRegenerativeOutcome"]["properties"]) == {
        "id",
        "location_id",
        "farm_id",
        "period_start",
        "period_end",
        "summary_name",
        "hectares_restored",
        "baseline_species_count",
        "latest_species_count",
        "species_diversity_delta",
        "baseline_soil_carbon_t_ha",
        "latest_soil_carbon_t_ha",
        "soil_carbon_delta_t_ha",
        "trees_planted_count",
        "trees_surviving_count",
        "tree_survival_rate_pct",
        "regenerative_score",
        "jobs_or_roles_supported_count",
        "training_hours",
        "beneficiary_count",
        "evidence_confidence",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    }
    gnh_schema = section_schema["properties"]["gnh_alignment"]
    assert len(gnh_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusGnhAlignment"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusGnhAlignmentAssessment"]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusGnhAlignment"]["properties"]) == {
        "report_type",
        "location_id",
        "location_name",
        "assessments",
        "average_alignment_score",
        "limitations",
        "generated_at",
    }
    assert set(schemas["ComprehensiveStatusGnhAlignmentAssessment"]["properties"]) == {
        "id",
        "location_id",
        "farm_id",
        "assessment_date",
        "gnh_domain",
        "principle_refs",
        "alignment_score",
        "strengths",
        "gaps",
        "safeguards",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    }
    capital_schema = section_schema["properties"]["capital_efficiency"]
    assert len(capital_schema["anyOf"]) == 2
    assert schemas["ComprehensiveStatusCapitalEfficiency"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusCapitalEfficiencyScenario"]["additionalProperties"] is False
    assert schemas["ComprehensiveStatusCapitalEfficiencyObservation"]["additionalProperties"] is False
    assert set(schemas["ComprehensiveStatusCapitalEfficiency"]["properties"]) == {
        "report_type",
        "location_id",
        "location_name",
        "scenarios",
        "regenerative_efficiency",
        "limitations",
        "generated_at",
    }
    assert set(schemas["ComprehensiveStatusCapitalEfficiencyScenario"]["properties"]) == {
        "id",
        "location_id",
        "farm_id",
        "scenario_name",
        "scenario_type",
        "period_start",
        "period_end",
        "capital_deployed_usd",
        "gross_output_value_usd",
        "net_output_value_usd",
        "public_goods_value_usd",
        "capital_leverage_ratio",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    }
    assert set(
        schemas["ComprehensiveStatusCapitalEfficiencyObservation"]["properties"]
    ) == {
        "id",
        "location_id",
        "farm_id",
        "practice_event_id",
        "observation_date",
        "practice_type",
        "baseline_cost_usd",
        "observed_cost_usd",
        "cost_savings_pct",
        "incremental_output_value_usd",
        "implementation_cost_usd",
        "payback_months",
        "public_summary",
        "evidence_maturity",
        "evidence_maturity_label",
        "metadata",
    }


def test_http_route_accepts_the_generator_section_failure_shape(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    payload = _comprehensive_status_payload()
    payload["locations"][0]["sections"]["crop_noi"] = {
        "error": "report section failed (ProgrammingError)"
    }
    payload["locations"][0]["sections"]["environmental"] = {
        "error": "report section failed (DataError)"
    }
    payload["locations"][0]["sections"]["farm_summary"] = {
        "error": "report section failed (ProgrammingError)"
    }
    payload["locations"][0]["sections"]["financial_sustainability"] = {
        "error": "report section failed (DataError)"
    }
    payload["locations"][0]["sections"]["climate_impact"] = {
        "error": "report section failed (DataError)"
    }
    payload["locations"][0]["sections"]["regenerative_outcomes"] = {
        "error": "report section failed (DataError)"
    }
    payload["locations"][0]["sections"]["gnh_alignment"] = {
        "error": "report section failed (DataError)"
    }
    payload["locations"][0]["sections"]["capital_efficiency"] = {
        "error": "report section failed (DataError)"
    }
    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: payload,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 200
    assert response.json()["locations"][0]["sections"]["crop_noi"] == {
        "error": "report section failed (ProgrammingError)"
    }
    assert response.json()["locations"][0]["sections"]["environmental"] == {
        "error": "report section failed (DataError)"
    }
    assert response.json()["locations"][0]["sections"]["farm_summary"] == {
        "error": "report section failed (ProgrammingError)"
    }
    assert response.json()["locations"][0]["sections"]["financial_sustainability"] == {
        "error": "report section failed (DataError)"
    }
    assert response.json()["locations"][0]["sections"]["climate_impact"] == {
        "error": "report section failed (DataError)"
    }
    assert response.json()["locations"][0]["sections"]["regenerative_outcomes"] == {
        "error": "report section failed (DataError)"
    }
    assert response.json()["locations"][0]["sections"]["gnh_alignment"] == {
        "error": "report section failed (DataError)"
    }
    assert response.json()["locations"][0]["sections"]["capital_efficiency"] == {
        "error": "report section failed (DataError)"
    }


@pytest.mark.parametrize(
    "invalid_projection",
    [
        "extra", "network_scope", "nested_extra", "missing_section",
        "wrong_location", "wrong_selected_location", "negative_count",
        "crop_noi_extra", "crop_noi_cycle_extra", "crop_noi_wrong_location",
        "crop_noi_error_contract", "crop_noi_numeric_string",
        "environmental_extra", "environmental_species_extra",
        "environmental_wrong_location", "environmental_numeric_string",
        "environmental_error_contract",
        "farm_summary_extra", "farm_summary_plot_extra",
        "farm_summary_numeric_string", "farm_summary_error_contract",
        "financial_plan_extra", "financial_plan_wrong_location",
        "financial_report_wrong_location", "financial_numeric_string",
        "financial_error_contract",
        "climate_report_wrong_location", "climate_calculator_wrong_location",
        "climate_stored_summary_wrong_location", "climate_stored_summary_wrong_year",
        "climate_nested_extra", "climate_numeric_string", "climate_error_contract",
        "regenerative_report_wrong_location", "regenerative_outcome_wrong_location",
        "regenerative_outcome_extra", "regenerative_numeric_string",
        "regenerative_missing_field", "regenerative_invalid_confidence",
        "regenerative_invalid_period", "regenerative_total_mismatch",
        "regenerative_error_contract",
        "gnh_report_wrong_location", "gnh_assessment_wrong_location",
        "gnh_assessment_extra", "gnh_numeric_string", "gnh_missing_field",
        "gnh_invalid_domain", "gnh_wrong_average", "gnh_error_contract",
        "capital_scenario_wrong_location", "capital_observation_wrong_location",
        "capital_scenario_extra", "capital_observation_extra",
        "capital_scenario_numeric_string", "capital_scenario_capital_negative",
        "capital_scenario_gross_negative", "capital_scenario_goods_negative",
        "capital_scenario_leverage_negative", "capital_scenario_type_invalid",
        "capital_observation_baseline_negative", "capital_observation_observed_negative",
        "capital_observation_savings_low", "capital_observation_savings_high",
        "capital_observation_implementation_negative", "capital_observation_payback_negative",
        "capital_error_contract",
    ],
)
def test_http_route_rejects_malformed_success_projection(monkeypatch, invalid_projection):
    payload = _comprehensive_status_payload()
    if invalid_projection == "extra":
        payload["source_ids"] = [str(uuid4())]
    elif invalid_projection == "network_scope":
        payload["scope"] = "all_locations"
    elif invalid_projection == "nested_extra":
        payload["locations"][0]["private_note"] = "should not be returned"
    elif invalid_projection == "missing_section":
        payload["locations"][0]["sections"].pop("capital_accounting")
    elif invalid_projection == "wrong_location":
        payload["locations"][0]["location_id"] = str(uuid4())
    elif invalid_projection == "wrong_selected_location":
        other_location_id = str(uuid4())
        payload["selected_location_ids"] = [other_location_id]
        payload["locations"][0]["location_id"] = other_location_id
    elif invalid_projection == "crop_noi_extra":
        payload["locations"][0]["sections"]["crop_noi"]["private_source_ids"] = []
    elif invalid_projection == "crop_noi_cycle_extra":
        payload["locations"][0]["sections"]["crop_noi"]["crop_cycles"][0][
            "private_notes"
        ] = "must not escape"
    elif invalid_projection == "crop_noi_wrong_location":
        payload["locations"][0]["sections"]["crop_noi"]["location_id"] = str(uuid4())
    elif invalid_projection == "crop_noi_error_contract":
        payload["locations"][0]["sections"]["crop_noi"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "crop_noi_numeric_string":
        payload["locations"][0]["sections"]["crop_noi"]["crop_cycles"][0][
            "expected_yield"
        ] = "100.0"
    elif invalid_projection == "environmental_extra":
        payload["locations"][0]["sections"]["environmental"]["private_metadata"] = {}
    elif invalid_projection == "environmental_species_extra":
        payload["locations"][0]["sections"]["environmental"][
            "species_observations"
        ][0]["observer_id"] = str(uuid4())
    elif invalid_projection == "environmental_wrong_location":
        payload["locations"][0]["sections"]["environmental"]["location_id"] = str(
            uuid4()
        )
    elif invalid_projection == "environmental_numeric_string":
        payload["locations"][0]["sections"]["environmental"]["remote_sensing"][0][
            "ndvi"
        ] = "0.72"
    elif invalid_projection == "environmental_error_contract":
        payload["locations"][0]["sections"]["environmental"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "farm_summary_extra":
        payload["locations"][0]["sections"]["farm_summary"][
            "unreviewed_source_ids"
        ] = [str(uuid4())]
    elif invalid_projection == "farm_summary_plot_extra":
        payload["locations"][0]["sections"]["farm_summary"]["plots"][0][
            "private_note"
        ] = "must not escape"
    elif invalid_projection == "farm_summary_numeric_string":
        payload["locations"][0]["sections"]["farm_summary"]["financial_summary"][
            "total_revenue"
        ] = "0.0"
    elif invalid_projection == "farm_summary_error_contract":
        payload["locations"][0]["sections"]["farm_summary"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "financial_plan_extra":
        payload["locations"][0]["sections"]["financial_sustainability"]["plans"][0][
            "counterparty_account"
        ] = "must not escape"
    elif invalid_projection == "financial_plan_wrong_location":
        payload["locations"][0]["sections"]["financial_sustainability"]["plans"][0][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "financial_report_wrong_location":
        payload["locations"][0]["sections"]["financial_sustainability"]["location_id"] = str(
            uuid4()
        )
    elif invalid_projection == "financial_numeric_string":
        payload["locations"][0]["sections"]["financial_sustainability"]["plans"][0][
            "grant_dependency_pct"
        ] = "25.0"
    elif invalid_projection == "financial_error_contract":
        payload["locations"][0]["sections"]["financial_sustainability"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "climate_report_wrong_location":
        payload["locations"][0]["sections"]["climate_impact"]["location_id"] = str(
            uuid4()
        )
    elif invalid_projection == "climate_calculator_wrong_location":
        payload["locations"][0]["sections"]["climate_impact"]["tree_carbon"][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "climate_stored_summary_wrong_location":
        payload["locations"][0]["sections"]["climate_impact"]["stored_summary"][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "climate_stored_summary_wrong_year":
        payload["locations"][0]["sections"]["climate_impact"]["stored_summary"][
            "reporting_year"
        ] = 2024
    elif invalid_projection == "climate_nested_extra":
        payload["locations"][0]["sections"]["climate_impact"]["operations_protocols"][
            0
        ]["private_content"] = "must not escape"
    elif invalid_projection == "climate_numeric_string":
        payload["locations"][0]["sections"]["climate_impact"]["carbon_balance"][
            "net_climate_impact_tonnes_co2e"
        ] = "8.75"
    elif invalid_projection == "climate_error_contract":
        payload["locations"][0]["sections"]["climate_impact"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "regenerative_report_wrong_location":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["location_id"] = str(
            uuid4()
        )
    elif invalid_projection == "regenerative_outcome_wrong_location":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "regenerative_outcome_extra":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0][
            "source_raw"
        ] = {"private": "must not escape"}
    elif invalid_projection == "regenerative_numeric_string":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0][
            "hectares_restored"
        ] = "1.2500"
    elif invalid_projection == "regenerative_missing_field":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0].pop(
            "public_summary"
        )
    elif invalid_projection == "regenerative_invalid_confidence":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0][
            "evidence_confidence"
        ] = "unreviewed"
    elif invalid_projection == "regenerative_invalid_period":
        payload["locations"][0]["sections"]["regenerative_outcomes"]["outcomes"][0][
            "period_start"
        ] = "2026-01-01"
    elif invalid_projection == "regenerative_total_mismatch":
        payload["locations"][0]["sections"]["regenerative_outcomes"][
            "total_hectares_restored"
        ] = 9.0
    elif invalid_projection == "regenerative_error_contract":
        payload["locations"][0]["sections"]["regenerative_outcomes"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "gnh_report_wrong_location":
        payload["locations"][0]["sections"]["gnh_alignment"]["location_id"] = str(
            uuid4()
        )
    elif invalid_projection == "gnh_assessment_wrong_location":
        payload["locations"][0]["sections"]["gnh_alignment"]["assessments"][0][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "gnh_assessment_extra":
        payload["locations"][0]["sections"]["gnh_alignment"]["assessments"][0][
            "source_raw"
        ] = {"private": "must not escape"}
    elif invalid_projection == "gnh_numeric_string":
        payload["locations"][0]["sections"]["gnh_alignment"]["assessments"][0][
            "alignment_score"
        ] = "8.50"
    elif invalid_projection == "gnh_missing_field":
        payload["locations"][0]["sections"]["gnh_alignment"]["assessments"][0].pop(
            "public_summary"
        )
    elif invalid_projection == "gnh_invalid_domain":
        payload["locations"][0]["sections"]["gnh_alignment"]["assessments"][0][
            "gnh_domain"
        ] = "private_unregistered_domain"
    elif invalid_projection == "gnh_wrong_average":
        payload["locations"][0]["sections"]["gnh_alignment"][
            "average_alignment_score"
        ] = 9.0
    elif invalid_projection == "gnh_error_contract":
        payload["locations"][0]["sections"]["gnh_alignment"] = {
            "error": "database connection failed with private SQL"
        }
    elif invalid_projection == "capital_scenario_wrong_location":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "location_id"
        ] = str(uuid4())
    elif invalid_projection == "capital_observation_wrong_location":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["location_id"] = str(uuid4())
    elif invalid_projection == "capital_scenario_extra":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "source_raw"
        ] = {"private": "must not escape"}
    elif invalid_projection == "capital_observation_extra":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["source_id"] = "private-source-id"
    elif invalid_projection == "capital_scenario_numeric_string":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "capital_deployed_usd"
        ] = "10000.00"
    elif invalid_projection == "capital_scenario_capital_negative":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "capital_deployed_usd"
        ] = Decimal("-1.00")
    elif invalid_projection == "capital_scenario_gross_negative":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "gross_output_value_usd"
        ] = Decimal("-1.00")
    elif invalid_projection == "capital_scenario_goods_negative":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "public_goods_value_usd"
        ] = Decimal("-1.00")
    elif invalid_projection == "capital_scenario_leverage_negative":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "capital_leverage_ratio"
        ] = Decimal("-1.00")
    elif invalid_projection == "capital_scenario_type_invalid":
        payload["locations"][0]["sections"]["capital_efficiency"]["scenarios"][0][
            "scenario_type"
        ] = "unknown_scenario"
    elif invalid_projection == "capital_observation_baseline_negative":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["baseline_cost_usd"] = Decimal("-1.00")
    elif invalid_projection == "capital_observation_observed_negative":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["observed_cost_usd"] = Decimal("-1.00")
    elif invalid_projection == "capital_observation_savings_low":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["cost_savings_pct"] = Decimal("-100.01")
    elif invalid_projection == "capital_observation_savings_high":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["cost_savings_pct"] = Decimal("100.01")
    elif invalid_projection == "capital_observation_implementation_negative":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["implementation_cost_usd"] = Decimal("-1.00")
    elif invalid_projection == "capital_observation_payback_negative":
        payload["locations"][0]["sections"]["capital_efficiency"][
            "regenerative_efficiency"
        ][0]["payback_months"] = Decimal("-1.00")
    elif invalid_projection == "capital_error_contract":
        payload["locations"][0]["sections"]["capital_efficiency"] = {
            "error": "database connection failed with private SQL"
        }
    else:
        payload["ecosystem_overview"]["total_locations"] = -1

    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: payload,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 500
    assert response.json() == {"error": "Comprehensive Status read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_http_route_returns_404_when_oidc_is_disabled():
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("disabled OIDC must not invoke the read service")

    register_comprehensive_status_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_route_maps_tenant_grant_denial_to_no_store_403(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status", deny
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "A tenant-qualified Comprehensive Status read grant is required"
    }


def test_http_route_caps_final_encoded_response(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    monkeypatch.setattr(reads, "MAX_COMPREHENSIVE_STATUS_BYTES", 8)
    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: _comprehensive_status_payload(),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
