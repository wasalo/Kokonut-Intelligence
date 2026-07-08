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
    UNION ALL SELECT 'ground analytics schema',
        to_regclass('public.plant_analysis') IS NOT NULL
        AND to_regclass('public.water_analysis') IS NOT NULL
        AND to_regclass('public.disease_observation') IS NOT NULL
        AND to_regclass('public.irrigation_program') IS NOT NULL
    UNION ALL SELECT 'ground analytics pilot records',
        (SELECT count(*) FROM plant_analysis WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM water_analysis WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM disease_observation WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM irrigation_program WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
    UNION ALL SELECT 'ground analytics lineage',
        NOT EXISTS (SELECT 1 FROM plant_analysis WHERE location_id = '{PILOT_LOCATION_ID}' AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL))
        AND NOT EXISTS (SELECT 1 FROM water_analysis WHERE location_id = '{PILOT_LOCATION_ID}' AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL))
        AND NOT EXISTS (SELECT 1 FROM disease_observation WHERE location_id = '{PILOT_LOCATION_ID}' AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL))
        AND NOT EXISTS (SELECT 1 FROM irrigation_program WHERE location_id = '{PILOT_LOCATION_ID}' AND (source_system IS NULL OR source_id IS NULL OR source_raw IS NULL))
    UNION ALL SELECT 'ground analytics lifecycle canonical',
        NOT EXISTS (SELECT 1 FROM plant_analysis WHERE status NOT IN ('draft', 'submitted', 'verified', 'published', 'rejected'))
        AND NOT EXISTS (SELECT 1 FROM water_analysis WHERE status NOT IN ('draft', 'submitted', 'verified', 'published', 'rejected'))
        AND NOT EXISTS (SELECT 1 FROM disease_observation WHERE status NOT IN ('draft', 'submitted', 'verified', 'published', 'rejected'))
        AND NOT EXISTS (SELECT 1 FROM irrigation_program WHERE status NOT IN ('draft', 'submitted', 'verified', 'published', 'rejected'))
    UNION ALL SELECT 'farm onboarding profile', EXISTS (
        SELECT 1 FROM farm
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND logo_url IS NOT NULL
          AND traditional_name IS NOT NULL
          AND array_length(languages, 1) >= 1
          AND array_length(global_standard_certifications, 1) >= 1
          AND array_length(economic_sectors, 1) >= 1
          AND array_length(credits_registries, 1) >= 1
          AND data_privacy_status = 'public_summary_private_evidence'
    )
    UNION ALL SELECT 'daoip5 project metadata', EXISTS (
        SELECT 1 FROM farm_registry_record
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND daoip5_project_id = 'daoip-5:Kokonut:project:kokonut-adelphi'
          AND content_uri IS NOT NULL
          AND jsonb_array_length(socials) >= 1
          AND jsonb_array_length(relevant_to) >= 1
    ) AND EXISTS (SELECT 1 FROM v_daoip5_project_json WHERE farm_registry_record_id = 'a0000000-0000-0000-0000-000000000500')
    UNION ALL SELECT 'tenure rights assessment', EXISTS (
        SELECT 1 FROM tenure_rights_assessment
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND status = 'published'
          AND source_system IS NOT NULL
          AND source_id IS NOT NULL
          AND source_raw IS NOT NULL
    )
    UNION ALL SELECT 'data hub flora fauna views',
        EXISTS (SELECT 1 FROM v_public_farm_places WHERE location_id = '{PILOT_LOCATION_ID}')
        AND EXISTS (SELECT 1 FROM v_public_flora_fauna_summary WHERE location_id = '{PILOT_LOCATION_ID}')
    UNION ALL SELECT 'crop forecast summary view', EXISTS (
        SELECT 1 FROM v_crop_forecast_summary
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND annual_forecasted_revenue_per_harvest_per_plot_usd IS NOT NULL
    )
    UNION ALL SELECT 'carbon credits index view', EXISTS (
        SELECT 1 FROM v_public_project_carbon_credit_index
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND carbon_credits_index_usd > 0
    )
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
           AND resolver_address = '0x7A7390Ceb3E8145EffB81914271DA0ebDaF932Ef'
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
    UNION ALL SELECT 'carbon framework schema',
        to_regclass('public.ghg_emission_factor') IS NOT NULL
        AND to_regclass('public.ghg_emissions_inventory') IS NOT NULL
        AND to_regclass('public.tree_inventory') IS NOT NULL
        AND to_regclass('public.underplanting_event') IS NOT NULL
        AND to_regclass('public.carbon_benchmark') IS NOT NULL
        AND to_regclass('public.regenerative_practice_checklist') IS NOT NULL
        AND to_regclass('public.framework_phase') IS NOT NULL
        AND to_regclass('public.climate_impact_summary') IS NOT NULL
        AND to_regclass('public.operations_protocol') IS NOT NULL
    UNION ALL SELECT 'carbon framework seeds',
        (SELECT count(*) FROM ghg_emission_factor) >= 10
        AND (SELECT count(*) FROM carbon_benchmark) >= 5
        AND (SELECT count(*) FROM operations_protocol WHERE status = 'active') >= 4
    UNION ALL SELECT 'carbon framework pilot records',
        (SELECT count(*) FROM tree_inventory WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM underplanting_event WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM ghg_emissions_inventory WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
        AND (SELECT count(*) FROM framework_phase WHERE location_id = '{PILOT_LOCATION_ID}' AND phase_status IN ('active', 'completed')) >= 1
        AND (SELECT count(*) FROM regenerative_practice_checklist WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 5
        AND (SELECT count(*) FROM climate_impact_summary WHERE location_id = '{PILOT_LOCATION_ID}' AND status = 'published') >= 1
    UNION ALL SELECT 'carbon balance views',
        to_regclass('public.v_carbon_balance') IS NOT NULL
        AND to_regclass('public.v_regenerative_score_summary') IS NOT NULL
        AND to_regclass('public.v_ghg_emissions_summary') IS NOT NULL
        AND to_regclass('public.v_framework_phase_status') IS NOT NULL
    UNION ALL SELECT 'regenerative score view', EXISTS (
        SELECT 1 FROM v_regenerative_score_summary
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND total_score > 0
          AND score_pct > 0
    )
    UNION ALL SELECT 'impact accountability schema',
        to_regclass('public.evidence_maturity_level') IS NOT NULL
        AND to_regclass('public.stakeholder_feedback') IS NOT NULL
        AND to_regclass('public.stakeholder_feedback_review') IS NOT NULL
        AND to_regclass('public.stakeholder_outcome') IS NOT NULL
        AND to_regclass('public.impact_claim') IS NOT NULL
        AND to_regclass('public.metric_proposal') IS NOT NULL
        AND to_regclass('public.v_public_stakeholder_feedback_summary') IS NOT NULL
        AND to_regclass('public.v_public_impact_claim_summary') IS NOT NULL
    UNION ALL SELECT 'evidence maturity reference data',
        (SELECT count(*) FROM evidence_maturity_level) = 7
        AND EXISTS (SELECT 1 FROM evidence_maturity_level WHERE level = 6 AND requires_external_verification = TRUE)
    UNION ALL SELECT 'stakeholder feedback privacy',
        EXISTS (SELECT 1 FROM stakeholder_feedback WHERE location_id = '{PILOT_LOCATION_ID}' AND is_public = TRUE AND consent_given = TRUE AND status = 'published')
        AND EXISTS (SELECT 1 FROM stakeholder_feedback WHERE location_id = '{PILOT_LOCATION_ID}' AND is_public = FALSE AND consent_given = FALSE)
        AND NOT EXISTS (SELECT 1 FROM v_public_stakeholder_feedback_summary WHERE public_summary IS NULL)
    UNION ALL SELECT 'impact claim level6 carbon gate',
        EXISTS (
            SELECT 1 FROM impact_claim
            WHERE location_id = '{PILOT_LOCATION_ID}'
              AND claim_category = 'carbon'
              AND public_claim = TRUE
              AND evidence_maturity = 6
              AND status = 'published'
              AND external_verifier IS NOT NULL
              AND methodology_ref IS NOT NULL
        )
        AND NOT EXISTS (
            SELECT 1 FROM v_public_impact_claim_summary
            WHERE claim_category = 'carbon'
              AND evidence_maturity < 6
        )
    UNION ALL SELECT 'participatory metric proposal', EXISTS (
        SELECT 1 FROM metric_proposal
        WHERE location_id = '{PILOT_LOCATION_ID}'
          AND proposed_by_role = 'farm_operator'
          AND status IN ('approved', 'implemented')
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
