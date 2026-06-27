"""DB-backed EBF integration checks.

These tests run only when the Compose database service is available.
"""

from __future__ import annotations

import subprocess


def database_running() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "--services"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return result.returncode == 0 and "database" in result.stdout.splitlines()


def psql_scalar(sql: str) -> str:
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "database",
            "psql", "-v", "ON_ERROR_STOP=1", "-U", "kokonut", "-d", "kokonut_intelligence", "-Atc", sql,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def test_db_has_ebf_score_impact_claim_link() -> None:
    if not database_running():
        print("  ⚠ Database service not running — skipping EBF DB integration")
        return
    exists = psql_scalar(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'ebf_score' AND column_name = 'impact_claim_id');"
    )
    assert exists == "t"


def test_public_ebf_views_require_verified_carbon_impact_claim() -> None:
    if not database_running():
        print("  ⚠ Database service not running — skipping EBF DB integration")
        return
    viewdef = psql_scalar("SELECT pg_get_viewdef('v_public_ebf_scorecard'::regclass, true);")
    assert "third_party_verified_claim" in viewdef
    assert "external_verifier" in viewdef
    assert "methodology_ref" in viewdef
    assert "impact_claim" in viewdef


if __name__ == "__main__":
    test_db_has_ebf_score_impact_claim_link()
    test_public_ebf_views_require_verified_carbon_impact_claim()
