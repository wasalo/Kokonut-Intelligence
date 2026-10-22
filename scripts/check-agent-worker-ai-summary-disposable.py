#!/usr/bin/env python3
"""Replay and check signed-worker AI-summary drafts on disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/check-ai-summary-review-disposable.py"
WORKER_FIXTURE = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
AI_SUMMARY_FIXTURE = ROOT / "tests/fixtures/agent_worker_ai_summary_disposable.sql"
MIGRATIONS = [
    ROOT / "schemas/postgres/405_signed_worker_tenant_context.sql",
    ROOT / "schemas/postgres/419_private_worker_context_functions.sql",
    ROOT / "schemas/postgres/521_location_scoped_ai_summary_review.sql",
    ROOT / "schemas/postgres/522_authenticated_ai_summary_drafts.sql",
    ROOT / "schemas/postgres/523_ai_summary_source_references.sql",
    ROOT / "schemas/postgres/524_ai_summary_global_source_references.sql",
    ROOT / "schemas/postgres/529_signed_agent_ai_summary_drafts.sql",
    ROOT / "schemas/postgres/530_signed_agent_ai_summary_source_references.sql",
    ROOT / "schemas/postgres/531_capital_efficiency_synthesis_source_references.sql",
    ROOT / "schemas/postgres/532_registered_agent_source_reference_views.sql",
    ROOT / "schemas/postgres/533_regenerator_synthesis_source_references.sql",
    ROOT / "schemas/postgres/534_public_synthesis_source_reference_views.sql",
    ROOT / "schemas/postgres/535_consent_safe_wellbeing_feedback_source_views.sql",
    ROOT / "schemas/postgres/536_location_scoped_kokonut_commons_source_views.sql",
    ROOT / "schemas/postgres/537_registered_worker_summary_types.sql",
    ROOT / "schemas/postgres/539_agent_worker_structured_result_replay.sql",
]
OUTPUT = ROOT / "docs/refactor/builds/2026-10-21-recovery/cap-038-worker-structured-result-replay-disposable.json"
IMAGE = "postgis/postgis:16-3.4"
WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
REQUEST_ID = "d0000000-0000-4000-8000-000000000901"
RAW_CREDENTIAL = "synthetic-agent-summary-worker-credential-2026-10-21"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
ADDITIONAL_SOURCE_TABLES = [
    "time_liberation_observation",
    "capital_alignment_assessment",
    "governance_inclusion_observation",
    "land_stewardship_commitment",
    "gnh_alignment_assessment",
    "cultural_preservation_plan",
    "renewable_energy_plan",
    "vulnerable_group_access_plan",
    "foundational_wellbeing_observation",
    "financial_sustainability_plan",
    "risk_mitigation_register",
    "scaling_roadmap_milestone",
    "farm_launch_unit_economics",
    "adoption_barrier_assessment",
    "perpetual_value_stress_test",
]
ADDITIONAL_SOURCE_VIEWS = {
    "time_liberation_observation": "v_public_time_liberation_summary",
    "capital_alignment_assessment": "v_public_capital_alignment_summary",
    "governance_inclusion_observation": "v_public_governance_inclusion_summary",
    "land_stewardship_commitment": "v_public_land_stewardship_summary",
    "gnh_alignment_assessment": "v_public_gnh_alignment_summary",
    "cultural_preservation_plan": "v_public_cultural_preservation_summary",
    "renewable_energy_plan": "v_public_renewable_energy_summary",
    "vulnerable_group_access_plan": "v_public_vulnerable_access_summary",
    "foundational_wellbeing_observation": "v_public_foundational_wellbeing_summary",
    "financial_sustainability_plan": "v_public_financial_sustainability_summary",
    "risk_mitigation_register": "v_public_risk_mitigation_summary",
    "scaling_roadmap_milestone": "v_public_scaling_roadmap_summary",
    "farm_launch_unit_economics": "v_public_farm_launch_unit_economics",
    "adoption_barrier_assessment": "v_public_adoption_barrier_assessment",
    "perpetual_value_stress_test": "v_public_perpetual_value_stress_test",
}
CONSENT_SAFE_SOURCE_VIEWS = {
    "cultural_context_record": "v_public_cultural_context_summary",
    "wellbeing_metric_observation": "v_public_wellbeing_metric_summary",
    "participatory_action_record": "v_public_participatory_governance_summary",
    "stakeholder_feedback": "v_public_stakeholder_feedback_summary",
}
KOKONUT_COMMONS_SOURCE_VIEWS = {
    "anti_capture_governance_policy": "v_public_anti_capture_governance_policy",
    "commons_redistribution_policy": "v_public_commons_redistribution_policy",
    "algorithmic_redistribution_mechanism": "v_public_algorithmic_redistribution_mechanism",
}


def _load_base():
    spec = importlib.util.spec_from_file_location("ai_summary_review_disposable", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the disposable PostgreSQL helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _worker_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{WORKER_ID}', 'agent-summary-draft');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{WORKER_ID}', '{CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'draft', 'synthetic acceptance fixture'
    );

    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE created RECORD;
            lineage_probe RECORD;
            replayed RECORD;
            looked_up RECORD;
            denied BOOLEAN;
            manifest JSONB;
            bio_manifest JSONB;
            regenerator_manifest JSONB;
            source_result JSONB;
            bio_probe RECORD;
            regenerator_probe RECORD;
            regenerator_bad_probe RECORD;
            test_summary_type TEXT;
            test_summary_counter INTEGER := 950;
    BEGIN
        SELECT * INTO created
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'holistic_wellbeing', 'Worker-produced synthetic draft.',
              ARRAY['harvest_event', 'crop_cycle', 'crop', 'expense_category',
                    'capital_efficiency_scenario', 'regenerative_efficiency_observation',
                    'governance_throughput_observation', 'capital_provider_utility_scenario'],
              'agent-v2', '{REQUEST_ID}'
          );
        IF created.summary_id IS NULL OR created.replayed
           OR created.resulting_status <> 'draft' THEN
            RAISE EXCEPTION 'first worker request did not create one draft';
        END IF;

        FOREACH test_summary_type IN ARRAY ARRAY[
            'operations', 'financial', 'environmental', 'combined',
            'bio_factory', 'capital_efficiency', 'commons_liberation',
            'stakeholder_feedback', 'gnh_alignment', 'holistic_wellbeing',
            'kokonut_commons', 'open_source_capitalist',
            'financial_resilience', 'regenerative_outcomes'
        ] LOOP
            test_summary_counter := test_summary_counter + 1;
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', test_summary_type,
                'Registered summary acceptance ' || test_summary_type,
                ARRAY['harvest_event'], 'agent-v1',
                ('d0000000-0000-4000-8000-' || lpad(test_summary_counter::TEXT, 12, '0'))::UUID
            );
        END LOOP;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', 'unregistered_agent', 'Unregistered summary type.',
                ARRAY['harvest_event'], 'agent-v1', 'd0000000-0000-4000-8000-000000000906'
            );
        EXCEPTION WHEN check_violation THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'unregistered worker summary type was accepted'; END IF;
        SELECT * INTO looked_up
          FROM kokonut_security.get_location_ai_summary_worker_draft_request(
              '{LOCATION_ID}', 'unregistered_agent',
              'd0000000-0000-4000-8000-000000000906'
          );
        IF FOUND THEN
            RAISE EXCEPTION 'rejected summary type left a worker receipt';
        END IF;

        manifest := jsonb_build_object(
            'harvest_event', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000001'),
                'row_count', 1, 'truncated', false
            ),
            'crop_cycle', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000102'),
                'row_count', 1, 'truncated', false
            ),
            'crop', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000101'),
                'row_count', 1, 'truncated', false
            ),
            'expense_category', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000104'),
                'row_count', 1, 'truncated', false
            ),
            'capital_efficiency_scenario', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000201'),
                'row_count', 1, 'truncated', false
            ),
            'regenerative_efficiency_observation', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000211'),
                'row_count', 1, 'truncated', false
            ),
            'governance_throughput_observation', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000221'),
                'row_count', 1, 'truncated', false
            ),
            'capital_provider_utility_scenario', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000231'),
                'row_count', 1, 'truncated', false
            )
        );
        source_result := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', created.summary_id, '{REQUEST_ID}', manifest
        );
        IF source_result IS DISTINCT FROM manifest THEN
            RAISE EXCEPTION 'worker source manifest did not preserve validated references';
        END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', created.summary_id, '{REQUEST_ID}'
        );
        IF source_result IS DISTINCT FROM manifest THEN
            RAISE EXCEPTION 'exact worker source-reference read did not return attached rows';
        END IF;

        SELECT * INTO lineage_probe
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'capital_efficiency', 'Published-view lineage rejection fixture.',
              ARRAY['capital_efficiency_scenario'], 'agent-v2',
              'd0000000-0000-4000-8000-000000000911'
          );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', lineage_probe.summary_id, 'd0000000-0000-4000-8000-000000000911',
                '{{"capital_efficiency_scenario":{{"record_ids":["e0000000-0000-4000-8000-000000000202"],"row_count":1,"truncated":false}}}}'::jsonb
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'unpublished source row was accepted'; END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', lineage_probe.summary_id, 'd0000000-0000-4000-8000-000000000911'
        );
        IF source_result <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'rejected unpublished source left a partial manifest';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', lineage_probe.summary_id, 'd0000000-0000-4000-8000-000000000911',
                '{{"capital_efficiency_scenario":{{"record_ids":["e0000000-0000-4000-8000-000000000201"],"row_count":2,"truncated":true}}}}'::jsonb
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'inexact public-view row count was accepted'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', lineage_probe.summary_id, 'd0000000-0000-4000-8000-000000000911',
                '{{"capital_efficiency_scenario":{{"record_ids":["e0000000-0000-4000-8000-000000000203"],"row_count":1,"truncated":false}}}}'::jsonb
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'other-location public row was accepted'; END IF;

        SELECT * INTO bio_probe
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'bio_factory', 'Published bio-factory source references.',
              ARRAY['bio_factory_batch', 'bio_input_provenance', 'bio_recipe_library',
                    'bio_factory_quality_test'],
              'bio-factory-agent-v1', 'd0000000-0000-4000-8000-000000000912'
          );
        bio_manifest := jsonb_build_object(
            'bio_factory_batch', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000301'),
                'row_count', 1, 'truncated', false
            ),
            'bio_input_provenance', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000311'),
                'row_count', 1, 'truncated', false
            ),
            'bio_recipe_library', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000321'),
                'row_count', 1, 'truncated', false
            ),
            'bio_factory_quality_test', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000331'),
                'row_count', 1, 'truncated', false
            )
        );
        source_result := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', bio_probe.summary_id, 'd0000000-0000-4000-8000-000000000912',
            bio_manifest
        );
        IF source_result IS DISTINCT FROM bio_manifest THEN
            RAISE EXCEPTION 'registered bio-factory views did not preserve source references';
        END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', bio_probe.summary_id, 'd0000000-0000-4000-8000-000000000912'
        );
        IF source_result IS DISTINCT FROM bio_manifest THEN
            RAISE EXCEPTION 'bio-factory source references were not returned under exact scope';
        END IF;

        SELECT * INTO regenerator_probe
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'regenerative_outcomes', 'Published regenerative source references.',
              ARRAY['regenerative_outcome_summary', 'community_governance_mechanism',
                    'replication_readiness_assessment', 'adaptive_stewardship_review'],
              'regenerator-agent-v1', 'd0000000-0000-4000-8000-000000000913'
          );
        regenerator_manifest := jsonb_build_object(
            'regenerative_outcome_summary', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000401'),
                'row_count', 1, 'truncated', false
            ),
            'community_governance_mechanism', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000411'),
                'row_count', 1, 'truncated', false
            ),
            'replication_readiness_assessment', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000421'),
                'row_count', 1, 'truncated', false
            ),
            'adaptive_stewardship_review', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000431'),
                'row_count', 1, 'truncated', false
            )
        );
        source_result := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', regenerator_probe.summary_id, 'd0000000-0000-4000-8000-000000000913',
            regenerator_manifest
        );
        IF source_result IS DISTINCT FROM regenerator_manifest THEN
            RAISE EXCEPTION 'registered regenerator views did not preserve source references';
        END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', regenerator_probe.summary_id, 'd0000000-0000-4000-8000-000000000913'
        );
        IF source_result IS DISTINCT FROM regenerator_manifest THEN
            RAISE EXCEPTION 'regenerator source references were not returned under exact scope';
        END IF;
        SELECT * INTO regenerator_bad_probe
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'regenerative_outcomes', 'Cross-location rejection fixture.',
              ARRAY['regenerative_outcome_summary'], 'regenerator-agent-v1',
              'd0000000-0000-4000-8000-000000000914'
          );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', regenerator_bad_probe.summary_id, 'd0000000-0000-4000-8000-000000000914',
                '{{"regenerative_outcome_summary":{{"record_ids":["e0000000-0000-4000-8000-000000000403"],"row_count":1,"truncated":false}}}}'::jsonb
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'other-location regenerative source row was accepted'; END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', regenerator_bad_probe.summary_id, 'd0000000-0000-4000-8000-000000000914'
        );
        IF source_result <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'rejected regenerative attachment left a partial manifest';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.get_location_ai_summary_worker_source_references(
                '{LOCATION_ID}', created.summary_id,
                'd0000000-0000-4000-8000-000000000904'
            );
        EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker source read accepted a mismatched request receipt'; END IF;
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.get_location_ai_summary_worker_source_references(
                '{OTHER_LOCATION_ID}', created.summary_id, '{REQUEST_ID}'
            );
        EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker source read accepted a mismatched location'; END IF;

        SELECT * INTO replayed
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'holistic_wellbeing', 'Changed generated text is ignored on exact request retry.',
              ARRAY['harvest_event', 'crop_cycle', 'crop', 'expense_category',
                    'capital_efficiency_scenario', 'regenerative_efficiency_observation',
                    'governance_throughput_observation', 'capital_provider_utility_scenario'],
              'agent-v3', '{REQUEST_ID}'
          );
        IF replayed.summary_id IS DISTINCT FROM created.summary_id
           OR NOT replayed.replayed
           OR replayed.content IS DISTINCT FROM created.content THEN
            RAISE EXCEPTION 'exact request retry did not replay the original draft';
        END IF;

        SELECT * INTO looked_up
          FROM kokonut_security.get_location_ai_summary_worker_draft_request(
              '{LOCATION_ID}', 'holistic_wellbeing', '{REQUEST_ID}'
          );
        IF looked_up.summary_id IS DISTINCT FROM created.summary_id
           OR looked_up.content IS DISTINCT FROM created.content THEN
            RAISE EXCEPTION 'bounded retry lookup did not return the original draft';
        END IF;

        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', created.summary_id, '{REQUEST_ID}'
        );
        IF source_result IS DISTINCT FROM manifest THEN
            RAISE EXCEPTION 'source references were not stable across an exact retry';
        END IF;

        PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
            '{LOCATION_ID}', 'operations', 'Second synthetic draft for source-scope denial.',
            ARRAY['harvest_event'], 'agent-v2', 'd0000000-0000-4000-8000-000000000902'
        );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}',
                (SELECT summary_id FROM kokonut_security.get_location_ai_summary_worker_draft_request(
                    '{LOCATION_ID}', 'operations', 'd0000000-0000-4000-8000-000000000902'
                )),
                'd0000000-0000-4000-8000-000000000902',
                jsonb_build_object('harvest_event', jsonb_build_object(
                    'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000002'),
                    'row_count', 1, 'truncated', false
                ))
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'cross-location source reference was accepted'; END IF;
        source_result := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}',
            (SELECT summary_id FROM kokonut_security.get_location_ai_summary_worker_draft_request(
                '{LOCATION_ID}', 'operations', 'd0000000-0000-4000-8000-000000000902'
            )),
            'd0000000-0000-4000-8000-000000000902'
        );
        IF source_result <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'failed cross-location attachment left a partial manifest';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', 'operations', 'Conflicting intent.',
                ARRAY['harvest_event'], 'agent-v2', '{REQUEST_ID}'
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'request ID reuse for another intent was accepted'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{OTHER_LOCATION_ID}', 'holistic_wellbeing', 'Wrong location.',
                ARRAY['harvest_event'], 'agent-v2', 'd0000000-0000-4000-8000-000000000902'
            );
        EXCEPTION WHEN SQLSTATE '42501' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker grant crossed its location boundary'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft(
                '{LOCATION_ID}', 'holistic_wellbeing', 'Duplicate source metadata.',
                ARRAY['harvest_event', 'harvest_event'], 'agent-v2',
                'd0000000-0000-4000-8000-000000000903'
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'duplicate source metadata was accepted'; END IF;

        denied := FALSE;
        BEGIN
            PERFORM count(*) FROM public.ai_summary_agent_draft_request;
        EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker execution role can read private receipts directly'; END IF;
        IF has_table_privilege('kokonut_worker_execution',
                               'kokonut_security.ai_summary_source_manifest', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution',
                                  'kokonut_security.ai_summary_source_reference', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution', 'public.harvest_event', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution', 'public.capital_efficiency_scenario', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution', 'public.bio_factory_batch', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution', 'public.regenerative_outcome_summary', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution', 'kokonut_security.ai_summary_source_reference_view', 'SELECT') THEN
            RAISE EXCEPTION 'worker execution role has direct source or manifest table access';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    INSERT INTO public.agent_worker_ai_summary_test_result (summary_id)
    SELECT summary_id
      FROM public.ai_summary_agent_draft_request
     WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
    """


def _worker_result_create_acceptance() -> str:
    request_id = "d0000000-0000-4000-8000-000000009800"
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE created RECORD;
            expected JSONB := jsonb_build_object(
                'location_id', '{LOCATION_ID}',
                'synthesis', 'Structured result preserved across retries',
                'confidence', 0.875,
                'evidence', jsonb_build_array('source-a', 'source-b')
            );
    BEGIN
        SELECT * INTO STRICT created
          FROM kokonut_security.create_location_ai_summary_worker_draft_with_result(
              '{LOCATION_ID}', 'holistic_wellbeing',
              'Structured result preserved across retries',
              ARRAY['harvest_event'], 'agent-v2', '{request_id}', expected
          );
        IF created.replayed OR created.worker_result IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'first worker result was not stored with its draft';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _worker_result_retry_acceptance() -> str:
    request_id = "d0000000-0000-4000-8000-000000009800"
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE replayed RECORD;
            expected JSONB := jsonb_build_object(
                'location_id', '{LOCATION_ID}',
                'synthesis', 'Structured result preserved across retries',
                'confidence', 0.875,
                'evidence', jsonb_build_array('source-a', 'source-b')
            );
    BEGIN
        SELECT * INTO STRICT replayed
          FROM kokonut_security.create_location_ai_summary_worker_draft_with_result(
              '{LOCATION_ID}', 'holistic_wellbeing',
              'Changed content is ignored by an exact retry',
              ARRAY['harvest_event'], 'agent-v3', '{request_id}',
              jsonb_build_object('synthesis', 'Changed content is ignored by an exact retry')
          );
        IF NOT replayed.replayed OR replayed.worker_result IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'exact worker retry did not return the original structured result';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _worker_result_lookup_acceptance() -> str:
    request_id = "d0000000-0000-4000-8000-000000009800"
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE looked_up RECORD;
            legacy RECORD;
            denied BOOLEAN := FALSE;
            expected JSONB := jsonb_build_object(
                'location_id', '{LOCATION_ID}',
                'synthesis', 'Structured result preserved across retries',
                'confidence', 0.875,
                'evidence', jsonb_build_array('source-a', 'source-b')
            );
    BEGIN
        SELECT * INTO STRICT looked_up
          FROM kokonut_security.get_location_ai_summary_worker_result(
              '{LOCATION_ID}', 'holistic_wellbeing', '{request_id}'
          );
        IF looked_up.worker_result IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'worker result lookup did not return the original structured result';
        END IF;
        SELECT * INTO STRICT legacy
          FROM kokonut_security.get_location_ai_summary_worker_result(
              '{LOCATION_ID}', 'holistic_wellbeing', '{REQUEST_ID}'
          );
        IF legacy.content <> 'Worker-produced synthetic draft.'
           OR legacy.worker_result IS NOT NULL THEN
            RAISE EXCEPTION 'pre-result worker receipt did not retain the content-only fallback';
        END IF;
        BEGIN
            PERFORM count(*) FROM kokonut_security.ai_summary_agent_draft_result;
        EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker execution can read result receipts directly'; END IF;
        IF has_table_privilege('kokonut_runtime',
                'kokonut_security.ai_summary_agent_draft_result', 'SELECT')
           OR has_table_privilege('directus',
                'kokonut_security.ai_summary_agent_draft_result', 'SELECT')
           OR has_table_privilege('kokonut_worker_execution',
                'kokonut_security.ai_summary_agent_draft_result', 'INSERT')
           OR NOT has_function_privilege('kokonut_worker_execution',
                'kokonut_security.get_location_ai_summary_worker_result(uuid,text,uuid)', 'EXECUTE')
           OR NOT has_function_privilege('kokonut_worker_execution',
                'kokonut_security.create_location_ai_summary_worker_draft_with_result(uuid,text,text,text[],text,uuid,jsonb)', 'EXECUTE') THEN
            RAISE EXCEPTION 'worker result function and table privileges are not isolated';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _worker_result_validation_acceptance() -> str:
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE denied BOOLEAN := FALSE;
    BEGIN
        BEGIN
            PERFORM * FROM kokonut_security.create_location_ai_summary_worker_draft_with_result(
                '{LOCATION_ID}', 'holistic_wellbeing', 'Draft and result must agree',
                ARRAY['harvest_event'], 'agent-v1', 'd0000000-0000-4000-8000-000000009801',
                jsonb_build_object(
                    'content', 'Draft and result must agree',
                    'synthesis', 'Different output'
                )
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN
            RAISE EXCEPTION 'mismatched structured result was accepted';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    DO $$
    DECLARE draft_exists BOOLEAN;
            result_exists BOOLEAN;
    BEGIN
        SELECT EXISTS (
            SELECT 1 FROM public.ai_summary_agent_draft_request
             WHERE request_id = 'd0000000-0000-4000-8000-000000009801'
        ) INTO draft_exists;
        SELECT EXISTS (
            SELECT 1 FROM kokonut_security.ai_summary_agent_draft_result
             WHERE request_id = 'd0000000-0000-4000-8000-000000009801'
        ) INTO result_exists;
        IF draft_exists OR result_exists THEN
            RAISE EXCEPTION 'mismatched structured result left draft %, result %',
                draft_exists, result_exists;
        END IF;
    END;
    $$;
    """


def _expect_worker_result_lookup_sqlstate(
    base, docker: str, container: str, *, location_id: str, summary_type: str,
    request_id: str, sqlstate: str, label: str,
) -> None:
    sql = f"""\
    \\set VERBOSITY verbose
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    SELECT * FROM kokonut_security.get_location_ai_summary_worker_result(
        '{location_id}', '{summary_type}', '{request_id}'
    );
    COMMIT;
    """
    try:
        base.psql(docker, container, sql)
    except RuntimeError as exc:
        if f"ERROR:  {sqlstate}:" not in str(exc):
            raise RuntimeError(f"{label} failed with an unexpected database error") from exc
        return
    raise RuntimeError(f"{label} was accepted instead of failing with SQLSTATE {sqlstate}")


def _registered_synthesis_source_acceptance() -> str:
    groups = [
        ("commons_liberation", "commons-agent-v1", ADDITIONAL_SOURCE_TABLES[:4]),
        ("gnh_alignment", "gnh-agent-v1", ADDITIONAL_SOURCE_TABLES[4:9]),
        ("financial_resilience", "resilience-agent-v1", ADDITIONAL_SOURCE_TABLES[9:12]),
        ("open_source_capitalist", "open-source-capitalist-agent-v1", ADDITIONAL_SOURCE_TABLES[12:]),
    ]
    id_by_table = {
        table: f"e0000000-0000-4000-8000-{index:012d}"
        for index, table in enumerate(ADDITIONAL_SOURCE_TABLES, start=501)
    }
    statements = []
    for group_index, (summary_type, model_version, source_tables) in enumerate(groups, start=1):
        request_id = f"d0000000-0000-4000-8000-{920 + group_index:012d}"
        source_array = ", ".join(f"'{table}'" for table in source_tables)
        payload_entries = ", ".join(
            f"'{table}', jsonb_build_object('record_ids', jsonb_build_array('{id_by_table[table]}'), "
            "'row_count', 1, 'truncated', false)"
            for table in source_tables
        )
        statements.append(
            f"""
        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', '{summary_type}', 'Synthetic {summary_type} source references.',
              ARRAY[{source_array}], '{model_version}', '{request_id}'
          );
        payload := jsonb_build_object({payload_entries});
        attached := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', draft_record.summary_id, '{request_id}', payload
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION '{summary_type} source references did not match the registered views';
        END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id, '{request_id}'
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION '{summary_type} source references were not returned under exact scope';
        END IF;
"""
        )

    view_array = ", ".join(f"'{view}'" for view in ADDITIONAL_SOURCE_VIEWS.values())
    table_array = ", ".join(f"'{table}'" for table in ADDITIONAL_SOURCE_TABLES)
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE draft_record RECORD;
            payload JSONB;
            attached JSONB;
            object_name TEXT;
    BEGIN
        {''.join(statements)}
        FOREACH object_name IN ARRAY ARRAY[{view_array}] LOOP
            IF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'id', 'SELECT')
               OR NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'location_id', 'SELECT')
               OR has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'public_summary', 'SELECT') THEN
                RAISE EXCEPTION 'source-view drafter grant is not limited to identity and location columns';
            END IF;
        END LOOP;
        FOREACH object_name IN ARRAY ARRAY[{table_array}] LOOP
            IF has_table_privilege('kokonut_worker_execution',
                    format('public.%I', object_name), 'SELECT') THEN
                RAISE EXCEPTION 'worker execution has direct source table access to %', object_name;
            END IF;
        END LOOP;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _consent_safe_feedback_acceptance() -> str:
    source_ids = {
        "cultural_context_record": "e0000000-0000-4000-8000-000000000601",
        "wellbeing_metric_observation": "e0000000-0000-4000-8000-000000000602",
        "participatory_action_record": "e0000000-0000-4000-8000-000000000603",
        "stakeholder_feedback": "e0000000-0000-4000-8000-000000000604",
    }
    source_array = ", ".join(f"'{table}'" for table in CONSENT_SAFE_SOURCE_VIEWS)
    payload_entries = ", ".join(
        f"'{table}', jsonb_build_object('record_ids', jsonb_build_array('{source_ids[table]}'), "
        "'row_count', 1, 'truncated', false)"
        for table in CONSENT_SAFE_SOURCE_VIEWS
    )
    view_array = ", ".join(f"'{view}'" for view in CONSENT_SAFE_SOURCE_VIEWS.values())
    table_array = ", ".join(f"'{table}'" for table in CONSENT_SAFE_SOURCE_VIEWS)
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE draft_record RECORD;
            payload JSONB;
            attached JSONB;
            denied BOOLEAN;
            object_name TEXT;
    BEGIN
        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'holistic_wellbeing', 'Synthetic consent-safe wellbeing references.',
              ARRAY[{source_array}], 'wellbeing-agent-v1',
              'd0000000-0000-4000-8000-000000000931'
          );
        payload := jsonb_build_object({payload_entries});
        attached := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000931', payload
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION 'wellbeing source references did not match consent-safe views';
        END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000931'
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION 'wellbeing source references were not returned under exact scope';
        END IF;

        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'stakeholder_feedback', 'Synthetic public feedback references.',
              ARRAY['stakeholder_feedback'], 'feedback-agent-v1',
              'd0000000-0000-4000-8000-000000000932'
          );
        payload := jsonb_build_object(
            'stakeholder_feedback', jsonb_build_object(
                'record_ids', jsonb_build_array('{source_ids['stakeholder_feedback']}'),
                'row_count', 1, 'truncated', false
            )
        );
        attached := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000932', payload
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION 'feedback source references did not retain the consented public row';
        END IF;

        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'stakeholder_feedback', 'Private feedback rejection fixture.',
              ARRAY['stakeholder_feedback'], 'feedback-agent-v1',
              'd0000000-0000-4000-8000-000000000933'
          );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', draft_record.summary_id,
                'd0000000-0000-4000-8000-000000000933',
                '{{"stakeholder_feedback":{{"record_ids":["e0000000-0000-4000-8000-000000000605"],"row_count":1,"truncated":false}}}}'::jsonb
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'private/no-consent feedback row was accepted'; END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000933'
        );
        IF attached <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'rejected private feedback left a partial manifest';
        END IF;

        FOREACH object_name IN ARRAY ARRAY[{view_array}] LOOP
            IF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'id', 'SELECT')
               OR NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'location_id', 'SELECT')
               OR has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'public_summary', 'SELECT') THEN
                RAISE EXCEPTION 'consent-safe view grant exceeds ID and location columns';
            END IF;
        END LOOP;
        FOREACH object_name IN ARRAY ARRAY[{table_array}] LOOP
            IF has_table_privilege('kokonut_worker_execution',
                    format('public.%I', object_name), 'SELECT') THEN
                RAISE EXCEPTION 'worker execution has direct sensitive-source access to %', object_name;
            END IF;
        END LOOP;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _kokonut_commons_source_acceptance() -> str:
    source_ids = {
        "anti_capture_governance_policy": "e0000000-0000-4000-8000-000000000701",
        "commons_redistribution_policy": "e0000000-0000-4000-8000-000000000702",
        "algorithmic_redistribution_mechanism": "e0000000-0000-4000-8000-000000000703",
    }
    payload_entries = ", ".join(
        f"'{table}', jsonb_build_object('record_ids', jsonb_build_array('{source_ids[table]}'), "
        "'row_count', 1, 'truncated', false)"
        for table in KOKONUT_COMMONS_SOURCE_VIEWS
    )
    view_array = ", ".join(f"'{view}'" for view in KOKONUT_COMMONS_SOURCE_VIEWS.values())
    table_array = ", ".join(f"'{table}'" for table in KOKONUT_COMMONS_SOURCE_VIEWS)
    return f"""
    SET ROLE kokonut_agent_summary_draft_login;
    BEGIN;
    SET LOCAL ROLE kokonut_worker_execution;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'draft'
    );
    DO $$
    DECLARE draft_record RECORD;
            payload JSONB;
            attached JSONB;
            object_name TEXT;
    BEGIN
        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'kokonut_commons', 'Synthetic Kokonut Commons policies.',
              ARRAY['anti_capture_governance_policy', 'commons_redistribution_policy',
                    'federation_protocol', 'algorithmic_redistribution_mechanism',
                    'participatory_signal_experiment'], 'kokonut-commons-agent-v1',
              'd0000000-0000-4000-8000-000000000941'
          );
        payload := jsonb_build_object({payload_entries});
        attached := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000941', payload
        );
        IF attached IS DISTINCT FROM payload
           OR payload ? 'federation_protocol'
           OR payload ? 'participatory_signal_experiment' THEN
            RAISE EXCEPTION 'Kokonut Commons references included a global catalogue or lost local source rows';
        END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000941'
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION 'Kokonut Commons references were not returned under exact scope';
        END IF;
        IF payload -> 'commons_redistribution_policy' -> 'record_ids'
           ? 'e0000000-0000-4000-8000-000000000704' THEN
            RAISE EXCEPTION 'network-wide commons policy entered a farm manifest';
        END IF;
        FOREACH object_name IN ARRAY ARRAY[{view_array}] LOOP
            IF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'id', 'SELECT')
               OR NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'location_id', 'SELECT')
               OR has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'public_summary', 'SELECT') THEN
                RAISE EXCEPTION 'Kokonut Commons drafter grant exceeds ID and location columns';
            END IF;
        END LOOP;
        FOREACH object_name IN ARRAY ARRAY[{table_array}] LOOP
            IF has_table_privilege('kokonut_worker_execution',
                    format('public.%I', object_name), 'SELECT') THEN
                RAISE EXCEPTION 'worker execution has direct Kokonut Commons source access to %', object_name;
            END IF;
        END LOOP;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def _review_context_fixture() -> str:
    return r"""
    CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
    RETURNS TABLE(tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
        SELECT NULLIF(current_setting('kokonut.tenant_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.location_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID,
               NULLIF(current_setting('kokonut.actor_type', TRUE), '')::TEXT
    $$;
    """


def _review_acceptance() -> str:
    reviewer_id = "a0000000-0000-0000-0000-000000000902"
    return f"""
    SET ROLE kokonut_runtime;
    BEGIN;
    SELECT set_config('kokonut.tenant_id', '{TENANT_ID}', TRUE);
    SELECT set_config('kokonut.location_id', '{LOCATION_ID}', TRUE);
    SELECT set_config('kokonut.actor_id', '{reviewer_id}', TRUE);
    SELECT set_config('kokonut.actor_type', 'operator', TRUE);
    DO $$
    DECLARE queue_row RECORD;
            decision_row RECORD;
            worker_summary_id UUID;
            denied BOOLEAN;
    BEGIN
        SELECT summary_id INTO STRICT worker_summary_id
          FROM public.agent_worker_ai_summary_test_result;
        SELECT * INTO queue_row
          FROM kokonut_security.list_location_ai_summary_reviews('{LOCATION_ID}', 51, 0)
         WHERE summary_id = worker_summary_id;
        IF NOT FOUND OR NOT queue_row.review_ready
           OR 'creator_unattributed' = ANY(queue_row.blocked_reasons) THEN
            RAISE EXCEPTION 'worker-attributed draft was not reviewable';
        END IF;

        SELECT * INTO queue_row
          FROM kokonut_security.list_location_ai_summary_reviews_with_sources(
              '{LOCATION_ID}', 51, 0
          )
         WHERE summary_id = worker_summary_id;
        IF NOT FOUND
           OR queue_row.source_references -> 'harvest_event' -> 'record_ids'
              <> '["e0000000-0000-4000-8000-000000000001"]'::jsonb
           OR queue_row.source_references -> 'crop' -> 'record_ids'
              <> '["e0000000-0000-4000-8000-000000000101"]'::jsonb
           OR queue_row.source_references -> 'expense_category' -> 'record_ids'
              <> '["e0000000-0000-4000-8000-000000000104"]'::jsonb THEN
            RAISE EXCEPTION 'independent reviewer queue did not expose worker source references';
        END IF;

        SELECT * INTO queue_row
          FROM kokonut_security.list_location_ai_summary_reviews('{LOCATION_ID}', 51, 0)
         WHERE summary_id = 'c0000000-0000-4000-8000-000000000099';
        IF NOT FOUND OR queue_row.review_ready
           OR NOT ('creator_unattributed' = ANY(queue_row.blocked_reasons)) THEN
            RAISE EXCEPTION 'legacy unattributed draft was not blocked';
        END IF;

        SELECT * INTO decision_row
          FROM kokonut_security.decide_location_ai_summary_review(
              '{LOCATION_ID}', worker_summary_id, 'approve',
              'd0000000-0000-4000-8000-000000000904', 'approved_after_review'
          );
        IF decision_row.resulting_status <> 'verified' THEN
            RAISE EXCEPTION 'human review did not stop at verified';
        END IF;

        denied := FALSE;
        BEGIN
            PERFORM * FROM kokonut_security.decide_location_ai_summary_review(
                '{LOCATION_ID}', 'c0000000-0000-4000-8000-000000000099', 'approve',
                'd0000000-0000-4000-8000-000000000905', 'approved_after_review'
            );
        EXCEPTION WHEN SQLSTATE '55000' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'unattributed legacy draft was approved'; END IF;
    END;
    $$;
    COMMIT;

    RESET ROLE;
    DO $$
    DECLARE worker_summary_id UUID;
            denied BOOLEAN;
    BEGIN
        SELECT summary_id INTO STRICT worker_summary_id
          FROM public.agent_worker_ai_summary_test_result;
        IF NOT EXISTS (
            SELECT 1 FROM public.ai_summary
             WHERE id = worker_summary_id AND status = 'verified'
               AND reviewed_by = '{reviewer_id}' AND reviewed_at IS NOT NULL
               AND created_by IS NULL
               AND created_by_worker_id = '{WORKER_ID}'
        ) THEN RAISE EXCEPTION 'worker attribution or independent review was not persisted'; END IF;
        IF (SELECT count(*) FROM public.lifecycle_transition
             WHERE entity_id = worker_summary_id
               AND to_status = 'verified' AND actor_type = 'operator') <> 1 THEN
            RAISE EXCEPTION 'human lifecycle transition was not independently attributed';
        END IF;
        IF has_table_privilege('kokonut_worker_execution',
                               'public.ai_summary', 'INSERT')
           OR has_table_privilege('kokonut_agent_summary_draft_login',
                                  'public.ai_summary', 'INSERT')
           OR has_table_privilege('kokonut_runtime', 'public.ai_summary', 'UPDATE')
           OR has_table_privilege('directus', 'public.ai_summary', 'UPDATE') THEN
            RAISE EXCEPTION 'worker roles retained direct summary or review-update privileges';
        END IF;
        IF has_table_privilege('kokonut_runtime',
                               'public.ai_summary_agent_draft_request', 'SELECT')
           OR has_table_privilege('directus',
                                  'public.ai_summary_agent_draft_request', 'SELECT') THEN
            RAISE EXCEPTION 'runtime or Directus can read private worker receipts';
        END IF;
        IF has_function_privilege('kokonut_runtime',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') OR has_function_privilege('directus',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') THEN
            RAISE EXCEPTION 'runtime or Directus can execute the worker draft function';
        END IF;
        IF NOT has_function_privilege('kokonut_worker_execution',
            'kokonut_security.create_location_ai_summary_worker_draft(uuid,text,text,text[],text,uuid)',
            'EXECUTE') THEN
            RAISE EXCEPTION 'worker execution role lacks bounded draft function';
        END IF;

        denied := FALSE;
        BEGIN
            UPDATE public.ai_summary_agent_draft_request
               SET summary_type = 'tampered'
             WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
        EXCEPTION WHEN raise_exception THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker retry receipt update was accepted'; END IF;

        denied := FALSE;
        BEGIN
            DELETE FROM public.ai_summary_agent_draft_request
             WHERE worker_id = '{WORKER_ID}' AND request_id = '{REQUEST_ID}';
        EXCEPTION WHEN raise_exception THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'worker retry receipt deletion was accepted'; END IF;
    END $$;
    """


def _operator_source_acceptance() -> str:
    operator_id = "a0000000-0000-0000-0000-000000000902"
    summary_id = "c0000000-0000-4000-8000-000000000098"
    request_id = "d0000000-0000-4000-8000-000000000910"
    return f"""
    INSERT INTO public.operator_scope_grant (operator_id, location_id, resource, action)
    VALUES ('{operator_id}', '{LOCATION_ID}', 'ai_summary', 'draft');
    INSERT INTO public.ai_summary (
        id, subject_type, subject_id, summary_type, content,
        source_tables, model_version, status, created_by
    ) VALUES (
        '{summary_id}', 'location', '{LOCATION_ID}', 'operations',
        'Operator-authored source-linked draft.', ARRAY['harvest_event'], 'operator-v1',
        'draft', '{operator_id}'
    );
    INSERT INTO public.ai_summary_draft_request (
        operator_id, request_id, location_id, summary_type, request_hash, summary_id
    ) VALUES (
        '{operator_id}', '{request_id}', '{LOCATION_ID}', 'operations', repeat('a', 64),
        '{summary_id}'
    );

    SET ROLE kokonut_runtime;
    BEGIN;
    SELECT set_config('kokonut.tenant_id', '{TENANT_ID}', TRUE);
    SELECT set_config('kokonut.location_id', '{LOCATION_ID}', TRUE);
    SELECT set_config('kokonut.actor_id', '{operator_id}', TRUE);
    SELECT set_config('kokonut.actor_type', 'operator', TRUE);
    DO $$
    DECLARE attached JSONB;
    BEGIN
        attached := kokonut_security.set_location_ai_summary_source_references(
            '{LOCATION_ID}', '{summary_id}', '{request_id}',
            '{{"harvest_event":{{"record_ids":["e0000000-0000-4000-8000-000000000001"],"row_count":1,"truncated":false}}}}'::jsonb
        );
        IF attached -> 'harvest_event' -> 'record_ids'
           <> '["e0000000-0000-4000-8000-000000000001"]'::jsonb THEN
            RAISE EXCEPTION 'operator source-reference behavior changed';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;
    """


def main() -> int:
    base = _load_base()
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker executable is required for disposable PostgreSQL acceptance")
    container = f"kokonut-agent-summary-worker-{uuid.uuid4().hex[:8]}"
    checks = [
        "migrations 405, 419, 521-524, 529-537 and 539 apply; migrations 530-537 and 539 replay",
        "the original structured worker result is stored atomically with its draft and replayed without source reads",
        "pre-result worker receipts retain their content-only lookup fallback",
        "same-key summary-type collisions fail with 22023 before worker source reads, while cross-location result lookups fail with 42501",
        "worker results must match draft content, stay within size bounds, and remain inaccessible through direct table grants",
        "signed worker credential grants only ai_summary:draft for the exact owned location",
        "worker draft is attributed to a database worker principal and exact request retries replay once",
        "only the four deterministic and ten registered synthesis summary types can create drafts, and rejected types leave no partial row",
        "worker references include location-owned, shared-catalog, and four capital-efficiency rows validated through published public views",
        "the registered view map validates four location-scoped bio-factory views without exposing the regional network catalogue",
        "migration 533 validates four regenerative source views and rejects cross-location rows without changing attached manifests",
        "migration 534 validates fifteen location-scoped views across commons, GNH, financial resilience, and open-source-capitalist agents",
        "the four additional agent manifests round-trip through signed worker scope; global source catalogues stay excluded",
        "the drafter receives only ID/location view columns and worker execution receives no direct source table access",
        "migration 535 validates consent-filtered cultural, wellbeing, participatory-action, and stakeholder-feedback views",
        "private/no-consent stakeholder feedback cannot be attached to a worker draft",
        "the consent-safe source drafter receives only ID/location columns and worker execution has no sensitive-table access",
        "migration 536 validates location-assigned Kokonut Commons governance policy views",
        "Kokonut Commons manifests include location-assigned rows but exclude global federation, signal, and unassigned policy records",
        "Kokonut Commons drafter grants are limited to ID/location and worker execution has no direct policy-table access",
        "cross-location, unpublished, and inexact-count view references fail closed without partial manifests; workers lack direct source-table access",
        "conflicting request intent, mismatched location, and duplicate source metadata fail closed",
        "worker login/execution cannot write summaries directly; runtime and Directus cannot bypass review with direct UPDATE",
        "independent operator review sees the worker attribution and can verify only to verified",
        "review queue exposes attached worker source references and the operator setter remains compatible",
        "legacy unattributed drafts remain blocked from approval; lifecycle review is operator-attributed",
        "runtime and Directus cannot call worker draft functions or read private worker receipts",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [path.name for path in MIGRATIONS],
        "database_target": "new disposable PostgreSQL 16 container with network disabled",
        "candidate_or_legacy_modified": False,
        "credential_note": "only a synthetic high-entropy credential is hashed in the disposable fixture",
        "review_context_note": "operator review uses a synthetic context stub in the disposable SQL fixture; production worker code uses the database-signed context helper",
        "source_lineage_note": "capital-efficiency, bio-factory, regenerative, commons, GNH, financial resilience, open-source-capitalist, consent-safe wellbeing/feedback, and farm-assigned Kokonut Commons synthesis attach bounded IDs for thirty-four location-scoped public views; private feedback and global governance catalogues remain unreferenced",
        "checks": checks,
    }
    stage = "container_start"
    try:
        base.run([
            docker, "run", "--rm", "--detach", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        base.wait_ready(docker, container)
        stage = "worker_fixture_and_migrations_405_419"
        base.psql(docker, container, WORKER_FIXTURE.read_text(encoding="utf-8"))
        for migration_path in MIGRATIONS[:2]:
            sql = migration_path.read_text(encoding="utf-8")
            base.psql(docker, container, sql)
        stage = "ai_summary_fixture_and_migrations_521_522_523_524_529_530_531_532_533_534_535_536_537_539"
        base.psql(docker, container, AI_SUMMARY_FIXTURE.read_text(encoding="utf-8"))
        for migration_path in MIGRATIONS[2:]:
            sql = migration_path.read_text(encoding="utf-8")
            base.psql(docker, container, sql)
            if migration_path.name.startswith(("530_", "531_", "532_", "533_", "534_", "535_", "536_", "537_", "539_")):
                base.psql(docker, container, sql)
        stage = "signed_worker_acceptance"
        base.psql(docker, container, _worker_acceptance())
        stage = "structured_worker_result_first_write_acceptance"
        base.psql(docker, container, _worker_result_create_acceptance())
        stage = "structured_worker_result_exact_retry_acceptance"
        base.psql(docker, container, _worker_result_retry_acceptance())
        stage = "structured_worker_result_signed_lookup_acceptance"
        base.psql(docker, container, _worker_result_lookup_acceptance())
        stage = "structured_worker_result_validation_acceptance"
        base.psql(docker, container, _worker_result_validation_acceptance())
        stage = "structured_worker_result_conflicting_summary_type_rejection"
        _expect_worker_result_lookup_sqlstate(
            base, docker, container, location_id=LOCATION_ID,
            summary_type="carbon_yield", request_id="d0000000-0000-4000-8000-000000009800",
            sqlstate="22023", label="same-key summary-type collision",
        )
        stage = "structured_worker_result_cross_location_rejection"
        _expect_worker_result_lookup_sqlstate(
            base, docker, container, location_id=OTHER_LOCATION_ID,
            summary_type="holistic_wellbeing", request_id="d0000000-0000-4000-8000-000000009800",
            sqlstate="42501", label="cross-location worker result lookup",
        )
        stage = "multi_agent_source_reference_acceptance"
        base.psql(docker, container, _registered_synthesis_source_acceptance())
        stage = "consent_safe_wellbeing_feedback_acceptance"
        base.psql(docker, container, _consent_safe_feedback_acceptance())
        stage = "kokonut_commons_source_acceptance"
        base.psql(docker, container, _kokonut_commons_source_acceptance())
        base.psql(docker, container, _review_context_fixture())
        stage = "synthetic_operator_source_reference_acceptance"
        base.psql(docker, container, _operator_source_acceptance())
        stage = "synthetic_operator_review_acceptance"
        base.psql(docker, container, _review_acceptance())
        evidence["result"] = "passed"
        evidence["assertions_passed"] = len(checks)
    except Exception as exc:  # noqa: BLE001 - no credential or connection string is recorded
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_stage"] = stage
        evidence["failure_summary"] = str(exc)[:1200]
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
