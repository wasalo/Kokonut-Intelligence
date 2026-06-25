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
    UNION ALL SELECT 'adelphi canonical location', EXISTS (
        SELECT 1 FROM location
        WHERE id = '{PILOT_LOCATION_ID}'
          AND slug = 'kokonut-adelphi'
          AND name = 'Kokonut Adelphi'
          AND country = 'Dominican Republic'
          AND region = 'Monte Plata'
    )
    UNION ALL SELECT 'adelphi registry record', EXISTS (
        SELECT 1 FROM farm_registry_record
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND registry_slug = 'kokonut-adelphi'
          AND land_size_m2 = 15725.0000
          AND public_goods_allocation_pct = 10.000
          AND status = 'published'
    ) AND NOT EXISTS (
        SELECT 1 FROM farm_registry_record
        WHERE registry_slug = 'kokonut-demo-farm-kisumu'
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
    UNION ALL SELECT 'public view filters registry', NOT EXISTS (
        SELECT 1 FROM v_public_farm_summary v
        WHERE NOT EXISTS (
            SELECT 1 FROM farm_registry_record fr
            WHERE fr.location_id = v.location_id
              AND fr.status IN ('verified', 'published')
        )
    )
    UNION ALL SELECT 'celo eas schemas current',
        (SELECT count(*) FROM attestation_schema
         WHERE chain = 'celo'
           AND active = TRUE
           AND resolver_address = '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad'
           AND schema_uid IN (
             '0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54',
             '0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe',
             '0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b',
             '0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff',
             '0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5'
           )) = 5
    UNION ALL SELECT 'gnosis dao metadata', EXISTS (
        SELECT 1 FROM protocol
        WHERE slug = 'kokonut-treasury'
          AND chain = 'gnosis'
          AND contract_address = '0xeb55b75328a8dffd45bbf34b7e7efc431a179085'
    ) AND (SELECT count(*) FROM wallet_profile WHERE chain = 'gnosis' AND owner_type = 'dao') >= 4
      AND NOT EXISTS (
        SELECT 1 FROM governance_event
        WHERE proposal_id IN ('P001', 'P002', 'P003')
          AND chain <> 'gnosis'
    )
    UNION ALL SELECT 'framework reference data',
        (SELECT count(*) FROM sdg WHERE is_active = TRUE AND COALESCE(TRIM(name), '') <> '') >= 17
        AND (SELECT count(*) FROM form_of_capital WHERE is_active = TRUE AND COALESCE(TRIM(name), '') <> '') >= 8
        AND (SELECT count(*) FROM impact_framework WHERE status = 'active' AND COALESCE(TRIM(name), '') <> '') >= 7
        AND (SELECT count(*) FROM regeneration_principle WHERE status = 'active') >= 5
    UNION ALL SELECT 'adelphi framework mappings',
        (SELECT count(*) FROM farm_impact_mapping WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 10
        AND (SELECT count(*) FROM farm_zone WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'active') >= 3
        AND (SELECT count(*) FROM farm_practice_event WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 5
    UNION ALL SELECT 'colony guild records',
        EXISTS (SELECT 1 FROM colony_instance WHERE colony_key = 'kokonut-guilds')
        AND (SELECT count(*) FROM kokonut_guild WHERE status = 'active') >= 6
        AND (SELECT count(*) FROM guild_contribution WHERE review_status = 'published') >= 3
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
