"""Platform definition-of-done verifier for a seeded local database.

Replaces test_mvp_done.py with comprehensive coverage of the full platform:
Critical platform tables, views, workflow specs, services, process maps,
and all governed seed data.

Usage:
    python3 -m tests.test_platform_done
    ./scripts/verify-platform.sh
"""

from __future__ import annotations

import subprocess
import sys
from typing import List, Tuple

import pytest


PILOT_LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


# ── Helpers ──────────────────────────────────────────────────────────────────

def database_running() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "--services"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return False
    return result.returncode == 0 and "database" in result.stdout.splitlines()


def run_sql(sql: str) -> List[Tuple[str, bool]]:
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "database",
            "psql", "-U", "kokonut", "-d", "kokonut_intelligence",
            "-At", "-F", "|", "-c", sql,
        ],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Platform SQL verifier failed")
    checks: List[Tuple[str, bool]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, ok = line.split("|", 1)
        checks.append((name, ok == "t"))
    return checks


def to_regclass_check(*tables: str) -> str:
    parts = [f"to_regclass('public.{t}') IS NOT NULL" for t in tables]
    return " AND ".join(parts)


def count_check(table: str, min_count: int, where: str = "") -> str:
    w = f" WHERE {where}" if where else ""
    return f"(SELECT count(*) FROM {table}{w}) >= {min_count}"


def _batch(name_checks: List[Tuple[str, str]]) -> str:
    """Build UNION ALL SELECT clauses from (name, sql_condition) pairs."""
    parts = []
    for name, cond in name_checks:
        parts.append(f"SELECT '{name}', {cond}")
    return " UNION ALL ".join(parts)


# ── Check Sections ───────────────────────────────────────────────────────────

def schema_completeness_checks() -> List[Tuple[str, bool]]:
    """Section 1: Verify all critical tables exist."""
    critical_tables = [
        # Agriculture & Environment
        "location", "farm", "plot", "crop_cycle", "crop", "farm_activity",
        "harvest_event", "expense_event", "revenue_event", "farm_zone",
        "farm_practice_event", "farm_impact_mapping", "farm_registry_record",
        "soil_sample", "soil_carbon_measurement", "weather_observation",
        "weather_forecast", "sensor_reading", "sensor_device",
        "irrigation_program", "irrigation_zone", "tree_inventory",
        "water_analysis", "water_sample",
        # Carbon & Ecology
        "carbon_credit", "carbon_benchmark", "ghg_emission_factor",
        "ghg_emissions_inventory", "regenerative_practice_checklist",
        "framework_phase", "climate_impact_summary", "habitat_zone",
        "wildlife_corridor", "pollinator_observation", "species_observation",
        "waste_stream",
        # Credit & Marketplace
        "credit_class", "credit_batch", "credit_balance", "credit_retirement",
        "credit_basket", "market_listing", "market_order",
        # Threatcasting
        "threat", "threat_narrative", "threat_flag", "threat_signal",
        "threat_cross_impact", "threat_cascade", "threat_horizon",
        "backcast_plan", "backcast_principle",
        # Process Management (Phase 1-5 + 6A-6D)
        "process_map", "process_ownership", "process_entity_mapping",
        "process_handoff", "process_handoff_log", "process_trace",
        "process_target", "process_gap", "process_maturity", "process_maturity_level",
        "process_cost", "process_cost_observation", "process_benchmark", "process_improvement",
        "process_simulation", "process_simulation_result", "process_capability",
        "process_model", "process_variant", "work_item",
        # Service & Data Quality (Phase 6C)
        "service_registry", "data_quality_rule", "data_quality_score",
        # Business Architecture
        "business_capability", "capability_process_map", "capability_service_map",
        "capability_maturity_assessment", "strategy_map", "strategy_capability_map",
        "strategy_initiative", "vision_mission", "value_stream_definition",
        "value_stream_stage", "value_stream_stage_observation",
        # PRM (Phase 6D)
        "customer_satisfaction",
        # Governance & Wellbeing
        "stakeholder_feedback", "stakeholder_feedback_review", "stakeholder_outcome",
        "impact_claim", "metric_proposal", "metric_value", "metric_definition",
        "metric_version", "ai_summary", "report_snapshot",
        # Finance
        "noi_snapshot", "cash_flow_snapshot", "financial_plan",
        "farm_launch_unit_economics", "revenue_multiplier_config",
        # OODA Loop
        "decision_policy", "situation_assessment", "adaptive_threshold",
        "decision_log",
        # Data & Linked Data
        "data_stream_post", "iri_registry", "rdf_triple", "rdf_named_graph",
        "linkml_schema",
        # Agent Safety
        "agent_task", "agent_identity",
        # CRISP Risk
        "crisp_risk_assessment", "crisp_risk_dimension", "crisp_location_weight",
        # Pest Management
        "pest_scouting_record", "pest_intervention", "pesticide_application_log",
        "pest_action_threshold", "pest_trap",
        # Digital Finance
        "insurance_claim", "digital_lending",
        # Cooperative
        "cooperative", "cooperative_membership", "collective_purchase",
        # Extension
        "extension_module", "training_enrollment", "training_progress",
        # EBF
        "ebf_scorecard", "ebf_score", "ebf_pillar",
        # Systems Thinking
        "causal_loop", "leverage_assessment", "system_archetype",
        "stock_flow_model",
        # Trend Analysis
        "trend_estimate", "change_point", "trend_smoothing",
        # Geostatistics
        "geostat_realization",
        # Precision Ag
        "prescription" if False else "nutrient_budget",  # placeholder
        # Digital Twin
        "digital_twin", "what_if_scenario",
        # Mobile
        "mobile_device", "offline_collection",
        # LLM Chat
        "chat_session", "chat_message",
        # Planning
        "objective", "project", "program",
        # Management
        "responsibility_assignment", "staff",
        # Security
        "audit_log", "access_audit_log",
        # Data Governance
        "data_sharing_agreement", "data_sharing_consent",
        "data_portability_request", "data_retention_policy",
        # Event System
        "platform_event", "event_dead_letter",
        # Scheduler
        "scheduled_job", "scheduled_task",
        # Migration
        "schema_migration",
        # Federation
        "federation_node",
        # Delphi
        "delphi_study", "delphi_panel_member", "delphi_item",
        # Guilds
        "colony_instance", "kokonut_guild", "guild_contribution",
        # Coordination governance and learning
        "coordination_alliance", "coordination_participant", "coordination_objective",
        "coordination_contribution", "coordination_benefit", "coordination_risk",
        "coordination_knowledge_exchange", "coordination_review", "coordination_learning_link",
        "coordination_metric_observation", "coordination_conflict_declaration",
        "coordination_benefit_harm_analysis", "coordination_minority_view",
        "coordination_appeal", "coordination_remedy", "coordination_approval",
        "coordination_partner_event", "coordination_market_observation",
    ]
    values = ",".join(f"('{t}')" for t in critical_tables)
    sql = f"SELECT 'table:' || v, to_regclass('public.' || v) IS NOT NULL FROM (VALUES {values}) AS vs(v)"
    return run_sql(sql)


def seed_data_checks() -> List[Tuple[str, bool]]:
    """Section 2: Verify critical seed data."""
    checks = [
        ("seed:process_map >= 27", count_check("process_map", 27)),
        ("seed:process_target >= 30", count_check("process_target", 30)),
        ("seed:process_cost >= 25", count_check("process_cost", 25)),
        ("seed:process_handoff >= 9", count_check("process_handoff", 9)),
        ("seed:process_maturity_level = 5",
         "(SELECT count(*) FROM process_maturity_level) = 5"),
        ("seed:process_model >= 3", count_check("process_model", 3)),
        ("seed:process_entity_mapping >= 22", count_check("process_entity_mapping", 22)),
        ("seed:service_registry >= 57", count_check("service_registry", 57)),
        ("seed:business_capability >= 30",
         count_check("business_capability", 30, "status = 'active'")),
        ("seed:capability_process_map >= 30", count_check("capability_process_map", 30)),
        ("seed:capability_service_map >= 60", count_check("capability_service_map", 60)),
        ("seed:strategy_map perspectives = 4",
         "(SELECT count(DISTINCT perspective) FROM strategy_map WHERE entity_type = 'platform') = 4"),
        ("seed:vision_mission approved >= 3",
         count_check("vision_mission", 3, "entity_type = 'platform' AND status = 'approved'")),
        ("seed:value_stream_definition >= 4",
         count_check("value_stream_definition", 4, "status = 'active'")),
        ("seed:data_quality_rule >= 14", count_check("data_quality_rule", 14)),
        ("seed:impact_framework >= 7",
         count_check("impact_framework", 7, "status = 'active'")),
        ("seed:sdg >= 17",
         count_check("sdg", 17, "is_active = TRUE")),
        ("seed:form_of_capital >= 8",
         count_check("form_of_capital", 8, "is_active = TRUE")),
        ("seed:regeneration_principle >= 5",
         count_check("regeneration_principle", 5, "status = 'active'")),
        ("seed:evidence_maturity_level = 7",
         "(SELECT count(*) FROM evidence_maturity_level) = 7"),
        ("seed:attestation_schema celo = 5",
         "(SELECT count(*) FROM attestation_schema WHERE chain = 'celo' AND active = TRUE) >= 5"),
        ("seed:ghg_emission_factor >= 10",
         count_check("ghg_emission_factor", 10)),
        ("seed:carbon_benchmark >= 5",
         count_check("carbon_benchmark", 5)),
        ("seed:operations_protocol active >= 4",
         count_check("operations_protocol", 4, "status = 'active'")),
        ("seed:schema_version >= 1", count_check("schema_version", 1)),
        ("seed:metric_definition >= 1",
         count_check("metric_definition", 1, "version IS NOT NULL")),
        ("seed:metric_version >= 1", count_check("metric_version", 1)),
        ("seed:kokonut_guild active >= 6",
         count_check("kokonut_guild", 6, "status = 'active'")),
        ("seed:guild_contribution published >= 3",
         count_check("guild_contribution", 3, "review_status = 'published'")),
        ("seed:draft Adelphi coordination example",
         "EXISTS (SELECT 1 FROM coordination_alliance WHERE id = 'a0000000-0000-0000-0000-000000002000' AND status = 'draft')"),
    ]
    sql = _batch(checks)
    return run_sql(sql)


def process_architecture_checks() -> List[Tuple[str, bool]]:
    """Section 3: Process architecture integrity."""
    checks = [
        ("process:27 process_map entries",
         "(SELECT count(*) FROM process_map) >= 27"),
        ("process:all process_types valid",
         "NOT EXISTS (SELECT 1 FROM process_map WHERE process_type NOT IN ('management', 'core', 'support'))"),
        ("process:22+ entity_mappings",
         "(SELECT count(*) FROM process_entity_mapping) >= 22"),
        ("process:9 handoffs",
         "(SELECT count(*) FROM process_handoff) >= 9"),
        ("process:handoff_log table ready",
         "to_regclass('public.process_handoff_log') IS NOT NULL"),
        ("process:trace table ready",
         "to_regclass('public.process_trace') IS NOT NULL"),
        ("process:maturity levels 1-5",
         "(SELECT count(*) FROM process_maturity_level) = 5"),
        ("process:cost types valid",
         "NOT EXISTS (SELECT 1 FROM process_cost WHERE cost_type NOT IN ('labor', 'compute', 'external', 'opportunity'))"),
        ("process:simulation table ready",
         "to_regclass('public.process_simulation') IS NOT NULL"),
        ("process:capability table ready",
         "to_regclass('public.process_capability') IS NOT NULL"),
    ]
    sql = _batch(checks)
    return run_sql(sql)


def view_integrity_checks() -> List[Tuple[str, bool]]:
    """Section 4: Critical views exist and have correct definitions."""
    checks = [
        ("view:v_public_metric_summary exists",
         to_regclass_check("v_public_metric_summary")),
        ("view:v_public_metric_summary has verified gate",
         "pg_get_viewdef('v_public_metric_summary'::regclass, TRUE) ILIKE '%verified = true%'"),
        ("view:v_public_farm_summary exists",
         to_regclass_check("v_public_farm_summary")),
        ("view:v_public_attestation_summary exists",
         to_regclass_check("v_public_attestation_summary")),
        ("view:v_total_cost_of_ownership exists",
         to_regclass_check("v_total_cost_of_ownership")),
        ("view:v_process_outcome_correlation exists",
         to_regclass_check("v_process_outcome_correlation")),
        ("view:v_carbon_balance exists",
         to_regclass_check("v_carbon_balance")),
        ("view:v_regenerative_score_summary exists",
         to_regclass_check("v_regenerative_score_summary")),
        ("view:v_ghg_emissions_summary exists",
         to_regclass_check("v_ghg_emissions_summary")),
        ("view:v_framework_phase_status exists",
         to_regclass_check("v_framework_phase_status")),
        ("view:v_daoip5_project_json exists",
         to_regclass_check("v_daoip5_project_json")),
        ("view:v_crop_forecast_summary exists",
         to_regclass_check("v_crop_forecast_summary")),
        ("view:v_public_stakeholder_feedback_summary exists",
         to_regclass_check("v_public_stakeholder_feedback_summary")),
        ("view:v_public_impact_claim_summary exists",
         to_regclass_check("v_public_impact_claim_summary")),
        ("view:v_public_flora_fauna_summary exists",
         to_regclass_check("v_public_flora_fauna_summary")),
        ("view:v_public_farm_places exists",
         to_regclass_check("v_public_farm_places")),
        ("view:v_crisp_composite_rating exists",
         to_regclass_check("v_crisp_composite_rating")),
        ("view:v_delphi_study_summary exists",
         to_regclass_check("v_delphi_study_summary")),
        ("view:v_capability_dashboard exists",
         to_regclass_check("v_capability_dashboard")),
        ("view:v_strategy_execution exists",
         to_regclass_check("v_strategy_execution")),
        ("view:v_current_vision_mission exists",
         to_regclass_check("v_current_vision_mission")),
        ("view:v_value_stream_performance exists",
         to_regclass_check("v_value_stream_performance")),
        ("view:v_coordination_cockpit_internal exists",
         to_regclass_check("v_coordination_cockpit_internal")),
        ("view:v_public_coordination_alliance exists",
         to_regclass_check("v_public_coordination_alliance")),
    ]
    sql = _batch(checks)
    return run_sql(sql)


def pilot_data_checks() -> List[Tuple[str, bool]]:
    """Section 5: Adelphi pilot data integrity."""
    pid = PILOT_LOCATION_ID
    checks = [
        ("pilot:adelphi location exists",
         f"EXISTS (SELECT 1 FROM location WHERE id = '{pid}' AND slug = 'kokonut-adelphi')"),
        ("pilot:registry record published",
         f"EXISTS (SELECT 1 FROM farm_registry_record WHERE location_id = '{pid}' AND status = 'published')"),
        ("pilot:farm record exists",
         f"(SELECT count(*) FROM farm WHERE location_id = '{pid}') >= 1"),
        ("pilot:plot record exists",
         f"(SELECT count(*) FROM plot p JOIN farm f ON f.id = p.farm_id WHERE f.location_id = '{pid}') >= 1"),
        ("pilot:crop_cycle exists",
         f"(SELECT count(*) FROM crop_cycle WHERE location_id = '{pid}') >= 1"),
        ("pilot:farm_activity exists",
         f"(SELECT count(*) FROM farm_activity WHERE location_id = '{pid}') >= 1"),
        ("pilot:harvest_event exists",
         f"(SELECT count(*) FROM harvest_event WHERE location_id = '{pid}') >= 1"),
        ("pilot:expense_event exists",
         f"(SELECT count(*) FROM expense_event WHERE location_id = '{pid}') >= 1"),
        ("pilot:metric_value exists",
         f"(SELECT count(*) FROM metric_value WHERE location_id = '{pid}') >= 1"),
        ("pilot:noi_snapshot exists",
         f"(SELECT count(*) FROM noi_snapshot WHERE location_id = '{pid}') >= 1"),
        ("pilot:expense lineage",
         f"NOT EXISTS (SELECT 1 FROM expense_event WHERE location_id = '{pid}' AND (source_system IS NULL OR source_id IS NULL))"),
        ("pilot:harvest lineage",
         f"NOT EXISTS (SELECT 1 FROM harvest_event WHERE location_id = '{pid}' AND (source_system IS NULL OR source_id IS NULL))"),
        ("pilot:environmental_baseline",
         f"(SELECT count(*) FROM environmental_baseline WHERE location_id = '{pid}') >= 1"),
        ("pilot:farm_zones active >= 3",
         f"(SELECT count(*) FROM farm_zone WHERE location_id = '{pid}' AND status = 'active') >= 3"),
        ("pilot:farm_impact_mapping published >= 10",
         f"(SELECT count(*) FROM farm_impact_mapping WHERE location_id = '{pid}' AND status = 'published') >= 10"),
        ("pilot:farm_practice_event published >= 5",
         f"(SELECT count(*) FROM farm_practice_event WHERE location_id = '{pid}' AND status = 'published') >= 5"),
    ]
    sql = _batch(checks)
    return run_sql(sql)


def governance_view_checks() -> List[Tuple[str, bool]]:
    """Section 6: Public view governance gates."""
    checks = [
        ("govt:public farm view filters registry",
         """NOT EXISTS (
            SELECT 1 FROM v_public_farm_summary v
            WHERE NOT EXISTS (
                SELECT 1 FROM farm_registry_record fr
                WHERE fr.location_id = v.location_id
                  AND fr.status IN ('verified', 'published')
            )
        )"""),
        ("govt:stakeholder feedback privacy",
         f"NOT EXISTS (SELECT 1 FROM v_public_stakeholder_feedback_summary WHERE public_summary IS NULL)"),
        ("govt:impact claim level6 carbon gate",
         """NOT EXISTS (
            SELECT 1 FROM v_public_impact_claim_summary
            WHERE claim_category = 'carbon' AND evidence_maturity < 6
        )"""),
    ]
    sql = _batch(checks)
    return run_sql(sql)


def framework_reference_checks() -> List[Tuple[str, bool]]:
    """Section 7: Framework and blockchain reference data."""
    checks = [
        ("chain:gnosis dao metadata",
         """EXISTS (SELECT 1 FROM protocol WHERE slug = 'kokonut-treasury' AND chain = 'gnosis')
            AND (SELECT count(*) FROM wallet_profile WHERE chain = 'gnosis' AND owner_type = 'dao') >= 4"""),
        ("chain:celo resolver",
         """EXISTS (SELECT 1 FROM attestation_schema
            WHERE chain = 'celo' AND resolver_address = '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad'
            AND active = TRUE)"""),
        ("framework:impact_framework active >= 7",
         count_check("impact_framework", 7, "status = 'active'")),
        ("framework:regeneration_principle active >= 5",
         count_check("regeneration_principle", 5, "status = 'active'")),
        ("framework:colony_instance exists",
         "EXISTS (SELECT 1 FROM colony_instance WHERE colony_key = 'kokonut-guilds')"),
    ]
    sql = _batch(checks)
    return run_sql(sql)


# ── Main Entry Point ─────────────────────────────────────────────────────────

def all_checks() -> List[Tuple[str, bool]]:
    results: List[Tuple[str, bool]] = []
    sections = [
        ("Schema Completeness", schema_completeness_checks),
        ("Seed Data Integrity", seed_data_checks),
        ("Process Architecture", process_architecture_checks),
        ("View Integrity", view_integrity_checks),
        ("Pilot Data (Adelphi)", pilot_data_checks),
        ("Governance Views", governance_view_checks),
        ("Framework & Chain", framework_reference_checks),
    ]
    for section_name, check_fn in sections:
        print(f"\n  [{section_name}]")
        try:
            section_results = check_fn()
            for name, ok in section_results:
                status = "✓" if ok else "✗"
                print(f"    {status} {name}")
            results.extend(section_results)
        except Exception as e:
            print(f"    ✗ Section failed: {e}")
            results.append((section_name, False))
    return results


def run_platform_done() -> List[Tuple[str, bool]]:
    if not database_running():
        print("  ⚠ Database service not running — skipping platform verifier")
        return []

    print("\n=== Platform Definition Of Done ===")
    results = all_checks()

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n  Results: {passed} passed, {failed} failed, {len(results)} total")

    failures = [name for name, ok in results if not ok]
    if failures:
        print("\nFailed checks:")
        for name in failures:
            print(f"  - {name}")
    else:
        print("\n  All platform checks passed ✓")
    return results


def test_platform_done() -> None:
    if not database_running():
        pytest.skip("Database service not running")

    results = run_platform_done()
    failures = [name for name, ok in results if not ok]
    assert not failures, f"Platform checks failed: {', '.join(failures)}"


if __name__ == "__main__":
    results = run_platform_done()
    if results and any(not ok for _, ok in results):
        sys.exit(1)
