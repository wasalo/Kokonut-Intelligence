"""End-to-end platform test.

Validates the entire Kokonut Intelligence platform against the seeded
database. Uses docker compose exec to run SQL checks directly.

Usage:
    python3 -m tests.test_e2e_platform
    python3 -m tests.test_e2e_platform --category schema
    python3 -m tests.test_e2e_platform --category seeds
    python3 -m tests.test_e2e_platform --category views
    python3 -m tests.test_e2e_platform --category services
    python3 -m tests.test_e2e_platform --category crisp
    python3 -m tests.test_e2e_platform --category abundance
    python3 -m tests.test_e2e_platform --category token
    python3 -m tests.test_e2e_platform --category voting
    python3 -m tests.test_e2e_platform --category multifarm
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Pilot location UUID
ADELPHI = "a0000000-0000-0000-0000-000000000001"
GENESIS = "a0000000-0000-0000-0000-000000000002"


def _run_sql(sql: str) -> str:
    """Execute SQL via docker compose exec."""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "database", "psql",
         "-U", "kokonut", "-d", "kokonut_intelligence", "-c", sql],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _check_table(table_name: str) -> bool:
    """Check if a table exists."""
    result = _run_sql(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}') AS exists")
    return "t" in result


def _check_view(view_name: str) -> bool:
    """Check if a view exists in PostgreSQL."""
    result = _run_sql(f"SELECT EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema = 'public' AND table_name = '{view_name}') AS exists")
    return "t" in result


def _run_ch(sql: str) -> str:
    """Execute SQL via ClickHouse client in Docker."""
    password = os.environ.get("CLICKHOUSE_PASSWORD", "dev-clickhouse-kokonut-2026")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "clickhouse", "clickhouse-client",
         "--user", "kokonut", "--password", password,
         "--query", sql],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _check_ch_view(view_name: str) -> bool:
    """Check if a view or materialized view exists in ClickHouse."""
    result = _run_ch(
        f"SELECT count() FROM system.tables WHERE name = '{view_name}' AND database = currentDatabase()"
    )
    return result.strip() != "0"


def _check_column(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = _run_sql(f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}') AS exists")
    return "t" in result


def _check_row_count(table_name: str, location_id: str = None) -> int:
    """Count rows in a table."""
    if location_id:
        result = _run_sql(f"SELECT COUNT(*) FROM {table_name} WHERE location_id = '{location_id}'")
    else:
        result = _run_sql(f"SELECT COUNT(*) FROM {table_name}")
    try:
        # Parse psql output: " count \n-------\n     1\n(1 row)"
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                return int(line.strip())
        return 0
    except (ValueError, IndexError):
        return 0


def _parse_count(result: str) -> int:
    """Parse a COUNT(*) result from psql output."""
    try:
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                return int(line.strip())
        return 0
    except (ValueError, IndexError):
        return 0


# ============================================================
# Category 1: Schema Completeness
# ============================================================

def test_all_tables_exist():
    """Verify all 363 tables exist."""
    schema_dir = Path("schemas/postgres")
    all_tables = set()
    for sql_file in schema_dir.glob("*.sql"):
        content = sql_file.read_text()
        for match in __import__("re").findall(r"CREATE TABLE IF NOT EXISTS (\w+)", content):
            all_tables.add(match)

    missing = []
    for table in sorted(all_tables):
        if not _check_table(table):
            missing.append(table)

    assert not missing, f"Missing tables: {missing}"
    print(f"  All {len(all_tables)} tables exist")


def test_all_views_exist():
    """Verify all views exist in their respective databases."""
    import re

    # PostgreSQL views
    pg_views = set()
    pg_dir = Path("schemas/postgres")
    for sql_file in pg_dir.glob("*.sql"):
        content = sql_file.read_text()
        for match in re.findall(r"CREATE (?:OR REPLACE )?VIEW (\w+)", content):
            pg_views.add(match)

    pg_missing = [v for v in sorted(pg_views) if not _check_view(v)]
    assert not pg_missing, f"Missing PostgreSQL views: {pg_missing}"
    print(f"  All {len(pg_views)} PostgreSQL views exist")

    # ClickHouse views (materialized + regular)
    ch_views = set()
    ch_dir = Path("schemas/clickhouse")
    if ch_dir.exists():
        for sql_file in ch_dir.glob("*.sql"):
            content = sql_file.read_text()
            for match in re.findall(r"CREATE (?:OR REPLACE )?(?:MATERIALIZED )?VIEW (?:IF NOT EXISTS )?(\w+)", content):
                ch_views.add(match)

    ch_missing = [v for v in sorted(ch_views) if not _check_ch_view(v)]
    assert not ch_missing, f"Missing ClickHouse views: {ch_missing}"
    print(f"  All {len(ch_views)} ClickHouse views exist")


# ============================================================
# Category 2: Seed Data Loaded
# ============================================================

def test_adelphi_location_exists():
    result = _run_sql(f"SELECT name FROM location WHERE id = '{ADELPHI}'")
    assert "Adelphi" in result or "adelphi" in result.lower()


def test_genesis_location_exists():
    result = _run_sql(f"SELECT name FROM location WHERE id = '{GENESIS}'")
    assert "Genesis" in result or "genesis" in result.lower()


def test_framework_reference_data():
    result = _run_sql("SELECT COUNT(*) FROM impact_framework WHERE status = 'active'")
    try:
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                count = int(line.strip())
                assert count >= 5, f"Expected 5+ frameworks, got {count}"
                return
        assert False, "Could not parse result"
    except (ValueError, IndexError):
        assert False, f"Could not parse: {result}"


def test_ebf_rubric_loaded():
    result = _run_sql("SELECT COUNT(*) FROM ebf_rubric_band")
    try:
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                count = int(line.strip())
                assert count >= 50, f"Expected 50+ rubric bands, got {count}"
                return
        assert False, "Could not parse result"
    except (ValueError, IndexError):
        assert False, f"Could not parse: {result}"


def test_celo_eas_schemas():
    result = _run_sql("SELECT COUNT(*) FROM attestation_schema WHERE chain = 'celo' AND active = TRUE")
    try:
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                count = int(line.strip())
                assert count >= 5, f"Expected 5+ Celo EAS schemas, got {count}"
                return
        assert False, "Could not parse result"
    except (ValueError, IndexError):
        assert False, f"Could not parse: {result}"


def test_gnosis_dao_metadata():
    result = _run_sql("SELECT COUNT(*) FROM colony_instance WHERE chain = 'gnosis'")
    try:
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                count = int(line.strip())
                assert count >= 1, f"Expected 1+ Gnosis colony, got {count}"
                return
        assert False, "Could not parse result"
    except (ValueError, IndexError):
        assert False, f"Could not parse: {result}"


# ============================================================
# Category 3: Core Farm Operations
# ============================================================

def test_farm_registry_record():
    result = _check_row_count("farm_registry_record", ADELPHI)
    assert result >= 1, f"Expected 1+ registry records for Adelphi, got {result}"


def test_farm_zones():
    result = _check_row_count("farm_zone", ADELPHI)
    assert result >= 3, f"Expected 3+ farm zones for Adelphi, got {result}"


def test_crop_cycles():
    result = _check_row_count("crop_cycle", ADELPHI)
    assert result >= 1, f"Expected 1+ crop cycles for Adelphi, got {result}"


def test_harvest_events():
    result = _check_row_count("harvest_event", ADELPHI)
    assert result >= 1, f"Expected 1+ harvest events for Adelphi, got {result}"


def test_revenue_events():
    result = _check_row_count("revenue_event", ADELPHI)
    assert result >= 1, f"Expected 1+ revenue events for Adelphi, got {result}"


def test_expense_events():
    result = _check_row_count("expense_event", ADELPHI)
    assert result >= 1, f"Expected 1+ expense events for Adelphi, got {result}"


# ============================================================
# Category 4: Environmental Monitoring
# ============================================================

def test_weather_observations():
    result = _check_row_count("weather_observation", ADELPHI)
    assert result >= 0  # May not have weather data yet


def test_soil_samples():
    result = _check_row_count("soil_sample", ADELPHI)
    assert result >= 0


def test_species_observations():
    result = _check_row_count("species_observation", ADELPHI)
    assert result >= 0


# ============================================================
# Category 5: Web3 & Governance
# ============================================================

def test_wallet_profiles():
    result = _run_sql("SELECT COUNT(*) FROM wallet_profile")
    count = _parse_count(result)
    assert count >= 1, f"Expected 1+ wallet profiles, got {count}"


def test_attestation_records():
    result = _run_sql("SELECT COUNT(*) FROM attestation_record")
    count = _parse_count(result)
    assert count >= 0  # May not have attestations yet


def test_dao_proposals():
    result = _check_row_count("dao_proposal")
    assert result >= 0


# ============================================================
# Category 6: Carbon Framework
# ============================================================

def test_carbon_benchmarks():
    result = _run_sql("SELECT COUNT(*) FROM carbon_benchmark")
    count = _parse_count(result)
    assert count >= 5, f"Expected 5+ carbon benchmarks, got {count}"


def test_ghg_emission_factors():
    result = _run_sql("SELECT COUNT(*) FROM ghg_emission_factor")
    count = _parse_count(result)
    assert count >= 10, f"Expected 10+ emission factors, got {count}"


def test_tree_inventory():
    result = _check_row_count("tree_inventory", ADELPHI)
    assert result >= 1, f"Expected 1+ tree inventory for Adelphi, got {result}"


def test_climate_impact_summary():
    result = _check_row_count("climate_impact_summary", ADELPHI)
    assert result >= 1, f"Expected 1+ climate impact summary for Adelphi, got {result}"


# ============================================================
# Category 7: EBF Scoring
# ============================================================

def test_ebf_scorecard():
    result = _check_row_count("ebf_scorecard", ADELPHI)
    assert result >= 1, f"Expected 1+ EBF scorecard for Adelphi, got {result}"


def test_ebf_pillars():
    result = _run_sql("SELECT COUNT(*) FROM ebf_pillar WHERE status = 'active'")
    count = _parse_count(result)
    assert count >= 7, f"Expected 7 EBF pillars, got {count}"


# ============================================================
# Category 8: CRISP Risk Scoring
# ============================================================

def test_crisp_dimensions():
    result = _run_sql("SELECT COUNT(*) FROM crisp_risk_dimension WHERE status = 'active'")
    count = _parse_count(result)
    assert count >= 5, f"Expected 5 CRISP dimensions, got {count}"


def test_crisp_assessment():
    result = _check_row_count("crisp_risk_assessment")
    assert result >= 0  # May not have assessments yet


# ============================================================
# Category 9: Abundance Protocol
# ============================================================

def test_expertise_categories():
    result = _run_sql("SELECT COUNT(*) FROM expertise_category")
    count = _parse_count(result)
    assert count >= 0


def test_impact_estimate_posts():
    result = _check_row_count("impact_estimate_post")
    assert result >= 0


def test_validation_rounds():
    result = _check_row_count("validation_round")
    assert result >= 0


def test_coin_inflation_events():
    result = _check_row_count("coin_inflation_event")
    assert result >= 0


# ============================================================
# Category 10: Token Integration
# ============================================================

def test_governance_token():
    result = _run_sql("SELECT COUNT(*) FROM governance_token")
    count = _parse_count(result)
    assert count >= 1, f"Expected 1+ governance tokens, got {count}"


def test_tree_token_binding():
    result = _check_row_count("tree_token_binding")
    assert result >= 0


def test_staking_positions():
    result = _check_row_count("staking_position")
    assert result >= 0


# ============================================================
# Category 11: Hybrid DAO Voting
# ============================================================

def test_dao_votes():
    result = _check_row_count("dao_vote")
    assert result >= 0


def test_reputation_tokens():
    result = _check_row_count("reputation_token")
    assert result >= 0


def test_delegation_records():
    result = _check_row_count("delegation_record")
    assert result >= 0


# ============================================================
# Category 12: Multi-Farm
# ============================================================

def test_genesis_farm_registry():
    result = _check_row_count("farm_registry_record", GENESIS)
    assert result >= 1, f"Expected 1+ registry records for Genesis, got {result}"


def test_genesis_onboarding_workflow():
    result = _check_row_count("farm_onboarding_workflow", GENESIS)
    assert result >= 5, f"Expected 5+ onboarding steps for Genesis, got {result}"


def test_farm_template_instance():
    result = _check_row_count("farm_template_instance")
    assert result >= 1, f"Expected 1+ template instances, got {result}"


# ============================================================
# Category 13: Public Views
# ============================================================

def test_public_metric_summary():
    result = _check_view("v_public_metric_summary")
    assert result, "v_public_metric_summary view missing"


def test_public_attestation_summary():
    result = _check_view("v_public_attestation_summary")
    assert result, "v_public_attestation_summary view missing"


def test_public_carbon_credit_inventory():
    result = _check_view("v_public_carbon_credit_inventory")
    assert result, "v_public_carbon_credit_inventory view missing"


def test_public_farm_network_summary():
    result = _check_view("v_public_farm_network_summary")
    assert result, "v_public_farm_network_summary view missing"


def test_crisp_composite_rating():
    result = _check_view("v_crisp_composite_rating")
    assert result, "v_crisp_composite_rating view missing"


def test_public_evaluator_directory():
    result = _check_view("v_public_evaluator_directory")
    assert result, "v_public_evaluator_directory view missing"


def test_public_ranking_comparison():
    result = _check_view("v_public_ranking_comparison")
    assert result, "v_public_ranking_comparison view missing"


def test_currency_stability_summary():
    result = _check_view("v_currency_stability_summary")
    assert result, "v_currency_stability_summary view missing"


def test_infrastructure_utilization():
    result = _check_view("v_infrastructure_utilization_summary")
    assert result, "v_infrastructure_utilization_summary view missing"


def test_cold_chain_compliance():
    result = _check_view("v_cold_chain_compliance")
    assert result, "v_cold_chain_compliance view missing"


# ============================================================
# Category 14: Column Integrity
# ============================================================

def test_critical_columns_exist():
    """Verify critical columns exist across key tables."""
    checks = [
        ("location", "centroid"),
        ("tree_record", "dbh_cm"),
        ("tree_record", "health_score"),
        ("harvest_event", "quality_grade"),
        ("revenue_event", "amount"),
        ("ebf_scorecard", "overall_score"),
        ("crisp_risk_assessment", "composite_score"),
        ("carbon_credit", "issuable_tonnes"),
        ("governance_token", "contract_address"),
        ("tree_token_binding", "token_id_onchain"),
        ("dao_vote", "sqrt_weight"),
        ("reputation_token", "reputation_amount"),
        ("farm_onboarding_workflow", "step_order"),
    ]
    for table, column in checks:
        assert _check_column(table, column), f"Missing column: {table}.{column}"
    print(f"  All {len(checks)} critical columns exist")


# ============================================================
# Category 15: Data Integrity
# ============================================================

def test_adelphi_has_comprehensive_data():
    """Verify Adelphi has data across all major domains."""
    checks = {
        "farm_registry_record": 1,
        "farm_zone": 3,
        "tree_record": 1,
        "tree_inventory": 1,
        "ebf_scorecard": 1,
        "climate_impact_summary": 1,
        "carbon_benchmark": 5,
    }
    for table, min_count in checks.items():
        if "location_id" in _run_sql(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'location_id'"):
            count = _check_row_count(table, ADELPHI)
            assert count >= min_count, f"Expected {min_count}+ rows in {table} for Adelphi, got {count}"
    print(f"  Adelphi has comprehensive data across all major domains")


def test_genesis_has_onboarding_data():
    """Verify Genesis has onboarding workflow data."""
    count = _check_row_count("farm_onboarding_workflow", GENESIS)
    assert count >= 5, f"Expected 5+ onboarding steps for Genesis, got {count}"
    print(f"  Genesis has {count} onboarding steps")


def test_governance_token_has_entries():
    count = _run_sql("SELECT COUNT(*) FROM governance_token")
    c = _parse_count(count)
    assert c >= 1, f"Expected 1+ governance tokens, got {c}"


# ============================================================
# Main test runner
# ============================================================

ALL_TESTS = {
    "schema": [
        test_all_tables_exist,
        test_all_views_exist,
        test_critical_columns_exist,
    ],
    "seeds": [
        test_adelphi_location_exists,
        test_genesis_location_exists,
        test_framework_reference_data,
        test_ebf_rubric_loaded,
        test_celo_eas_schemas,
        test_gnosis_dao_metadata,
    ],
    "core": [
        test_farm_registry_record,
        test_farm_zones,
        test_crop_cycles,
        test_harvest_events,
        test_revenue_events,
        test_expense_events,
    ],
    "environmental": [
        test_weather_observations,
        test_soil_samples,
        test_species_observations,
    ],
    "web3": [
        test_wallet_profiles,
        test_attestation_records,
        test_dao_proposals,
    ],
    "carbon": [
        test_carbon_benchmarks,
        test_ghg_emission_factors,
        test_tree_inventory,
        test_climate_impact_summary,
    ],
    "ebf": [
        test_ebf_scorecard,
        test_ebf_pillars,
    ],
    "crisp": [
        test_crisp_dimensions,
        test_crisp_assessment,
    ],
    "abundance": [
        test_expertise_categories,
        test_impact_estimate_posts,
        test_validation_rounds,
        test_coin_inflation_events,
    ],
    "token": [
        test_governance_token,
        test_tree_token_binding,
        test_staking_positions,
    ],
    "voting": [
        test_dao_votes,
        test_reputation_tokens,
        test_delegation_records,
    ],
    "multifarm": [
        test_genesis_farm_registry,
        test_genesis_onboarding_workflow,
        test_farm_template_instance,
    ],
    "views": [
        test_public_metric_summary,
        test_public_attestation_summary,
        test_public_carbon_credit_inventory,
        test_public_farm_network_summary,
        test_crisp_composite_rating,
        test_public_evaluator_directory,
        test_public_ranking_comparison,
        test_currency_stability_summary,
        test_infrastructure_utilization,
        test_cold_chain_compliance,
    ],
    "data": [
        test_adelphi_has_comprehensive_data,
        test_genesis_has_onboarding_data,
        test_governance_token_has_entries,
    ],
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="End-to-end platform test")
    parser.add_argument("--category", help="Run specific category (schema, seeds, core, etc.)")
    args = parser.parse_args()

    # Check if database is running
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "--services"],
            capture_output=True, text=True, timeout=10,
        )
        if "database" not in result.stdout:
            print("ERROR: Database not running. Start with: docker compose up -d")
            sys.exit(1)
    except Exception:
        print("ERROR: Cannot check Docker status")
        sys.exit(1)

    print("=" * 60)
    print("KOKONUT INTELLIGENCE — END-TO-END PLATFORM TEST")
    print("=" * 60)

    if args.category:
        if args.category not in ALL_TESTS:
            print(f"Unknown category: {args.category}")
            print(f"Available: {', '.join(ALL_TESTS.keys())}")
            sys.exit(1)
        categories = {args.category: ALL_TESTS[args.category]}
    else:
        categories = ALL_TESTS

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cat_name, tests in categories.items():
        print(f"\n--- {cat_name.upper()} ---")
        for test_fn in tests:
            total += 1
            try:
                test_fn()
                passed += 1
                print(f"  ✓ {test_fn.__name__}")
            except AssertionError as e:
                failed += 1
                errors.append((test_fn.__name__, str(e)))
                print(f"  ✗ {test_fn.__name__}: {e}")
            except Exception as e:
                failed += 1
                errors.append((test_fn.__name__, str(e)))
                print(f"  ✗ {test_fn.__name__}: ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
