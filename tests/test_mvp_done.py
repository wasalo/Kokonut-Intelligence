"""MVP definition-of-done verifier for a seeded local pilot database."""

from __future__ import annotations

import subprocess
import sys


PILOT_LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


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


def run_sql(sql: str) -> list[tuple[str, bool]]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "database",
            "psql",
            "-U",
            "kokonut",
            "-d",
            "kokonut_intelligence",
            "-At",
            "-F",
            "|",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "MVP SQL verifier failed")

    checks: list[tuple[str, bool]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, ok = line.split("|", 1)
        checks.append((name, ok == "t"))
    return checks


def mvp_checks() -> list[tuple[str, bool]]:
    sql = f"""
WITH checks(name, ok) AS (
    SELECT 'location baselines', EXISTS (
        SELECT 1 FROM location
        WHERE id = '{PILOT_LOCATION_ID}'
          AND baseline_revenue IS NOT NULL
          AND baseline_asset_value IS NOT NULL
          AND baseline_cash_flow IS NOT NULL
    )
    UNION ALL SELECT 'core operational records',
        (SELECT count(*) FROM farm WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM plot p JOIN farm f ON f.id = p.farm_id WHERE f.location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM crop_cycle WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM farm_activity WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM expense_event WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM harvest_event WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM sales_event WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
    UNION ALL SELECT 'expense lineage', NOT EXISTS (
        SELECT 1 FROM expense_event
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL)
    )
    UNION ALL SELECT 'harvest lineage', NOT EXISTS (
        SELECT 1 FROM harvest_event
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL)
    )
    UNION ALL SELECT 'noi snapshots', (SELECT count(*) FROM noi_snapshot WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
    UNION ALL SELECT 'metric values verified', (SELECT count(*) FROM metric_value WHERE location_id = '{PILOT_LOCATION_ID}' AND verified = TRUE) >= 1
    UNION ALL SELECT 'environmental baselines', (SELECT count(*) FROM environmental_baseline WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
    UNION ALL SELECT 'web3 linked usage', (SELECT count(*) FROM digital_lego_usage WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
    UNION ALL SELECT 'forecast outputs',
        (SELECT count(*) FROM forecast_scenario WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
        AND (SELECT count(*) FROM forecast_output WHERE location_id = '{PILOT_LOCATION_ID}') >= 1
    UNION ALL SELECT 'published dashboard datasets', (SELECT count(*) FROM dashboard_dataset WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
    UNION ALL SELECT 'public farm view', EXISTS (SELECT 1 FROM v_public_farm_summary WHERE location_id = '{PILOT_LOCATION_ID}')
    UNION ALL SELECT 'public metric view', EXISTS (SELECT 1 FROM v_public_metric_summary WHERE location_id = '{PILOT_LOCATION_ID}')
    UNION ALL SELECT 'public attestation view', EXISTS (SELECT 1 FROM v_public_attestation_summary WHERE location_id = '{PILOT_LOCATION_ID}')
    UNION ALL SELECT 'claim lifecycle canonical', NOT EXISTS (
        SELECT 1 FROM mrv_claim
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND status NOT IN ('draft', 'submitted', 'verified', 'published', 'rejected')
    )
    UNION ALL SELECT 'attestation ready record',
        EXISTS (SELECT 1 FROM mrv_event WHERE location_id = '{PILOT_LOCATION_ID}' AND status IN ('verified', 'published') AND payload_hash IS NOT NULL)
        AND EXISTS (SELECT 1 FROM attestation_request WHERE status IN ('verified', 'published') AND execution_status IN ('pending', 'submitted', 'confirmed'))
    UNION ALL SELECT 'schema and metric versions',
        (SELECT count(*) FROM schema_version) >= 1
        AND (SELECT count(*) FROM metric_definition WHERE version IS NOT NULL) >= 1
        AND (SELECT count(*) FROM metric_version) >= 1
    UNION ALL SELECT 'agent summary permissions',
        EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Agent Read-Only')
        AND EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Agent Write')
        AND EXISTS (
            SELECT 1 FROM directus_permissions
            WHERE collection = 'ai_summary'
              AND action = 'create'
              AND policy = 'b1000000-0000-0000-0000-000000000007'
        )
)
SELECT name, ok FROM checks ORDER BY name;
"""
    return run_sql(sql)


def test_mvp_done() -> list[tuple[str, bool]]:
    if not database_running():
        print("  ⚠ Database service not running — skipping MVP verifier")
        return []

    checks = mvp_checks()
    for name, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    return checks


if __name__ == "__main__":
    print("=== Kokonut MVP Definition Of Done ===")
    results = test_mvp_done()
    failures = [name for name, ok in results if not ok]
    if failures:
        print("\nFailed checks:")
        for name in failures:
            print(f"  - {name}")
        sys.exit(1)
    print("\nMVP checks passed ✓")
