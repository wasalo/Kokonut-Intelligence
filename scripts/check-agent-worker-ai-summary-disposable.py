#!/usr/bin/env python3
"""Replay and check signed-worker AI-summary drafts on disposable PostgreSQL."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/check-ai-summary-review-disposable.py"
WORKER_FIXTURE = ROOT / "tests/fixtures/worker_tenant_context_disposable.sql"
AI_SUMMARY_FIXTURE = ROOT / "tests/fixtures/agent_worker_ai_summary_disposable.sql"
DELPHI_SOURCE_FIXTURE = ROOT / "tests/fixtures/agent_worker_delphi_source_disposable.sql"
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
    ROOT / "schemas/postgres/540_scoped_agent_source_references.sql",
    ROOT / "schemas/postgres/541_agent_synthesis_source_reader.sql",
    ROOT / "schemas/postgres/542_agent_deterministic_summary_source_reader.sql",
    ROOT / "schemas/postgres/543_tenant_scoped_agent_synthesis_source_views.sql",
    ROOT / "schemas/postgres/544_tenant_scoped_deterministic_summary_source_views.sql",
    ROOT / "schemas/postgres/545_signed_ebf_evidence_gap_source.sql",
    ROOT / "schemas/postgres/546_signed_cids_export_source.sql",
    ROOT / "schemas/postgres/547_signed_ai_summary_inspection_source.sql",
    ROOT / "schemas/postgres/548_signed_delphi_agent_summary_source.sql",
    ROOT / "schemas/postgres/580_agent_source_worker_identity_split.sql",
    ROOT / "schemas/postgres/581_isolated_ai_summary_inspection_worker.sql",
    ROOT / "schemas/postgres/582_isolated_organic_readiness_worker.sql",
    ROOT / "schemas/postgres/583_isolated_ecological_modeling_worker.sql",
    ROOT / "schemas/postgres/584_isolated_holistic_wellbeing_worker.sql",
    ROOT / "schemas/postgres/585_isolated_feedback_worker.sql",
    ROOT / "schemas/postgres/586_isolated_commons_liberation_worker.sql",
    ROOT / "schemas/postgres/587_isolated_gnh_alignment_worker.sql",
    ROOT / "schemas/postgres/588_isolated_regenerator_worker.sql",
    ROOT / "schemas/postgres/589_isolated_capital_efficiency_worker.sql",
    ROOT / "schemas/postgres/590_isolated_financial_resilience_worker.sql",
    ROOT / "schemas/postgres/591_isolated_bio_factory_worker.sql",
    ROOT / "schemas/postgres/592_isolated_open_source_capitalist_worker.sql",
]
OUTPUT = Path(os.environ.get(
    "KOKONUT_AGENT_WORKER_TEST_OUTPUT",
    ROOT / "docs/refactor/builds/2026-10-23-recovery/cap-038-gnh-alignment-identity-native-disposable.json",
))
IMAGE = os.environ.get("KOKONUT_AGENT_WORKER_TEST_IMAGE", "postgis/postgis:16-3.4")
PLATFORM = os.environ.get("KOKONUT_AGENT_WORKER_TEST_PLATFORM", "").strip()
if PLATFORM not in {"", "linux/amd64", "linux/arm64"}:
    raise SystemExit("KOKONUT_AGENT_WORKER_TEST_PLATFORM must be linux/amd64 or linux/arm64")
WORKER_ID = "a0000000-0000-0000-0000-000000000901"
TENANT_ID = "a0000000-0000-0000-0000-000000000801"
LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-0000-0000-000000000002"
REQUEST_ID = "d0000000-0000-4000-8000-000000000901"
RAW_CREDENTIAL = "synthetic-agent-summary-worker-credential-2026-10-21"
CREDENTIAL_HASH = hashlib.sha256(RAW_CREDENTIAL.encode("utf-8")).hexdigest()
SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000902"
SOURCE_RAW_CREDENTIAL = "synthetic-agent-summary-source-credential-2026-10-22"
SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
EBF_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000904"
EBF_SOURCE_RAW_CREDENTIAL = "synthetic-agent-ebf-source-credential-2026-10-23"
EBF_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    EBF_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
CIDS_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000905"
CIDS_SOURCE_RAW_CREDENTIAL = "synthetic-agent-cids-source-credential-2026-10-23"
CIDS_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    CIDS_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
DELPHI_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000906"
DELPHI_SOURCE_RAW_CREDENTIAL = "synthetic-agent-delphi-source-credential-2026-10-23"
DELPHI_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    DELPHI_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
DETERMINISTIC_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000903"
DETERMINISTIC_SOURCE_RAW_CREDENTIAL = "synthetic-agent-summary-deterministic-source-credential"
DETERMINISTIC_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    DETERMINISTIC_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
INSPECTION_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000907"
INSPECTION_SOURCE_RAW_CREDENTIAL = "synthetic-agent-summary-inspection-source-credential"
INSPECTION_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    INSPECTION_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
ORGANIC_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000908"
ORGANIC_SOURCE_RAW_CREDENTIAL = "synthetic-organic-readiness-source-credential-2026-10-23"
ORGANIC_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    ORGANIC_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
ECOLOGICAL_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000909"
ECOLOGICAL_SOURCE_RAW_CREDENTIAL = "synthetic-ecological-modeling-source-credential-2026-10-23"
ECOLOGICAL_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    ECOLOGICAL_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
HOLISTIC_WELLBEING_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000910"
HOLISTIC_WELLBEING_SOURCE_RAW_CREDENTIAL = "synthetic-holistic-wellbeing-source-credential-2026-10-23"
HOLISTIC_WELLBEING_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    HOLISTIC_WELLBEING_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
FEEDBACK_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000911"
FEEDBACK_SOURCE_RAW_CREDENTIAL = "synthetic-feedback-source-credential-2026-10-23"
FEEDBACK_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    FEEDBACK_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
COMMONS_LIBERATION_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000912"
COMMONS_LIBERATION_SOURCE_RAW_CREDENTIAL = "synthetic-commons-liberation-source-credential-2026-10-23"
COMMONS_LIBERATION_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    COMMONS_LIBERATION_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
GNH_ALIGNMENT_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000913"
GNH_ALIGNMENT_SOURCE_RAW_CREDENTIAL = "synthetic-gnh-alignment-source-credential-2026-10-23"
GNH_ALIGNMENT_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    GNH_ALIGNMENT_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
REGENERATOR_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000914"
REGENERATOR_SOURCE_RAW_CREDENTIAL = "synthetic-regenerator-source-credential-2026-10-23"
REGENERATOR_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    REGENERATOR_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
CAPITAL_EFFICIENCY_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000915"
CAPITAL_EFFICIENCY_SOURCE_RAW_CREDENTIAL = "synthetic-capital-efficiency-source-credential-2026-10-23"
CAPITAL_EFFICIENCY_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    CAPITAL_EFFICIENCY_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
FINANCIAL_RESILIENCE_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000916"
FINANCIAL_RESILIENCE_SOURCE_RAW_CREDENTIAL = "synthetic-financial-resilience-source-credential-2026-10-23"
FINANCIAL_RESILIENCE_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    FINANCIAL_RESILIENCE_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
BIO_FACTORY_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000917"
BIO_FACTORY_SOURCE_RAW_CREDENTIAL = "synthetic-bio-factory-source-credential-2026-10-23"
BIO_FACTORY_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    BIO_FACTORY_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
OPEN_SOURCE_CAPITALIST_SOURCE_WORKER_ID = "a0000000-0000-0000-0000-000000000918"
OPEN_SOURCE_CAPITALIST_SOURCE_RAW_CREDENTIAL = "synthetic-open-source-capitalist-source-credential-2026-10-23"
OPEN_SOURCE_CAPITALIST_SOURCE_CREDENTIAL_HASH = hashlib.sha256(
    OPEN_SOURCE_CAPITALIST_SOURCE_RAW_CREDENTIAL.encode("utf-8")
).hexdigest()
ORGANIC_SOURCE_VIEW_NAMES = (
    "organic_readiness_assessment",
    "organic_transition_plan",
    "organic_input_audit",
    "buffer_zone",
    "harvest_handling_record",
    "organic_certification_record",
    "organic_compliance_checklist",
    "prohibited_substance_record",
    "v_public_organic_readiness",
    "v_public_organic_transition",
    "v_public_organic_input_audit",
    "v_public_buffer_zone_status",
    "v_public_organic_harvest_segregation",
    "v_public_organic_certifications",
    "v_public_organic_prohibited_substance_audit",
)
HOLISTIC_WELLBEING_SOURCE_VIEW_NAMES = (
    "v_public_cultural_context_summary",
    "v_public_wellbeing_metric_summary",
    "v_public_participatory_governance_summary",
)
FEEDBACK_SOURCE_VIEW_NAMES = ("v_public_stakeholder_feedback_summary",)
COMMONS_LIBERATION_SOURCE_VIEW_NAMES = (
    "v_public_time_liberation_summary",
    "v_public_capital_alignment_summary",
    "v_public_governance_inclusion_summary",
    "v_public_land_stewardship_summary",
)
GNH_ALIGNMENT_SOURCE_VIEW_NAMES = (
    "v_public_gnh_alignment_summary",
    "v_public_cultural_preservation_summary",
    "v_public_renewable_energy_summary",
    "v_public_vulnerable_access_summary",
    "v_public_foundational_wellbeing_summary",
)
REGENERATOR_SOURCE_VIEW_NAMES = (
    "v_public_regenerative_outcome_summary",
    "v_public_community_governance_mechanism",
    "v_public_replication_readiness_summary",
    "v_public_adaptive_stewardship_summary",
)
CAPITAL_EFFICIENCY_SOURCE_VIEW_NAMES = (
    "v_public_capital_efficiency_summary",
    "v_public_regenerative_efficiency_summary",
    "v_public_governance_throughput_summary",
    "v_public_capital_provider_utility_summary",
)
FINANCIAL_RESILIENCE_SOURCE_VIEW_NAMES = (
    "v_public_financial_sustainability_summary",
    "v_public_risk_mitigation_summary",
    "v_public_scaling_roadmap_summary",
    "v_public_green_paper_publication_status",
)
FINANCIAL_RESILIENCE_LOCATION_VIEW_NAMES = FINANCIAL_RESILIENCE_SOURCE_VIEW_NAMES[:3]
BIO_FACTORY_SOURCE_VIEW_NAMES = (
    "v_public_bio_factory_batch_summary",
    "v_public_bio_input_provenance_summary",
    "v_public_bio_recipe_library_summary",
    "v_public_bio_factory_quality_test_summary",
    "v_public_bio_regional_input_summary",
)
BIO_FACTORY_LOCATION_VIEW_NAMES = BIO_FACTORY_SOURCE_VIEW_NAMES[:4]
OPEN_SOURCE_CAPITALIST_SOURCE_VIEW_NAMES = (
    "v_public_farm_launch_unit_economics",
    "v_public_adoption_barrier_assessment",
    "v_public_perpetual_value_stress_test",
    "v_public_network_scaling_target",
    "v_public_open_source_impact_artifact",
)
OPEN_SOURCE_CAPITALIST_LOCATION_VIEW_NAMES = OPEN_SOURCE_CAPITALIST_SOURCE_VIEW_NAMES[:3]
ECOLOGICAL_SOURCE_VIEW_NAMES = (
    "ecological_interaction",
    "energy_flow_measurement",
    "population_dynamics_record",
    "soil_input_application",
    "pest_observation",
    "biocontrol_release",
    "resource_consumption",
    "ecological_harvest_event",
    "location",
    "ecological_species_observation",
    "livestock_group",
    "feed_intake_record",
    "token_reward_distribution",
    "reward_calibration_model",
    "v_public_ecological_interaction_summary",
    "v_public_energy_flow_summary",
    "v_public_population_dynamics_summary",
    "v_public_soil_input_retention",
    "v_public_pest_trends",
    "v_public_biocontrol_effectiveness",
    "v_public_resource_efficiency",
    "v_public_ecological_species_conservation",
    "v_public_token_reward_distribution",
    "v_public_reward_calibration",
    "v_public_ecological_harvest_event_reference",
    "v_public_ecological_livestock_group_reference",
    "v_public_ecological_feed_intake_reference",
)
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
    "federation_protocol": "v_public_federation_protocol",
    "participatory_signal_experiment": "v_public_participatory_signal_experiment",
}
NETWORK_SOURCE_VIEWS = {
    "bio_regional_input_availability": "v_public_bio_regional_input_summary",
    "network_scaling_target": "v_public_network_scaling_target",
    "open_source_impact_artifact": "v_public_open_source_impact_artifact",
    "green_paper_publication_review": "v_public_green_paper_publication_status",
    "federation_protocol": "v_public_federation_protocol",
    "participatory_signal_experiment": "v_public_participatory_signal_experiment",
}
SOURCE_READER_VIEWS = tuple(sorted({
    "v_public_algorithmic_redistribution_mechanism",
    "v_public_anti_capture_governance_policy",
    "v_public_commons_redistribution_policy",
    "v_public_federation_protocol",
    "v_public_participatory_signal_experiment",
    # Holistic wellbeing receives these consent-filtered projections through
    # its own migration-584 task reader.
    # Feedback receives its consent-safe summary through a separate
    # migration-585 task reader.
    # Commons Liberation receives four location-filtered views through its
    # migration-586 task reader.
    # GNH Alignment receives five location-filtered views through its
    # migration-587 task reader.
    # Regenerator receives four location-filtered views through its
    # migration-588 task reader.
    # Capital Efficiency receives four location-filtered views through its
    # migration-589 task reader.
    # Financial Resilience receives three location views and one network view
    # through its migration-590 task reader. Bio Factory receives four location
    # views and one network catalogue through its migration-591 task reader.
    # Open Source Capitalist receives three mixed-scope and two network views
    # through its migration-592 task reader.

}))
DETERMINISTIC_SOURCE_TABLES = (
    "crop",
    "crop_cycle",
    "expense_category",
    "expense_event",
    "farm_registry_record",
    "harvest_event",
    "noi_snapshot",
    "remote_sensing_observation",
    "sales_event",
    "sensor_reading",
    "soil_carbon_measurement",
    "species_observation",
    "weather_observation",
)

EBF_SOURCE_FIXTURE = f"""
CREATE OR REPLACE VIEW public.v_ebf_evidence_gap_summary AS
SELECT
    'a0000000-0000-4000-8000-000000000101'::uuid AS scorecard_id,
    '{LOCATION_ID}'::uuid AS location_id,
    'Synthetic owned farm'::text AS location_name,
    'soil_health'::text AS pillar_key,
    'Soil Health'::text AS pillar_name,
    0.5::numeric AS normalized_score,
    'medium'::text AS confidence_level,
    3::integer AS evidence_maturity_level,
    'Reviewed'::text AS evidence_maturity_label,
    0::bigint AS evidence_count,
    0::bigint AS public_safe_evidence_count,
    3::integer AS min_linked_evidence_maturity,
    3::integer AS max_linked_evidence_maturity,
    'missing_evidence'::text AS gap_status
UNION ALL
SELECT
    'a0000000-0000-4000-8000-000000000102'::uuid,
    '{OTHER_LOCATION_ID}'::uuid,
    'Synthetic foreign farm'::text,
    'soil_health'::text,
    'Soil Health'::text,
    0.5::numeric,
    'medium'::text,
    3::integer,
    'Reviewed'::text,
    0::bigint,
    0::bigint,
    3::integer,
    3::integer,
    'missing_evidence'::text;
"""

CIDS_SOURCE_FIXTURE = f"""
ALTER TABLE public.location ADD COLUMN name TEXT, ADD COLUMN slug TEXT, ADD COLUMN description TEXT;
UPDATE public.location SET name = 'Synthetic farm', slug = 'synthetic-farm', description = 'Public-safe location summary'
 WHERE id = '{LOCATION_ID}';
UPDATE public.location SET name = 'Foreign farm', slug = 'foreign-farm', description = 'Other tenant'
 WHERE id = '{OTHER_LOCATION_ID}';
ALTER TABLE public.farm_registry_record
    ADD COLUMN project_summary TEXT,
    ADD COLUMN local_problem TEXT,
    ADD COLUMN proposed_solution TEXT,
    ADD COLUMN created_at TIMESTAMPTZ;
UPDATE public.farm_registry_record
   SET project_summary = 'Synthetic program', local_problem = 'Synthetic problem',
       proposed_solution = 'Synthetic solution', created_at = now()
 WHERE location_id = '{LOCATION_ID}';
CREATE TABLE public.farm (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, name TEXT, description TEXT
);
INSERT INTO public.farm VALUES
    ('e0000000-0000-4000-8000-000000000901', '{LOCATION_ID}', 'Synthetic farm', 'Farm summary'),
    ('e0000000-0000-4000-8000-000000000902', '{OTHER_LOCATION_ID}', 'Foreign farm', 'Other tenant');
CREATE TABLE public.stakeholder_outcome (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL, outcome_name TEXT, outcome_description TEXT,
    stakeholder_group TEXT, importance TEXT, is_underserved BOOLEAN,
    importance_perspective TEXT, sdg_number INTEGER
);
INSERT INTO public.stakeholder_outcome VALUES
    ('e0000000-0000-4000-8000-000000000911', '{LOCATION_ID}', 'verified', now(),
     'Farm operator capacity', 'Operators build skills', 'farm_operator', 'high', FALSE, 'interview', 8),
    ('e0000000-0000-4000-8000-000000000912', '{OTHER_LOCATION_ID}', 'published', now(),
     'Foreign outcome', 'Other tenant', 'community', 'high', FALSE, 'survey', 9);
CREATE TABLE public.sdg (sdg_number INTEGER PRIMARY KEY, name TEXT NOT NULL);
INSERT INTO public.sdg VALUES (8, 'Decent Work'), (9, 'Industry and Innovation');
CREATE TABLE public.farm_impact_mapping (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL,
    framework_key TEXT, dimension_key TEXT, sdg_number INTEGER
);
INSERT INTO public.farm_impact_mapping VALUES
    ('e0000000-0000-4000-8000-000000000921', '{LOCATION_ID}', 'published', 'ebf', 'value', 8),
    ('e0000000-0000-4000-8000-000000000922', '{OTHER_LOCATION_ID}', 'published', 'ebf', 'value', 9);
CREATE TABLE public.metric_definition (
    id UUID PRIMARY KEY, metric_key TEXT NOT NULL, display_name TEXT,
    description TEXT, unit TEXT, active BOOLEAN NOT NULL
);
CREATE TABLE public.metric_value (
    id UUID PRIMARY KEY, metric_id UUID NOT NULL, location_id UUID NOT NULL,
    period_start DATE, period_end DATE, value NUMERIC, unit TEXT,
    verified BOOLEAN NOT NULL, computation_method TEXT, computed_at TIMESTAMPTZ
);
INSERT INTO public.metric_definition VALUES
    ('e0000000-0000-4000-8000-000000000931', 'value_flowed', 'Value flowed', 'Verified value', 'USD', TRUE);
INSERT INTO public.metric_value VALUES
    ('e0000000-0000-4000-8000-000000000941', 'e0000000-0000-4000-8000-000000000931',
     '{LOCATION_ID}', '2026-01-01', '2026-01-31', 12.5, 'USD', TRUE, 'fixture', now()),
    ('e0000000-0000-4000-8000-000000000942', 'e0000000-0000-4000-8000-000000000931',
     '{OTHER_LOCATION_ID}', '2026-01-01', '2026-01-31', 99.0, 'USD', TRUE, 'fixture', now());
ALTER TABLE public.stakeholder_feedback
    ADD COLUMN feedback_date DATE,
    ADD COLUMN stakeholder_group TEXT,
    ADD COLUMN consent_scope TEXT,
    ADD COLUMN public_summary TEXT;
UPDATE public.stakeholder_feedback
   SET feedback_date = '2026-01-01', stakeholder_group = 'farm_operator',
       consent_scope = 'public_summary', public_summary = 'Synthetic public summary'
 WHERE id = 'e0000000-0000-4000-8000-000000000604';
INSERT INTO public.stakeholder_feedback (
    id, location_id, status, consent_given, is_public, feedback_date,
    stakeholder_group, consent_scope, public_summary
) VALUES
    ('e0000000-0000-4000-8000-000000000952', '{LOCATION_ID}', 'published', FALSE, FALSE,
     '2026-01-03', 'private_group', 'private', 'Private raw text'),
    ('e0000000-0000-4000-8000-000000000953', '{OTHER_LOCATION_ID}', 'published', TRUE, TRUE,
     '2026-01-04', 'foreign_group', 'public_summary', 'Foreign public text');
CREATE TABLE public.evidence_maturity_level (level INTEGER PRIMARY KEY, label TEXT NOT NULL);
INSERT INTO public.evidence_maturity_level VALUES (3, 'Reviewed record');
CREATE TABLE public.impact_claim (
    id UUID PRIMARY KEY, location_id UUID NOT NULL, status TEXT NOT NULL,
    claim_date DATE, claim_text TEXT, period_start DATE, period_end DATE,
    confidence_notes TEXT, evidence_maturity INTEGER, methodology_ref TEXT,
    external_verifier TEXT, attestation_uid TEXT
);
INSERT INTO public.impact_claim VALUES
    ('e0000000-0000-4000-8000-000000000961', '{LOCATION_ID}', 'verified', '2026-01-05',
     'Synthetic impact claim', '2026-01-01', '2026-01-31', 'High confidence', 3,
     'methodology-v1', 'Independent reviewer', '0xsynthetic'),
    ('e0000000-0000-4000-8000-000000000962', '{OTHER_LOCATION_ID}', 'published', '2026-01-05',
     'Foreign claim', '2026-01-01', '2026-01-31', 'Other tenant', 3,
     'methodology-v1', 'Reviewer', '0xforeign');
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
ALTER TABLE public.farm ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm FORCE ROW LEVEL SECURITY;
ALTER TABLE public.farm_registry_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm_registry_record FORCE ROW LEVEL SECURITY;
ALTER TABLE public.stakeholder_outcome ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stakeholder_outcome FORCE ROW LEVEL SECURITY;
ALTER TABLE public.farm_impact_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm_impact_mapping FORCE ROW LEVEL SECURITY;
ALTER TABLE public.sdg ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sdg FORCE ROW LEVEL SECURITY;
ALTER TABLE public.metric_definition ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.metric_definition FORCE ROW LEVEL SECURITY;
ALTER TABLE public.metric_value ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.metric_value FORCE ROW LEVEL SECURITY;
ALTER TABLE public.stakeholder_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stakeholder_feedback FORCE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_maturity_level ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_maturity_level FORCE ROW LEVEL SECURITY;
ALTER TABLE public.impact_claim ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.impact_claim FORCE ROW LEVEL SECURITY;
"""


def _organic_source_projection_fixture() -> str:
    statements = []
    for view_name in ORGANIC_SOURCE_VIEW_NAMES:
        statements.append(
            f"""
            CREATE VIEW kokonut_agent_source.{view_name}
            WITH (security_barrier = true) AS
            SELECT source_row.location_id
              FROM (VALUES ('{LOCATION_ID}'::uuid), ('{OTHER_LOCATION_ID}'::uuid))
                   AS source_row(location_id)
             WHERE EXISTS (
                   SELECT 1
                     FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE scope.location_id = source_row.location_id
             );
            GRANT SELECT ON kokonut_agent_source.{view_name}
                TO kokonut_agent_summary_source_reader;
            """
        )
    return "\n".join(statements)


def _organic_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(f"'{name}'" for name in ORGANIC_SOURCE_VIEW_NAMES)
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{ORGANIC_SOURCE_WORKER_ID}', 'agent-organic-readiness-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{ORGANIC_SOURCE_WORKER_ID}', '{ORGANIC_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{ORGANIC_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic organic-readiness source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$ BEGIN
        IF has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_source_login',
            'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'shared synthesis roles retain organic source access';
        END IF;
        IF NOT has_table_privilege(
            'kokonut_agent_organic_readiness_reader',
            'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_organic_readiness_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_organic_readiness_login',
            'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_organic_readiness_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_organic_readiness_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_organic_readiness_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'organic source login/reader exceeds the task contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_organic_readiness_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_organic_readiness_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'organic projection % returned rows before signed context', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{ORGANIC_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_organic_readiness_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'organic projection % violated signed location scope', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _organic_source_stale_grants() -> str:
    view_names = ", ".join(
        f"kokonut_agent_source.{name}" for name in ORGANIC_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {view_names}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_organic_readiness_reader;
    GRANT SELECT ON public.ai_summary
        TO kokonut_agent_organic_readiness_reader,
           kokonut_agent_organic_readiness_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_organic_readiness_reader,
           kokonut_agent_organic_readiness_login;
    """


def _ecological_source_projection_fixture() -> str:
    statements = []
    for view_name in ECOLOGICAL_SOURCE_VIEW_NAMES:
        statements.append(
            f"""
            CREATE VIEW kokonut_agent_source.{view_name}
            WITH (security_barrier = true) AS
            SELECT source_row.location_id
              FROM (VALUES ('{LOCATION_ID}'::uuid), ('{OTHER_LOCATION_ID}'::uuid))
                   AS source_row(location_id)
             WHERE EXISTS (
                   SELECT 1
                     FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
                    WHERE scope.location_id = source_row.location_id
             );
            GRANT SELECT ON kokonut_agent_source.{view_name}
                TO kokonut_agent_summary_source_reader;
            """
        )
    return "\n".join(statements)


def _ecological_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(f"'{name}'" for name in ECOLOGICAL_SOURCE_VIEW_NAMES)
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{ECOLOGICAL_SOURCE_WORKER_ID}', 'agent-ecological-modeling-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{ECOLOGICAL_SOURCE_WORKER_ID}', '{ECOLOGICAL_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{ECOLOGICAL_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic ecological-modeling source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$ BEGIN
        IF has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'kokonut_agent_source.ecological_interaction', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_source_login',
            'kokonut_agent_source.ecological_interaction', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'shared synthesis roles retain ecological modeling source access';
        END IF;
        IF NOT has_table_privilege(
            'kokonut_agent_ecological_modeling_reader',
            'kokonut_agent_source.ecological_interaction', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_ecological_modeling_reader',
            'kokonut_agent_source.organic_readiness_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_ecological_modeling_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_ecological_modeling_login',
            'kokonut_agent_source.ecological_interaction', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_ecological_modeling_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_ecological_modeling_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_ecological_modeling_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'ecological modeling source login/reader exceeds its task contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_ecological_modeling_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_ecological_modeling_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'ecological projection % returned rows before signed context', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{ECOLOGICAL_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_ecological_modeling_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'ecological projection % violated signed location scope', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _ecological_source_stale_grants() -> str:
    view_names = ", ".join(
        f"kokonut_agent_source.{name}" for name in ECOLOGICAL_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {view_names}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_ecological_modeling_reader;
    GRANT SELECT ON public.ai_summary
        TO kokonut_agent_ecological_modeling_reader,
           kokonut_agent_ecological_modeling_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_ecological_modeling_reader,
           kokonut_agent_ecological_modeling_login;
    """


def _holistic_wellbeing_source_projection_fixture() -> str:
    return f"""
    INSERT INTO public.cultural_context_record
        (id, location_id, status, consent_given, is_public)
    VALUES ('e0000000-0000-4000-8000-000000000970', '{OTHER_LOCATION_ID}',
            'published', TRUE, TRUE);
    INSERT INTO public.wellbeing_metric_observation (id, location_id, status)
    VALUES ('e0000000-0000-4000-8000-000000000971', '{OTHER_LOCATION_ID}', 'published');
    INSERT INTO public.participatory_action_record (id, location_id, status)
    VALUES ('e0000000-0000-4000-8000-000000000972', '{OTHER_LOCATION_ID}', 'published');
    """


def _holistic_wellbeing_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in HOLISTIC_WELLBEING_SOURCE_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{HOLISTIC_WELLBEING_SOURCE_WORKER_ID}', 'agent-holistic-wellbeing-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{HOLISTIC_WELLBEING_SOURCE_WORKER_ID}',
            '{HOLISTIC_WELLBEING_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{HOLISTIC_WELLBEING_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic holistic-wellbeing source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$ BEGIN
        IF has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_source_login',
            'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'shared synthesis roles retain holistic wellbeing source access';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_holistic_wellbeing_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_holistic_wellbeing_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_holistic_wellbeing_reader', 'public.ai_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_holistic_wellbeing_reader', 'public.stakeholder_feedback', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_holistic_wellbeing_login',
            'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_holistic_wellbeing_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_holistic_wellbeing_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'holistic wellbeing source login/reader exceeds its task contract';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(relation.relacl) AS acl
             WHERE namespace.nspname = 'kokonut_agent_source'
               AND relation.relname = ANY(ARRAY[{view_names_sql}]::TEXT[])
               AND acl.grantee = 0 AND acl.privilege_type = 'SELECT'
        ) THEN
            RAISE EXCEPTION 'PUBLIC retained holistic wellbeing projection access';
        END IF;
    END $$;

    SET ROLE kokonut_agent_holistic_wellbeing_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_holistic_wellbeing_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'wellbeing projection % returned rows before signed context', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{HOLISTIC_WELLBEING_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_holistic_wellbeing_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'wellbeing projection % violated signed location scope', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _holistic_wellbeing_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in HOLISTIC_WELLBEING_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_stakeholder_feedback_summary,
        kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_holistic_wellbeing_reader;
    GRANT SELECT ON public.ai_summary, public.stakeholder_feedback
        TO kokonut_agent_holistic_wellbeing_reader,
           kokonut_agent_holistic_wellbeing_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_holistic_wellbeing_reader,
           kokonut_agent_holistic_wellbeing_login;
    """


def _feedback_source_scope_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{FEEDBACK_SOURCE_WORKER_ID}', 'agent-feedback-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{FEEDBACK_SOURCE_WORKER_ID}', '{FEEDBACK_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{FEEDBACK_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic feedback source acceptance fixture'
    ) ON CONFLICT DO NOTHING;
    DO $$
    BEGIN
        IF NOT has_table_privilege(
            'kokonut_agent_feedback_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_source_login',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_feedback_reader', 'public.stakeholder_feedback', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_feedback_login', 'public.stakeholder_feedback', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_feedback_reader', 'public.ai_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_feedback_reader',
            'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_feedback_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_feedback_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'feedback worker roles exceed the task-specific source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_feedback_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_feedback_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_public_stakeholder_feedback_summary;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'feedback source returned rows before signed context';
        END IF;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{FEEDBACK_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_feedback_reader;
    DO $$
    DECLARE own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        SELECT count(*) INTO own_rows
          FROM kokonut_agent_source.v_public_stakeholder_feedback_summary
         WHERE location_id = '{LOCATION_ID}';
        SELECT count(*) INTO foreign_rows
          FROM kokonut_agent_source.v_public_stakeholder_feedback_summary
         WHERE location_id = '{OTHER_LOCATION_ID}';
        IF own_rows <> 1 OR foreign_rows <> 0 THEN
            RAISE EXCEPTION 'feedback view violated signed location scope (own %, foreign %)',
                own_rows, foreign_rows;
        END IF;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _feedback_source_stale_grants() -> str:
    return """
    GRANT SELECT ON kokonut_agent_source.v_public_stakeholder_feedback_summary
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_cultural_context_summary,
        kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_feedback_reader;
    GRANT SELECT ON public.ai_summary, public.stakeholder_feedback
        TO kokonut_agent_feedback_reader, kokonut_agent_feedback_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_feedback_reader, kokonut_agent_feedback_login;
    """


def _commons_liberation_source_projection_fixture() -> str:
    tables = (
        "time_liberation_observation",
        "capital_alignment_assessment",
        "governance_inclusion_observation",
        "land_stewardship_commitment",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=981)
    )


def _commons_liberation_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in COMMONS_LIBERATION_SOURCE_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{COMMONS_LIBERATION_SOURCE_WORKER_ID}', 'agent-commons-liberation-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{COMMONS_LIBERATION_SOURCE_WORKER_ID}',
            '{COMMONS_LIBERATION_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{COMMONS_LIBERATION_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic commons liberation acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{view_names_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_commons_liberation_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_commons_liberation_reader',
            'kokonut_agent_source.v_public_cultural_context_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_commons_liberation_reader',
            'public.time_liberation_observation', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_commons_liberation_login',
            'public.capital_alignment_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_commons_liberation_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_commons_liberation_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_commons_liberation_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'commons liberation roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_commons_liberation_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_commons_liberation_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'commons liberation view % returned rows without signed context',
                    view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{COMMONS_LIBERATION_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_commons_liberation_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'commons liberation view % violated signed scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _commons_liberation_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in COMMONS_LIBERATION_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_cultural_context_summary,
        kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_commons_liberation_reader;
    GRANT SELECT ON public.ai_summary, public.time_liberation_observation,
        public.capital_alignment_assessment
        TO kokonut_agent_commons_liberation_reader,
           kokonut_agent_commons_liberation_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_commons_liberation_reader,
           kokonut_agent_commons_liberation_login;
    """


def _gnh_alignment_source_projection_fixture() -> str:
    tables = (
        "gnh_alignment_assessment",
        "cultural_preservation_plan",
        "renewable_energy_plan",
        "vulnerable_group_access_plan",
        "foundational_wellbeing_observation",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=990)
    )


def _gnh_alignment_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in GNH_ALIGNMENT_SOURCE_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{GNH_ALIGNMENT_SOURCE_WORKER_ID}', 'agent-gnh-alignment-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{GNH_ALIGNMENT_SOURCE_WORKER_ID}',
            '{GNH_ALIGNMENT_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{GNH_ALIGNMENT_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic GNH alignment acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{view_names_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_gnh_alignment_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_gnh_alignment_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_gnh_alignment_reader',
            'public.gnh_alignment_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_gnh_alignment_login',
            'public.cultural_preservation_plan', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_gnh_alignment_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_gnh_alignment_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_gnh_alignment_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'GNH alignment roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_gnh_alignment_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_gnh_alignment_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'GNH alignment view % returned rows without signed context',
                    view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{GNH_ALIGNMENT_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_gnh_alignment_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'GNH alignment view % violated signed scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _gnh_alignment_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in GNH_ALIGNMENT_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_stakeholder_feedback_summary,
        kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_gnh_alignment_reader;
    GRANT SELECT ON public.ai_summary, public.gnh_alignment_assessment,
        public.cultural_preservation_plan
        TO kokonut_agent_gnh_alignment_reader,
           kokonut_agent_gnh_alignment_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_gnh_alignment_reader,
           kokonut_agent_gnh_alignment_login;
    """


def _regenerator_source_projection_fixture() -> str:
    tables = (
        "regenerative_outcome_summary",
        "community_governance_mechanism",
        "replication_readiness_assessment",
        "adaptive_stewardship_review",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=980)
    )


def _regenerator_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in REGENERATOR_SOURCE_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{REGENERATOR_SOURCE_WORKER_ID}', 'agent-regenerator-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{REGENERATOR_SOURCE_WORKER_ID}',
            '{REGENERATOR_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{REGENERATOR_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic regenerator source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{view_names_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_regenerator_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_regenerator_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_regenerator_reader',
            'public.regenerative_outcome_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_regenerator_login',
            'public.adaptive_stewardship_review', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_regenerator_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_regenerator_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_regenerator_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'Regenerator roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_regenerator_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_regenerator_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'Regenerator view % returned rows without signed context',
                    view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{REGENERATOR_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_regenerator_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'Regenerator view % violated signed scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _regenerator_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in REGENERATOR_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_cultural_context_summary,
        kokonut_agent_source.v_public_capital_efficiency_summary
        TO kokonut_agent_regenerator_reader;
    GRANT SELECT ON public.ai_summary, public.regenerative_outcome_summary,
        public.adaptive_stewardship_review
        TO kokonut_agent_regenerator_reader,
           kokonut_agent_regenerator_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_regenerator_reader,
           kokonut_agent_regenerator_login;
    """


def _capital_efficiency_source_projection_fixture() -> str:
    tables = (
        "capital_efficiency_scenario",
        "regenerative_efficiency_observation",
        "governance_throughput_observation",
        "capital_provider_utility_scenario",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=970)
    )


def _capital_efficiency_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in CAPITAL_EFFICIENCY_SOURCE_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{CAPITAL_EFFICIENCY_SOURCE_WORKER_ID}', 'agent-capital-efficiency-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{CAPITAL_EFFICIENCY_SOURCE_WORKER_ID}',
            '{CAPITAL_EFFICIENCY_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{CAPITAL_EFFICIENCY_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic capital-efficiency source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{view_names_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_capital_efficiency_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_capital_efficiency_reader',
            'kokonut_agent_source.v_public_stakeholder_feedback_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_capital_efficiency_reader',
            'public.capital_efficiency_scenario', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_capital_efficiency_login',
            'public.capital_provider_utility_scenario', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_capital_efficiency_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_capital_efficiency_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_capital_efficiency_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'capital-efficiency roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_capital_efficiency_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_capital_efficiency_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'capital-efficiency view % returned rows without signed context',
                    view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CAPITAL_EFFICIENCY_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_capital_efficiency_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'capital-efficiency view % violated signed scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _capital_efficiency_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in CAPITAL_EFFICIENCY_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_cultural_context_summary,
        kokonut_agent_source.v_public_stakeholder_feedback_summary
        TO kokonut_agent_capital_efficiency_reader;
    GRANT SELECT ON public.ai_summary, public.capital_efficiency_scenario,
        public.capital_provider_utility_scenario
        TO kokonut_agent_capital_efficiency_reader,
           kokonut_agent_capital_efficiency_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_capital_efficiency_reader,
           kokonut_agent_capital_efficiency_login;
    """


def _financial_resilience_source_projection_fixture() -> str:
    tables = (
        "financial_sustainability_plan",
        "risk_mitigation_register",
        "scaling_roadmap_milestone",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=960)
    )


def _financial_resilience_source_scope_acceptance() -> str:
    all_views_sql = ", ".join(
        f"'{name}'" for name in FINANCIAL_RESILIENCE_SOURCE_VIEW_NAMES
    )
    location_views_sql = ", ".join(
        f"'{name}'" for name in FINANCIAL_RESILIENCE_LOCATION_VIEW_NAMES
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{FINANCIAL_RESILIENCE_SOURCE_WORKER_ID}', 'agent-financial-resilience-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{FINANCIAL_RESILIENCE_SOURCE_WORKER_ID}',
            '{FINANCIAL_RESILIENCE_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{FINANCIAL_RESILIENCE_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic financial-resilience source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{all_views_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_financial_resilience_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name),
                 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_financial_resilience_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_financial_resilience_reader',
            'public.financial_sustainability_plan', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_financial_resilience_login',
            'public.green_paper_publication_review', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_financial_resilience_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_financial_resilience_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_financial_resilience_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'Financial Resilience roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_financial_resilience_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_financial_resilience_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{all_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'Financial Resilience view % returned rows without signed context',
                    view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{FINANCIAL_RESILIENCE_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_financial_resilience_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT; network_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{location_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'Financial Resilience view % violated location scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
        SELECT count(*) INTO network_rows
          FROM kokonut_agent_source.v_public_green_paper_publication_status;
        IF network_rows <> 1 THEN
            RAISE EXCEPTION 'network-wide Green Paper projection returned % rows, expected one',
                network_rows;
        END IF;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _financial_resilience_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in FINANCIAL_RESILIENCE_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_capital_efficiency_summary,
        kokonut_agent_source.v_public_regenerative_outcome_summary
        TO kokonut_agent_financial_resilience_reader;
    GRANT SELECT ON public.ai_summary, public.financial_sustainability_plan,
        public.green_paper_publication_review
        TO kokonut_agent_financial_resilience_reader,
           kokonut_agent_financial_resilience_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_financial_resilience_reader,
           kokonut_agent_financial_resilience_login;
    """


def _bio_factory_source_projection_fixture() -> str:
    tables = (
        "bio_factory_batch",
        "bio_input_provenance",
        "bio_recipe_library",
        "bio_factory_quality_test",
    )
    return "\n".join(
        f"INSERT INTO public.{table} (id, location_id, status) "
        f"VALUES ('e0000000-0000-4000-8000-{index:012d}', "
        f"'{OTHER_LOCATION_ID}', 'published');"
        for index, table in enumerate(tables, start=970)
    )


def _bio_factory_source_scope_acceptance() -> str:
    all_views_sql = ", ".join(f"'{name}'" for name in BIO_FACTORY_SOURCE_VIEW_NAMES)
    location_views_sql = ", ".join(f"'{name}'" for name in BIO_FACTORY_LOCATION_VIEW_NAMES)
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{BIO_FACTORY_SOURCE_WORKER_ID}', 'agent-bio-factory-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{BIO_FACTORY_SOURCE_WORKER_ID}', '{BIO_FACTORY_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{BIO_FACTORY_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic Bio Factory source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.unnest(ARRAY[{all_views_sql}]::TEXT[]) AS approved(view_name)
             WHERE NOT has_table_privilege(
                 'kokonut_agent_bio_factory_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name), 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_reader',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name), 'SELECT'
             ) OR has_table_privilege(
                 'kokonut_agent_summary_source_login',
                 pg_catalog.format('kokonut_agent_source.%I', approved.view_name), 'SELECT'
             )
        ) OR has_table_privilege(
            'kokonut_agent_bio_factory_reader',
            'kokonut_agent_source.v_public_financial_sustainability_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_bio_factory_reader', 'public.bio_factory_batch', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_bio_factory_login',
            'public.bio_regional_input_availability', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_bio_factory_reader', 'public.ai_summary', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_bio_factory_login', 'kokonut_agent_source', 'USAGE'
        ) OR has_function_privilege(
            'kokonut_agent_bio_factory_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'Bio Factory roles exceed their task source contract';
        END IF;
    END $$;

    SET ROLE kokonut_agent_bio_factory_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_bio_factory_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{all_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'Bio Factory view % returned rows without signed context', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{BIO_FACTORY_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_bio_factory_reader;
    DO $$
    DECLARE view_name TEXT; own_rows BIGINT; foreign_rows BIGINT; network_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{location_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO own_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1',
                view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF own_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'Bio Factory view % violated signed location scope (own %, foreign %)',
                    view_name, own_rows, foreign_rows;
            END IF;
        END LOOP;
        SELECT count(*) INTO network_rows
          FROM kokonut_agent_source.v_public_bio_regional_input_summary;
        IF network_rows <> 1 THEN
            RAISE EXCEPTION 'network-wide regional input view returned %, expected one', network_rows;
        END IF;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _bio_factory_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}" for name in BIO_FACTORY_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_financial_sustainability_summary,
        kokonut_agent_source.v_public_gnh_alignment_summary
        TO kokonut_agent_bio_factory_reader;
    GRANT SELECT ON public.ai_summary, public.bio_factory_batch,
        public.bio_input_provenance, public.bio_recipe_library,
        public.bio_factory_quality_test, public.bio_regional_input_availability
        TO kokonut_agent_bio_factory_reader,
           kokonut_agent_bio_factory_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_bio_factory_reader,
           kokonut_agent_bio_factory_login;
    """


def _open_source_capitalist_projection_fixture() -> str:
    """Add synthetic null-scope and foreign rows to all mixed-scope inputs."""
    return f"""
    INSERT INTO public.adoption_barrier_assessment (id, location_id, status) VALUES
        ('e0000000-0000-4000-8000-000000000810', '{OTHER_LOCATION_ID}', 'published'),
        ('e0000000-0000-4000-8000-000000000811', NULL, 'published');
    INSERT INTO public.perpetual_value_stress_test (id, location_id, status) VALUES
        ('e0000000-0000-4000-8000-000000000812', '{OTHER_LOCATION_ID}', 'published'),
        ('e0000000-0000-4000-8000-000000000813', NULL, 'published');
    """


def _open_source_capitalist_source_scope_acceptance() -> str:
    view_names_sql = ", ".join(
        f"'{name}'" for name in OPEN_SOURCE_CAPITALIST_SOURCE_VIEW_NAMES
    )
    location_views_sql = ", ".join(
        f"'{name}'" for name in OPEN_SOURCE_CAPITALIST_LOCATION_VIEW_NAMES
    )
    network_views_sql = ", ".join(
        f"'{name}'" for name in OPEN_SOURCE_CAPITALIST_SOURCE_VIEW_NAMES[3:]
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{OPEN_SOURCE_CAPITALIST_SOURCE_WORKER_ID}', 'agent-open-source-capitalist-source')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{OPEN_SOURCE_CAPITALIST_SOURCE_WORKER_ID}', '{OPEN_SOURCE_CAPITALIST_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{OPEN_SOURCE_CAPITALIST_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic Open Source Capitalist acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    DO $$
    DECLARE view_name TEXT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            IF has_table_privilege(
                'kokonut_agent_summary_source_reader',
                pg_catalog.format('kokonut_agent_source.%I', view_name), 'SELECT'
            ) OR has_table_privilege(
                'kokonut_agent_summary_source_login',
                pg_catalog.format('kokonut_agent_source.%I', view_name), 'SELECT'
            ) OR NOT has_table_privilege(
                'kokonut_agent_open_source_capitalist_reader',
                pg_catalog.format('kokonut_agent_source.%I', view_name), 'SELECT'
            ) THEN
                RAISE EXCEPTION 'Open Source Capitalist projection % has incorrect task/shared grants', view_name;
            END IF;
        END LOOP;
        IF has_table_privilege(
            'kokonut_agent_open_source_capitalist_login',
            'kokonut_agent_source.v_public_farm_launch_unit_economics', 'SELECT'
        ) OR has_schema_privilege(
            'kokonut_agent_open_source_capitalist_login', 'kokonut_agent_source', 'USAGE'
        ) OR NOT has_function_privilege(
            'kokonut_agent_open_source_capitalist_login',
            'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
        ) OR has_function_privilege(
            'kokonut_agent_open_source_capitalist_login',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) OR NOT has_function_privilege(
            'kokonut_agent_open_source_capitalist_reader',
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.ai_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader',
            'kokonut_agent_source.v_public_federation_protocol', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader',
            'kokonut_agent_source.v_public_farm_launch_unit_economics', 'UPDATE'
        ) OR has_schema_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'kokonut_agent_source', 'CREATE'
        ) THEN
            RAISE EXCEPTION 'Open Source Capitalist reader/login exceeds its task contract';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.farm_launch_unit_economics', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.adoption_barrier_assessment', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.perpetual_value_stress_test', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.network_scaling_target', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_open_source_capitalist_reader', 'public.open_source_impact_artifact', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'Open Source Capitalist reader can select a raw source table';
        END IF;
    END $$;

    SET ROLE kokonut_agent_open_source_capitalist_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_open_source_capitalist_reader;
    DO $$
    DECLARE view_name TEXT; visible_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{view_names_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO visible_rows;
            IF visible_rows <> 0 THEN
                RAISE EXCEPTION 'Open Source Capitalist projection % returned rows without signed context', view_name;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{OPEN_SOURCE_CAPITALIST_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_open_source_capitalist_reader;
    DO $$
    DECLARE
        view_name TEXT;
        owned_rows BIGINT;
        shared_rows BIGINT;
        foreign_rows BIGINT;
    BEGIN
        FOREACH view_name IN ARRAY ARRAY[{location_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1', view_name
            ) INTO owned_rows USING '{LOCATION_ID}'::UUID;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id IS NULL', view_name
            ) INTO shared_rows;
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I WHERE location_id = $1', view_name
            ) INTO foreign_rows USING '{OTHER_LOCATION_ID}'::UUID;
            IF owned_rows <> 1 OR shared_rows <> 1 OR foreign_rows <> 0 THEN
                RAISE EXCEPTION 'Open Source Capitalist mixed projection % violated location/network scope (owned %, shared %, foreign %)',
                    view_name, owned_rows, shared_rows, foreign_rows;
            END IF;
        END LOOP;
        FOREACH view_name IN ARRAY ARRAY[{network_views_sql}]::TEXT[] LOOP
            EXECUTE pg_catalog.format(
                'SELECT count(*) FROM kokonut_agent_source.%I', view_name
            ) INTO owned_rows;
            IF owned_rows <> 1 THEN
                RAISE EXCEPTION 'Open Source Capitalist network projection % returned %, expected one',
                    view_name, owned_rows;
            END IF;
        END LOOP;
    END $$;
    ROLLBACK;
    RESET ROLE;
    """


def _open_source_capitalist_source_stale_grants() -> str:
    views = ", ".join(
        f"kokonut_agent_source.{name}"
        for name in OPEN_SOURCE_CAPITALIST_SOURCE_VIEW_NAMES
    )
    return f"""
    GRANT SELECT ON {views}
        TO PUBLIC, kokonut_agent_summary_source_reader,
           kokonut_agent_summary_source_login;
    GRANT SELECT ON kokonut_agent_source.v_public_anti_capture_governance_policy
        TO kokonut_agent_open_source_capitalist_reader;
    GRANT SELECT ON public.ai_summary, public.farm_launch_unit_economics,
        public.adoption_barrier_assessment, public.perpetual_value_stress_test,
        public.network_scaling_target, public.open_source_impact_artifact
        TO kokonut_agent_open_source_capitalist_reader,
           kokonut_agent_open_source_capitalist_login;
    GRANT CREATE ON SCHEMA public, kokonut_security, kokonut_agent_source
        TO kokonut_agent_open_source_capitalist_reader,
           kokonut_agent_open_source_capitalist_login;
    """



def _source_reader_acceptance() -> str:
    approved_view_list = ", ".join(f"'{view_name}'" for view_name in SOURCE_READER_VIEWS)
    approved_metadata = "'geography_columns', 'geometry_columns', 'spatial_ref_sys'"
    return f"""
    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_source_login;
    DO $$
    BEGIN
        IF current_user <> 'kokonut_agent_summary_source_login' THEN
            RAISE EXCEPTION 'source login role was not selected';
        END IF;
        IF has_table_privilege(
            current_user,
            (SELECT relation.oid
               FROM pg_catalog.pg_class AS relation
               JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = relation.relnamespace
              WHERE namespace.nspname = 'kokonut_agent_source'
                AND relation.relname = 'v_public_capital_efficiency_summary'),
            'SELECT'
        ) THEN
            RAISE EXCEPTION 'NOINHERIT source login unexpectedly inherited scoped-reader privileges';
        END IF;
        IF has_table_privilege('kokonut_agent_summary_source_reader', 'public.ai_summary', 'SELECT') THEN
            RAISE EXCEPTION 'source reader can select private ai_summary rows';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_source_reader',
            'kokonut_security.worker_credential', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'source reader can inspect worker credentials';
        END IF;
        IF has_function_privilege(
            current_user,
            'kokonut_security.current_worker_scope(text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'source login can use worker-scope inspection directly';
        END IF;
        IF NOT has_function_privilege(
            current_user,
            'kokonut_security.set_worker_tenant_context(text,uuid,text,text)', 'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'source login cannot establish its signed read scope';
        END IF;
        IF has_table_privilege('kokonut_agent_summary_source_reader', 'public.v_public_capital_efficiency_summary', 'SELECT') THEN
            RAISE EXCEPTION 'source reader can bypass the location-scoped wrapper';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'kokonut_agent_source'
               AND relation.relname::text = ANY(ARRAY[{approved_view_list}]::text[])
               AND NOT has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'SELECT'
               )
        ) THEN
            RAISE EXCEPTION 'source reader is missing approved scoped view grants: %', (
                SELECT pg_catalog.string_agg(
                    relation.relname::TEXT, ', ' ORDER BY relation.relname::TEXT
                )
                  FROM pg_catalog.pg_class AS relation
                  JOIN pg_catalog.pg_namespace AS namespace
                    ON namespace.oid = relation.relnamespace
                 WHERE namespace.nspname = 'kokonut_agent_source'
                   AND relation.relname::TEXT = ANY(ARRAY[{approved_view_list}]::TEXT[])
                   AND NOT has_table_privilege(
                       'kokonut_agent_summary_source_reader', relation.oid, 'SELECT'
                   )
            );
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND has_table_privilege(
                   'kokonut_agent_summary_source_reader', relation.oid, 'SELECT'
               )
               AND relation.relname::text <> ALL (ARRAY[{approved_metadata}]::text[])
        ) THEN
            RAISE EXCEPTION 'source reader can select a public relation directly';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND (
                   has_table_privilege('kokonut_agent_summary_source_reader', relation.oid, 'INSERT')
                   OR has_table_privilege('kokonut_agent_summary_source_reader', relation.oid, 'UPDATE')
                   OR has_table_privilege('kokonut_agent_summary_source_reader', relation.oid, 'DELETE')
                   OR has_table_privilege('kokonut_agent_summary_source_reader', relation.oid, 'TRUNCATE')
               )
        ) THEN
            RAISE EXCEPTION 'source reader has public write privileges';
        END IF;
        IF has_schema_privilege('kokonut_agent_summary_source_reader', 'public', 'CREATE') THEN
            RAISE EXCEPTION 'source reader can create public objects';
        END IF;
        IF has_schema_privilege('kokonut_agent_summary_source_reader', 'kokonut_agent_source', 'CREATE') THEN
            RAISE EXCEPTION 'source reader can replace scoped views';
        END IF;
    END;
    $$;
    SET LOCAL ROLE kokonut_agent_summary_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_public_algorithmic_redistribution_mechanism;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'scoped source view returned rows without signed context';
        END IF;
        BEGIN
            PERFORM 1 FROM public.v_public_capital_efficiency_summary;
            RAISE EXCEPTION 'source reader can query an unfiltered source view';
        EXCEPTION WHEN insufficient_privilege THEN
            NULL;
        END;
    END;
    $$;
    ROLLBACK;
    """


def _source_reader_scope_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{SOURCE_WORKER_ID}', 'agent-summary-source');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{SOURCE_WORKER_ID}', '{SOURCE_CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic source-reader acceptance fixture'
    );

    SET ROLE kokonut_agent_summary_source_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_public_algorithmic_redistribution_mechanism;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'source rows were visible before context setup';
        END IF;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_source_reader;
    DO $$
    DECLARE
        exact_count BIGINT;
        mixed_count BIGINT;
        network_count BIGINT;
    BEGIN
        SELECT count(*) INTO exact_count
          FROM kokonut_agent_source.v_public_algorithmic_redistribution_mechanism
         WHERE location_id = '{LOCATION_ID}';
        IF exact_count <> 1 THEN
            RAISE EXCEPTION 'exact-location source wrapper returned % rows, expected 1', exact_count;
        END IF;
        SELECT count(*) INTO mixed_count
          FROM kokonut_agent_source.v_public_anti_capture_governance_policy;
        IF mixed_count <> 2 THEN
            RAISE EXCEPTION 'mixed-scope source wrapper returned % rows, expected one location and one unassigned row', mixed_count;
        END IF;
        SELECT count(*) INTO network_count
          FROM kokonut_agent_source.v_public_federation_protocol;
        IF network_count <> 1 THEN
            RAISE EXCEPTION 'network source wrapper requires context but preserves its public catalogue';
        END IF;
        BEGIN
            PERFORM 1 FROM public.v_public_capital_efficiency_summary;
            RAISE EXCEPTION 'source reader can query the original unfiltered view';
        EXCEPTION WHEN insufficient_privilege THEN
            NULL;
        END;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{SOURCE_CREDENTIAL_HASH}', '{OTHER_LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_public_algorithmic_redistribution_mechanism;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'location without a worker grant acquired source access';
        END IF;
    END;
    $$;
    ROLLBACK;
    """


def _ebf_source_scope_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{EBF_SOURCE_WORKER_ID}', 'agent-ebf-source');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{EBF_SOURCE_WORKER_ID}', '{EBF_SOURCE_CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{EBF_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ebf_scorecard', 'read', 'synthetic EBF source-reader acceptance fixture'
    );

    SET ROLE kokonut_agent_ebf_source_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_ebf_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
            exposed_columns TEXT[];
    BEGIN
        SELECT pg_catalog.array_agg(attribute.attname::text ORDER BY attribute.attnum)
          INTO exposed_columns
          FROM pg_catalog.pg_attribute AS attribute
          JOIN pg_catalog.pg_class AS relation ON relation.oid = attribute.attrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'kokonut_agent_source'
           AND relation.relname = 'v_ebf_evidence_gap_summary'
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped;
        IF exposed_columns IS DISTINCT FROM ARRAY[
            'scorecard_id', 'location_id', 'pillar_key', 'pillar_name',
            'normalized_score', 'confidence_level', 'evidence_maturity_level',
            'evidence_maturity_label', 'evidence_count',
            'public_safe_evidence_count', 'gap_status'
        ]::text[] THEN
            RAISE EXCEPTION 'EBF wrapper exposed an unexpected column set: %', exposed_columns;
        END IF;
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_ebf_evidence_gap_summary;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'EBF source was visible without signed location context';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_ebf_source_reader',
            'public.v_ebf_evidence_gap_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_ebf_source_login',
            'kokonut_agent_source.v_ebf_evidence_gap_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'EBF reader can bypass its signed wrapper or source login bypasses NOLOGIN role';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_ebf_source_reader',
            'kokonut_agent_source.v_ebf_evidence_gap_summary', 'INSERT'
        ) OR has_table_privilege(
            'kokonut_agent_ebf_source_reader',
            'kokonut_agent_source.v_ebf_evidence_gap_summary', 'UPDATE'
        ) OR has_table_privilege(
            'kokonut_agent_ebf_source_reader',
            'kokonut_agent_source.v_ebf_evidence_gap_summary', 'DELETE'
        ) THEN
            RAISE EXCEPTION 'EBF source reader has write privileges';
        END IF;
        BEGIN
            PERFORM 1 FROM public.v_ebf_evidence_gap_summary;
            RAISE EXCEPTION 'EBF reader can query the raw public source view';
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{EBF_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ebf_scorecard', 'read'
    );
    SET LOCAL ROLE kokonut_agent_ebf_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
            foreign_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_ebf_evidence_gap_summary
         WHERE scorecard_id = 'a0000000-0000-4000-8000-000000000101';
        SELECT count(*) INTO foreign_rows
          FROM kokonut_agent_source.v_ebf_evidence_gap_summary
         WHERE location_id <> '{LOCATION_ID}';
        IF visible_rows <> 1 OR foreign_rows <> 0 THEN
            RAISE EXCEPTION 'signed EBF wrapper scope mismatch: visible %, foreign %',
                visible_rows, foreign_rows;
        END IF;
        IF has_table_privilege(
            'kokonut_agent_ebf_source_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'EBF role can select synthesis source views';
        END IF;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{EBF_SOURCE_CREDENTIAL_HASH}', '{OTHER_LOCATION_ID}', 'ebf_scorecard', 'read'
    );
    SET LOCAL ROLE kokonut_agent_ebf_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows
          FROM kokonut_agent_source.v_ebf_evidence_gap_summary;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'location without an EBF worker grant acquired source access';
        END IF;
    END;
    $$;
    ROLLBACK;
    RESET ROLE;
    """


def _cids_source_acceptance() -> str:
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{CIDS_SOURCE_WORKER_ID}', 'agent-cids-source');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{CIDS_SOURCE_WORKER_ID}', '{CIDS_SOURCE_CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{CIDS_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'cids_export', 'read', 'synthetic CIDS source-reader acceptance fixture'
    );

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CIDS_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'cids_export', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_source_view_owner;
    DO $$
    DECLARE
        base_rows BIGINT;
        scope_rows BIGINT;
        wrapper_rows BIGINT;
    BEGIN
        SELECT count(*) INTO base_rows FROM public.location
         WHERE id = '{LOCATION_ID}';
        SELECT count(*) INTO scope_rows
          FROM kokonut_security.current_worker_scope('cids_export', 'read')
         WHERE location_id = '{LOCATION_ID}';
        SELECT count(*) INTO wrapper_rows FROM kokonut_agent_source.cids_location;
        IF base_rows <> 1 OR scope_rows <> 1 OR wrapper_rows <> 1 THEN
            RAISE EXCEPTION 'CIDS view-owner probe: base %, scope %, wrapper %',
                base_rows, scope_rows, wrapper_rows;
        END IF;
    END;
    $$;
    ROLLBACK;

    SET ROLE kokonut_agent_cids_source_login;
    BEGIN;
    SET LOCAL ROLE kokonut_agent_cids_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM kokonut_agent_source.cids_location;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'CIDS source rows were visible without signed context';
        END IF;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CIDS_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_cids_source_reader;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM kokonut_agent_source.cids_location;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'ai_summary grant unexpectedly authorized CIDS projection';
        END IF;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{CIDS_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'cids_export', 'read'
    );
    SET LOCAL ROLE kokonut_agent_cids_source_reader;
    DO $$
    DECLARE
        row_count BIGINT;
        foreign_rows BIGINT;
        feedback_count BIGINT;
        signed_scope_count BIGINT;
        signed_location UUID;
        exposed_columns TEXT[];
        denied BOOLEAN := FALSE;
    BEGIN
        SELECT count(*) INTO signed_scope_count
          FROM kokonut_security.current_worker_scope('cids_export', 'read');
        SELECT location_id INTO signed_location
          FROM kokonut_security.current_worker_scope('cids_export', 'read');
        SELECT count(*) INTO row_count FROM kokonut_agent_source.cids_location;
        SELECT count(*) INTO foreign_rows
          FROM kokonut_agent_source.cids_location WHERE id <> '{LOCATION_ID}';
        IF row_count <> 1 OR foreign_rows <> 0 THEN
            RAISE EXCEPTION 'CIDS location wrapper mismatch: signed scopes %, signed location %, rows %, foreign %',
                signed_scope_count, signed_location, row_count, foreign_rows;
        END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_stakeholder_outcome
         WHERE location_id <> '{LOCATION_ID}';
        IF row_count <> 0 THEN RAISE EXCEPTION 'CIDS outcomes crossed location scope'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_stakeholder_outcome
         WHERE location_id = '{LOCATION_ID}' AND status IN ('verified', 'published');
        IF row_count <> 1 THEN RAISE EXCEPTION 'CIDS scoped outcome projection is incomplete'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_farm_impact_mapping
         WHERE location_id <> '{LOCATION_ID}';
        IF row_count <> 0 THEN RAISE EXCEPTION 'CIDS impact mappings crossed location scope'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_farm_impact_mapping
         WHERE location_id = '{LOCATION_ID}' AND status IN ('verified', 'published');
        IF row_count <> 1 THEN RAISE EXCEPTION 'CIDS scoped impact mapping is incomplete'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_metric_value
         WHERE location_id <> '{LOCATION_ID}';
        IF row_count <> 0 THEN RAISE EXCEPTION 'CIDS metric values crossed location scope'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_metric_value
         WHERE location_id = '{LOCATION_ID}' AND verified AND active;
        IF row_count <> 1 THEN RAISE EXCEPTION 'CIDS scoped metric projection is incomplete'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_impact_claim
         WHERE location_id <> '{LOCATION_ID}';
        IF row_count <> 0 THEN RAISE EXCEPTION 'CIDS impact claims crossed location scope'; END IF;
        SELECT count(*) INTO row_count
          FROM kokonut_agent_source.cids_impact_claim
         WHERE location_id = '{LOCATION_ID}' AND status IN ('verified', 'published');
        IF row_count <> 1 THEN RAISE EXCEPTION 'CIDS scoped impact claim is incomplete'; END IF;
        SELECT count(*) INTO feedback_count
          FROM kokonut_agent_source.cids_stakeholder_feedback;
        IF feedback_count <> 1 THEN
            RAISE EXCEPTION 'CIDS public-feedback allowlist returned %, expected one consented synthetic row',
                feedback_count;
        END IF;
        SELECT pg_catalog.array_agg(attribute.attname::text ORDER BY attribute.attnum)
          INTO exposed_columns
          FROM pg_catalog.pg_attribute AS attribute
          JOIN pg_catalog.pg_class AS relation ON relation.oid = attribute.attrelid
          JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'kokonut_agent_source'
           AND relation.relname = 'cids_stakeholder_feedback'
           AND attribute.attnum > 0 AND NOT attribute.attisdropped;
        IF exposed_columns IS DISTINCT FROM ARRAY[
            'id', 'location_id', 'feedback_date', 'stakeholder_group'
        ]::text[] THEN
            RAISE EXCEPTION 'CIDS feedback wrapper exposed unexpected columns: %', exposed_columns;
        END IF;
        IF has_table_privilege(
            'kokonut_agent_cids_source_reader', 'public.stakeholder_feedback', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_cids_source_reader', 'public.impact_claim', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_cids_source_login',
            'kokonut_agent_source.cids_location', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'CIDS source identities can bypass projection views';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_cids_source_reader',
            'kokonut_agent_source.cids_location', 'INSERT'
        ) OR has_table_privilege(
            'kokonut_agent_cids_source_reader',
            'kokonut_agent_source.cids_location', 'UPDATE'
        ) OR has_table_privilege(
            'kokonut_agent_cids_source_reader',
            'kokonut_agent_source.cids_location', 'DELETE'
        ) THEN
            RAISE EXCEPTION 'CIDS projection reader has write privileges';
        END IF;
        BEGIN
            PERFORM 1 FROM public.stakeholder_feedback;
        EXCEPTION WHEN insufficient_privilege THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'CIDS reader selected raw feedback'; END IF;
        IF has_table_privilege(
            'kokonut_agent_cids_source_reader',
            'kokonut_agent_source.v_public_capital_efficiency_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'CIDS role can select synthesis source views';
        END IF;
    END;
    $$;
    ROLLBACK;
    RESET ROLE;
    """


def _deterministic_source_reader_acceptance() -> str:
    wrappers = DETERMINISTIC_SOURCE_TABLES
    wrapper_read_checks = " OR ".join(
        "NOT has_table_privilege('kokonut_agent_summary_deterministic_reader', "
        "(SELECT relation.oid FROM pg_catalog.pg_class AS relation "
        "JOIN pg_catalog.pg_namespace AS namespace "
        "ON namespace.oid = relation.relnamespace "
        "WHERE namespace.nspname = 'kokonut_agent_source' "
        f"AND relation.relname = '{wrapper_name}'), 'SELECT')"
        for wrapper_name in wrappers
    )
    raw_read_checks = " OR ".join(
        "has_table_privilege('kokonut_agent_summary_deterministic_reader', "
        f"'public.{table_name}', 'SELECT')"
        for table_name in DETERMINISTIC_SOURCE_TABLES
    )
    wrapper_reads = "\n".join(
        f"PERFORM count(*) FROM kokonut_agent_source.{wrapper_name};"
        for wrapper_name in wrappers
    )
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{DETERMINISTIC_SOURCE_WORKER_ID}', 'agent-summary-deterministic-source');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{DETERMINISTIC_SOURCE_WORKER_ID}', '{DETERMINISTIC_SOURCE_CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{DETERMINISTIC_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic deterministic source-reader fixture'
    );

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_deterministic_source_login;
    DO $$
    DECLARE deterministic_wrapper_oid OID;
    BEGIN
        SELECT relation.oid INTO deterministic_wrapper_oid
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'kokonut_agent_source'
           AND relation.relname = 'harvest_event';
        IF current_user <> 'kokonut_agent_summary_deterministic_source_login' THEN
            RAISE EXCEPTION 'deterministic source login role was not selected';
        END IF;
        IF has_table_privilege(current_user, 'public.harvest_event', 'SELECT')
           OR has_table_privilege(
               current_user, deterministic_wrapper_oid, 'SELECT'
           ) THEN
            RAISE EXCEPTION 'deterministic source login can bypass its reader role';
        END IF;
        IF has_function_privilege(
            current_user,
            'kokonut_security.current_worker_scope(text,text)',
            'EXECUTE'
        ) OR NOT has_function_privilege(
            current_user,
            'kokonut_security.set_worker_tenant_context(text,uuid,text,text)',
            'EXECUTE'
        ) THEN
            RAISE EXCEPTION 'deterministic source login has broader than setter-only function access';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_deterministic_reader', 'public.ai_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'deterministic source reader can select private ai_summary rows';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND has_table_privilege(
                   'kokonut_agent_summary_deterministic_reader', relation.oid, 'SELECT'
               )
               AND relation.relname::text <> ALL (
                   ARRAY['geography_columns', 'geometry_columns', 'spatial_ref_sys']::text[]
               )
        ) THEN
            RAISE EXCEPTION 'deterministic source reader retains raw public relation access';
        END IF;
        IF {raw_read_checks} THEN
            RAISE EXCEPTION 'deterministic source reader can select a raw source relation';
        END IF;
        IF {wrapper_read_checks} THEN
            RAISE EXCEPTION 'deterministic source reader is missing a scoped view grant';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND (
                   has_table_privilege('kokonut_agent_summary_deterministic_reader', relation.oid, 'INSERT')
                   OR has_table_privilege('kokonut_agent_summary_deterministic_reader', relation.oid, 'UPDATE')
                   OR has_table_privilege('kokonut_agent_summary_deterministic_reader', relation.oid, 'DELETE')
                   OR has_table_privilege('kokonut_agent_summary_deterministic_reader', relation.oid, 'TRUNCATE')
               )
        ) THEN
            RAISE EXCEPTION 'deterministic source reader has public write privileges';
        END IF;
        IF has_schema_privilege(
            'kokonut_agent_summary_deterministic_reader', 'kokonut_agent_source', 'CREATE'
        ) OR has_schema_privilege(
            'kokonut_agent_summary_deterministic_source_login', 'kokonut_agent_source', 'CREATE'
        ) OR has_schema_privilege(
            'kokonut_agent_summary_deterministic_source_login', 'public', 'CREATE'
        ) THEN
            RAISE EXCEPTION 'deterministic source roles retain schema CREATE privileges';
        END IF;
    END;
    $$;

    SET LOCAL ROLE kokonut_agent_summary_deterministic_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM harvest_event;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'deterministic location data was visible without signed context';
        END IF;
        BEGIN
            PERFORM 1 FROM public.harvest_event;
            RAISE EXCEPTION 'deterministic reader can query the raw public table';
        EXCEPTION WHEN insufficient_privilege THEN
            NULL;
        END;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_deterministic_source_login;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{DETERMINISTIC_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_deterministic_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE exact_count BIGINT; crop_count BIGINT;
            foreign_row BOOLEAN;
    BEGIN
        {wrapper_reads}
        SELECT count(*) INTO exact_count FROM harvest_event;
        IF exact_count <> 1 THEN
            RAISE EXCEPTION 'deterministic view returned % harvest rows; expected only the signed location row', exact_count;
        END IF;
        SELECT EXISTS (
            SELECT 1 FROM harvest_event
             WHERE id = 'e0000000-0000-4000-8000-000000000002'
        ) INTO foreign_row;
        IF foreign_row THEN
            RAISE EXCEPTION 'deterministic view exposed another location harvest';
        END IF;
        SELECT count(*) INTO crop_count FROM crop;
        IF crop_count <> 1 THEN
            RAISE EXCEPTION 'shared crop catalog is unavailable under valid signed scope';
        END IF;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_deterministic_source_login;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{DETERMINISTIC_SOURCE_CREDENTIAL_HASH}', '{OTHER_LOCATION_ID}', 'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_deterministic_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM harvest_event;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'location without a deterministic worker grant acquired source rows';
        END IF;
    END;
    $$;
    ROLLBACK;
    """


def _summary_inspection_acceptance() -> str:
    own_summary_id = "c0000000-0000-4000-8000-000000000201"
    foreign_summary_id = "c0000000-0000-4000-8000-000000000202"
    network_summary_id = "c0000000-0000-4000-8000-000000000203"
    expected_content = "Synthetic location summary " + "x" * 100
    expected_digest = hashlib.sha256(expected_content.encode("utf-8")).hexdigest()
    return f"""
    INSERT INTO public.ai_summary (
        id, subject_type, subject_id, summary_type, content,
        source_tables, model_version, status, created_at
    ) VALUES
      ('{own_summary_id}', 'location', '{LOCATION_ID}', 'operations',
       'Synthetic location summary ' || repeat('x', 100), ARRAY['harvest_event'],
       'synthetic-v1', 'draft', '2026-10-22 12:00:00+00'),
      ('{foreign_summary_id}', 'location', '{OTHER_LOCATION_ID}', 'financial',
       'Synthetic foreign summary must remain hidden.', ARRAY['expense_event'],
       'synthetic-v1', 'draft', '2026-10-22 13:00:00+00'),
      ('{network_summary_id}', 'network', '{LOCATION_ID}', 'combined',
       'Non-location summary must remain hidden.', ARRAY['harvest_event'],
       'synthetic-v1', 'draft', '2026-10-22 14:00:00+00');

    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{INSPECTION_SOURCE_WORKER_ID}', 'agent-summary-inspection-source');
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{INSPECTION_SOURCE_WORKER_ID}', '{INSPECTION_SOURCE_CREDENTIAL_HASH}');
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{INSPECTION_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'ai_summary', 'read', 'synthetic summary-inspection fixture'
    );

    ALTER TABLE public.ai_summary ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.ai_summary FORCE ROW LEVEL SECURITY;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_inspection_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM ai_summary_list;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'summary list exposed rows without a signed grant';
        END IF;
        SELECT count(*) INTO visible_rows FROM ai_summary_digest;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'summary digest view exposed rows without a signed grant';
        END IF;
        BEGIN
            PERFORM 1 FROM public.ai_summary;
            RAISE EXCEPTION 'deterministic reader can query raw AI-summary content';
        EXCEPTION WHEN insufficient_privilege THEN
            NULL;
        END;
    END;
    $$;
    ROLLBACK;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_deterministic_reader;
    DO $$ BEGIN
        IF has_table_privilege(current_user, 'kokonut_agent_source.ai_summary_list', 'SELECT')
           OR has_table_privilege(current_user, 'kokonut_agent_source.ai_summary_digest', 'SELECT')
           OR has_table_privilege(current_user, 'kokonut_agent_source.ai_summary_inspection', 'SELECT') THEN
            RAISE EXCEPTION 'deterministic source reader retains inspection projections';
        END IF;
    END $$;
    ROLLBACK;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_summary_inspection_login;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{INSPECTION_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}',
        'ai_summary', 'read'
    );
    SET LOCAL ROLE kokonut_agent_summary_inspection_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$ DECLARE visible_rows BIGINT; preview TEXT; digest_value TEXT; digest_length INTEGER; BEGIN
        IF NOT (SELECT relrowsecurity AND relforcerowsecurity
                  FROM pg_catalog.pg_class
                 WHERE oid = 'public.ai_summary'::regclass) THEN
            RAISE EXCEPTION 'forced RLS was not active for summary view-owner acceptance';
        END IF;
        SELECT count(*) INTO visible_rows FROM ai_summary_list;
        IF visible_rows <> 2 THEN
            RAISE EXCEPTION 'summary list returned %, expected two exact-location rows including the legacy fixture', visible_rows;
        END IF;
        SELECT ai_summary_list.preview INTO preview
          FROM ai_summary_list
         WHERE id = '{own_summary_id}' AND location_id = '{LOCATION_ID}';
        IF preview IS NULL OR length(preview) <> 80
           OR preview <> LEFT('Synthetic location summary ' || repeat('x', 100), 80) THEN
            RAISE EXCEPTION 'summary list did not expose only its bounded preview';
        END IF;
        IF EXISTS (SELECT 1 FROM ai_summary_list
                    WHERE id IN ('{foreign_summary_id}', '{network_summary_id}')) THEN
            RAISE EXCEPTION 'summary list exposed a foreign or non-location row';
        END IF;
        SELECT content_sha256, content_length INTO digest_value, digest_length
          FROM ai_summary_digest
         WHERE id = '{own_summary_id}' AND location_id = '{LOCATION_ID}';
        IF digest_value IS DISTINCT FROM '{expected_digest}'
           OR digest_length IS DISTINCT FROM {len(expected_content)} THEN
            RAISE EXCEPTION 'exact-location digest metadata is incorrect';
        END IF;
        SELECT count(*) INTO visible_rows FROM ai_summary_digest
         WHERE id = '{foreign_summary_id}' AND location_id = '{LOCATION_ID}';
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'foreign summary ID was visible through digest view';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'public.ai_summary', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_inspection_login',
            'public.ai_summary', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'summary inspection roles retained raw-table SELECT';
        END IF;
        IF has_schema_privilege(
            'kokonut_agent_summary_inspection_login',
            'kokonut_agent_source', 'USAGE'
        ) OR has_table_privilege(
            'kokonut_agent_summary_inspection_login',
            'kokonut_agent_source.ai_summary_digest', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'summary source login can bypass the NOLOGIN reader';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'kokonut_agent_source.ai_summary_list', 'INSERT'
        ) OR has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'kokonut_agent_source.ai_summary_digest', 'UPDATE'
        ) THEN
            RAISE EXCEPTION 'summary inspection reader has write privileges';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'kokonut_agent_source.ai_summary_list', 'SELECT'
        ) IS NOT TRUE OR has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'kokonut_agent_source.ai_summary_digest', 'SELECT'
        ) IS NOT TRUE THEN
            RAISE EXCEPTION 'inspection reader is missing a signed projection';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_attribute
             WHERE attrelid = 'kokonut_agent_source.ai_summary_digest'::regclass
               AND attname = 'content' AND NOT attisdropped
        ) THEN
            RAISE EXCEPTION 'digest projection exposes raw summary content';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_summary_inspection_reader',
            'kokonut_agent_source.harvest_event', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'inspection reader can access deterministic source data';
        END IF;
    END;
    $$;
    COMMIT;
    RESET ROLE;

    ALTER TABLE public.ai_summary NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.ai_summary DISABLE ROW LEVEL SECURITY;
    """


def _delphi_agent_source_acceptance() -> str:
    study_id = "d1000000-0000-4000-8000-000000000001"
    return f"""
    INSERT INTO kokonut_security.worker_principal (id, principal_key)
    VALUES ('{DELPHI_SOURCE_WORKER_ID}', 'agent-delphi-source')
    ON CONFLICT (id) DO NOTHING;
    INSERT INTO kokonut_security.worker_credential (worker_id, credential_hash)
    VALUES ('{DELPHI_SOURCE_WORKER_ID}', '{DELPHI_SOURCE_CREDENTIAL_HASH}')
    ON CONFLICT (credential_hash) DO NOTHING;
    INSERT INTO kokonut_security.worker_scope_grant (
        worker_id, tenant_id, location_id, resource, action, granted_by
    ) VALUES (
        '{DELPHI_SOURCE_WORKER_ID}', '{TENANT_ID}', '{LOCATION_ID}',
        'delphi', 'read', 'synthetic Delphi source acceptance fixture'
    ) ON CONFLICT DO NOTHING;

    ALTER TABLE public.delphi_study ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_study FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_item ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_item FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_contribution ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_contribution FORCE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_panel_member ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.delphi_panel_member FORCE ROW LEVEL SECURITY;

    BEGIN;
    SET LOCAL ROLE kokonut_agent_delphi_source_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM delphi_live_summary;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'Delphi source was visible without signed location context';
        END IF;
        IF has_table_privilege(
            'kokonut_agent_delphi_source_reader',
            'public.delphi_contribution', 'SELECT'
        ) OR has_table_privilege(
            'kokonut_agent_delphi_source_login',
            'public.delphi_contribution', 'SELECT'
        ) THEN
            RAISE EXCEPTION 'Delphi source roles can query contribution rows directly';
        END IF;
        BEGIN
            PERFORM 1 FROM public.delphi_contribution;
            RAISE EXCEPTION 'Delphi reader queried raw participant contributions';
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        IF has_table_privilege(
            'kokonut_agent_delphi_source_reader',
            'kokonut_agent_source.delphi_live_summary', 'INSERT'
        ) OR has_table_privilege(
            'kokonut_agent_delphi_source_reader',
            'kokonut_agent_source.delphi_live_summary', 'UPDATE'
        ) OR has_table_privilege(
            'kokonut_agent_delphi_source_reader',
            'kokonut_agent_source.delphi_live_summary', 'DELETE'
        ) THEN
            RAISE EXCEPTION 'Delphi source reader has write access';
        END IF;
    END;
    $$;
    ROLLBACK;

    SET ROLE kokonut_agent_delphi_source_login;
    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{DELPHI_SOURCE_CREDENTIAL_HASH}', '{LOCATION_ID}', 'delphi', 'read'
    );
    SET LOCAL ROLE kokonut_agent_delphi_source_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE summary_row RECORD;
            public_item JSONB;
            suppressed_item JSONB;
            foreign_rows BIGINT;
    BEGIN
        IF NOT (SELECT relrowsecurity AND relforcerowsecurity
                  FROM pg_catalog.pg_class
                 WHERE oid = 'public.delphi_contribution'::regclass) THEN
            RAISE EXCEPTION 'forced RLS was not active on Delphi source tables';
        END IF;
        SELECT * INTO summary_row
          FROM delphi_live_summary
         WHERE study_id = '{study_id}' AND location_id = '{LOCATION_ID}';
        IF NOT FOUND OR summary_row.title <> 'Synthetic owned study'
           OR summary_row.panel_size_available IS NOT TRUE
           OR summary_row.panel_size <> 4 THEN
            RAISE EXCEPTION 'signed Delphi source did not return the exact own-location summary';
        END IF;
        SELECT elem INTO public_item
          FROM jsonb_array_elements(summary_row.items) AS elem
         WHERE elem ->> 'label' = 'Public-safe item';
        IF public_item ->> 'results_available' IS DISTINCT FROM 'true'
           OR public_item ->> 'participant_count' IS DISTINCT FROM '4'
           OR (public_item ->> 'median')::NUMERIC <> 0.4 THEN
            RAISE EXCEPTION 'consented Delphi aggregate did not match its public-safe fixture: %', public_item;
        END IF;
        SELECT elem INTO suppressed_item
          FROM jsonb_array_elements(summary_row.items) AS elem
         WHERE elem ->> 'label' = 'Below-floor item';
        IF suppressed_item ->> 'results_available' IS DISTINCT FROM 'false'
           OR suppressed_item ->> 'participant_count' IS NOT NULL
           OR suppressed_item ->> 'median' IS NOT NULL THEN
            RAISE EXCEPTION 'below-threshold Delphi scores were not suppressed: %', suppressed_item;
        END IF;
        IF summary_row.items::TEXT LIKE '%private-token%'
           OR summary_row.items::TEXT LIKE '%reasoning%' THEN
            RAISE EXCEPTION 'Delphi summary exposed participant identifiers or reasoning';
        END IF;
        SELECT count(*) INTO foreign_rows
          FROM delphi_live_summary
         WHERE location_id <> '{LOCATION_ID}';
        IF foreign_rows <> 0 THEN
            RAISE EXCEPTION 'Delphi source exposed a foreign location';
        END IF;
    END;
    $$;
    ROLLBACK;
    RESET ROLE;

    SET ROLE kokonut_agent_delphi_source_login;
    BEGIN;
    SELECT * FROM kokonut_security.set_worker_tenant_context(
        '{DELPHI_SOURCE_CREDENTIAL_HASH}', '{OTHER_LOCATION_ID}', 'delphi', 'read'
    );
    SET LOCAL ROLE kokonut_agent_delphi_source_reader;
    SET LOCAL search_path = kokonut_agent_source, public;
    DO $$
    DECLARE visible_rows BIGINT;
    BEGIN
        SELECT count(*) INTO visible_rows FROM delphi_live_summary;
        IF visible_rows <> 0 THEN
            RAISE EXCEPTION 'location without an active Delphi grant acquired source access';
        END IF;
    END;
    $$;
    ROLLBACK;
    RESET ROLE;
    """


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
                    'bio_factory_quality_test', 'bio_regional_input_availability'],
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
            ),
            'bio_regional_input_availability', jsonb_build_object(
                'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000801'),
                'row_count', 1, 'truncated', false, 'scope', 'network'
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
        ("financial_resilience", "resilience-agent-v1", [*ADDITIONAL_SOURCE_TABLES[9:12], "green_paper_publication_review"]),
        ("open_source_capitalist", "open-source-capitalist-agent-v1", [*ADDITIONAL_SOURCE_TABLES[12:], "network_scaling_target", "open_source_impact_artifact"]),
    ]
    id_by_table = {
        table: f"e0000000-0000-4000-8000-{index:012d}"
        for index, table in enumerate(ADDITIONAL_SOURCE_TABLES, start=501)
    }
    id_by_table.update({
        "network_scaling_target": "e0000000-0000-4000-8000-000000000802",
        "open_source_impact_artifact": "e0000000-0000-4000-8000-000000000803",
        "green_paper_publication_review": "e0000000-0000-4000-8000-000000000804",
    })
    non_location_scopes = {
        "farm_launch_unit_economics": "location_or_network",
        "adoption_barrier_assessment": "location_or_network",
        "perpetual_value_stress_test": "location_or_network",
            "network_scaling_target": "network",
            "open_source_impact_artifact": "network",
            "green_paper_publication_review": "network",
    }
    statements = []
    for group_index, (summary_type, model_version, source_tables) in enumerate(groups, start=1):
        request_id = f"d0000000-0000-4000-8000-{920 + group_index:012d}"
        source_array = ", ".join(f"'{table}'" for table in source_tables)
        payload_entries_list = []
        for table in source_tables:
            ids = [id_by_table[table]]
            if table == "farm_launch_unit_economics":
                ids.append("e0000000-0000-4000-8000-000000000807")
            ids_sql = ", ".join(f"'{record_id}'" for record_id in ids)
            scope = non_location_scopes.get(table)
            scope_sql = f", 'scope', '{scope}'" if scope else ""
            payload_entries_list.append(
                f"'{table}', jsonb_build_object('record_ids', jsonb_build_array({ids_sql}), "
                f"'row_count', {len(ids)}, 'truncated', false{scope_sql})"
            )
        payload_entries = ", ".join(payload_entries_list)
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
    network_view_array = ", ".join(f"'{view}'" for view in NETWORK_SOURCE_VIEWS.values())
    table_array = ", ".join(
        f"'{table}'" for table in (*ADDITIONAL_SOURCE_TABLES, *NETWORK_SOURCE_VIEWS)
    )
    denial_checks = f"""
        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'open_source_capitalist', 'Mixed-scope cross-location denial.',
              ARRAY['farm_launch_unit_economics'], 'open-source-capitalist-agent-v1',
              'd0000000-0000-4000-8000-000000000929'
          );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', draft_record.summary_id,
                'd0000000-0000-4000-8000-000000000929',
                jsonb_build_object('farm_launch_unit_economics', jsonb_build_object(
                    'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000809'),
                    'row_count', 1, 'truncated', false, 'scope', 'location_or_network'
                ))
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'mixed-scope manifest accepted another location ID'; END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id, 'd0000000-0000-4000-8000-000000000929'
        );
        IF attached <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'rejected mixed-scope attachment left a partial manifest';
        END IF;

        SELECT * INTO STRICT draft_record
          FROM kokonut_security.create_location_ai_summary_worker_draft(
              '{LOCATION_ID}', 'open_source_capitalist', 'Network scope mismatch denial.',
              ARRAY['network_scaling_target'], 'open-source-capitalist-agent-v1',
              'd0000000-0000-4000-8000-000000000930'
          );
        denied := FALSE;
        BEGIN
            PERFORM kokonut_security.set_location_ai_summary_source_references(
                '{LOCATION_ID}', draft_record.summary_id,
                'd0000000-0000-4000-8000-000000000930',
                jsonb_build_object('network_scaling_target', jsonb_build_object(
                    'record_ids', jsonb_build_array('e0000000-0000-4000-8000-000000000802'),
                    'row_count', 1, 'truncated', false, 'scope', 'location'
                ))
            );
        EXCEPTION WHEN SQLSTATE '22023' THEN denied := TRUE;
        END;
        IF NOT denied THEN RAISE EXCEPTION 'network view accepted a location-only declaration'; END IF;
"""
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
        {''.join(statements)}
        {denial_checks}
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
        FOREACH object_name IN ARRAY ARRAY[{network_view_array}] LOOP
            IF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'id', 'SELECT')
               OR has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'public_summary', 'SELECT') THEN
                RAISE EXCEPTION 'network source-view drafter grant exceeds public record IDs';
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
        "anti_capture_governance_policy": [
            "e0000000-0000-4000-8000-000000000701",
            "e0000000-0000-4000-8000-000000000808",
        ],
        "commons_redistribution_policy": [
            "e0000000-0000-4000-8000-000000000702",
            "e0000000-0000-4000-8000-000000000704",
        ],
        "algorithmic_redistribution_mechanism": [
            "e0000000-0000-4000-8000-000000000703"
        ],
        "federation_protocol": ["e0000000-0000-4000-8000-000000000805"],
        "participatory_signal_experiment": [
            "e0000000-0000-4000-8000-000000000806"
        ],
    }
    source_scopes = {
        table: "network" if table in {"federation_protocol", "participatory_signal_experiment"}
        else "location_or_network"
        for table in KOKONUT_COMMONS_SOURCE_VIEWS
    }
    payload_entries = ", ".join(
        f"'{table}', jsonb_build_object('record_ids', jsonb_build_array({', '.join(repr(record_id) for record_id in source_ids[table])}), "
        f"'row_count', {len(source_ids[table])}, 'truncated', false, 'scope', '{source_scopes[table]}')"
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
           OR payload -> 'federation_protocol' ->> 'scope' <> 'network'
           OR payload -> 'participatory_signal_experiment' ->> 'scope' <> 'network'
           OR payload -> 'commons_redistribution_policy' ->> 'scope' <> 'location_or_network' THEN
            RAISE EXCEPTION 'Kokonut Commons source scopes were not preserved';
        END IF;
        attached := kokonut_security.get_location_ai_summary_worker_source_references(
            '{LOCATION_ID}', draft_record.summary_id,
            'd0000000-0000-4000-8000-000000000941'
        );
        IF attached IS DISTINCT FROM payload THEN
            RAISE EXCEPTION 'Kokonut Commons references were not returned under exact scope';
        END IF;
        FOREACH object_name IN ARRAY ARRAY[{view_array}] LOOP
            IF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'id', 'SELECT')
               OR has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'public_summary', 'SELECT') THEN
                RAISE EXCEPTION 'Kokonut Commons drafter grant exceeds ID and location columns';
            END IF;
            IF object_name IN ('v_public_federation_protocol', 'v_public_participatory_signal_experiment') THEN
                IF EXISTS (
                    SELECT 1 FROM pg_catalog.pg_attribute
                     WHERE attrelid = pg_catalog.to_regclass(format('public.%I', object_name))
                       AND attname = 'location_id' AND NOT attisdropped
                ) THEN
                    IF has_column_privilege('kokonut_ai_summary_drafter',
                            format('public.%I', object_name), 'location_id', 'SELECT') THEN
                        RAISE EXCEPTION 'network source grant includes unrelated location data';
                    END IF;
                END IF;
            ELSIF NOT has_column_privilege('kokonut_ai_summary_drafter',
                    format('public.%I', object_name), 'location_id', 'SELECT') THEN
                RAISE EXCEPTION 'mixed source grant omits its location validation column';
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
            scoped_source_references JSONB;
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
          FROM kokonut_security.list_location_ai_summary_reviews_with_sources(
              '{LOCATION_ID}', 51, 0
          )
         WHERE summary_type = 'open_source_capitalist';
        IF NOT FOUND
           OR queue_row.source_references -> 'farm_launch_unit_economics' ->> 'scope'
              <> 'location_or_network'
           OR queue_row.source_references -> 'network_scaling_target' ->> 'scope'
              <> 'network' THEN
            RAISE EXCEPTION 'review queue did not preserve network and mixed provenance labels';
        END IF;
        SELECT kokonut_security.get_location_ai_summary_source_references(
            '{LOCATION_ID}', queue_row.summary_id, 'review'
        ) INTO scoped_source_references;
        IF scoped_source_references -> 'network_scaling_target' ->> 'scope' <> 'network'
           OR scoped_source_references -> 'farm_launch_unit_economics' ->> 'scope'
              <> 'location_or_network' THEN
            RAISE EXCEPTION 'reviewer source-reference read lost provenance scope labels';
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
        "migrations 405, 419, 521-524, 529-537, 539-548, 580-592 apply; migrations 530-537, 539-548, 580-592 replay",
        "the original structured worker result is stored atomically with its draft and replayed without source reads",
        "pre-result worker receipts retain their content-only lookup fallback",
        "same-key summary-type collisions fail with 22023 before worker source reads, while cross-location result lookups fail with 42501",
        "worker results must match draft content, stay within size bounds, and remain inaccessible through direct table grants",
        "signed worker credential grants only ai_summary:draft for the exact owned location",
        "worker draft is attributed to a database worker principal and exact request retries replay once",
        "only the four deterministic and ten registered synthesis summary types can create drafts, and rejected types leave no partial row",
        "worker references include location-owned, shared-catalog, and four capital-efficiency rows validated through published public views",
        "the registered view map validates four location views and the network-scoped regional bio-input catalogue",
        "migration 533 validates four regenerative source views and rejects cross-location rows without changing attached manifests",
        "migration 534 validates fifteen location-scoped views across commons, GNH, financial resilience, and open-source-capitalist agents",
        "GNH, Commons, financial-resilience, and open-source manifests preserve location/network scope under signed worker context",
        "the drafter receives only ID/location view columns and worker execution receives no direct source table access",
        "migration 535 validates consent-filtered cultural, wellbeing, participatory-action, and stakeholder-feedback views",
        "private/no-consent stakeholder feedback cannot be attached to a worker draft",
        "the consent-safe source drafter receives only ID/location columns and worker execution has no sensitive-table access",
        "migration 536 and migration 540 validate mixed-scope Kokonut Commons policies and network federation/signal catalogues",
        "Kokonut Commons manifests label network-wide federation/signals and location-plus-unassigned policy rows explicitly",
        "migration 540 rejects cross-location mixed-scope IDs and mismatched declared scope without partial manifest writes",
        "the drafter receives only ID columns for network views and only ID/location for mixed views; worker execution has no direct source-table access",
        "cross-location, unpublished, and inexact-count view references fail closed without partial manifests; workers lack direct source-table access",
        "conflicting request intent, mismatched location, and duplicate source metadata fail closed",
        "worker login/execution cannot write summaries directly; runtime and Directus cannot bypass review with direct UPDATE",
        "independent operator review sees the worker attribution and can verify only to verified",
        "worker and signed reviewer reads preserve network/mixed provenance labels and the operator setter remains compatible",
        "synthesis source login can invoke only its bounded context setter; the shared reader retains only the five Kokonut Commons projections, with no raw/private/security tables and explicit network/mixed-scope behavior",
        "migration 541 removes inherited query-statistics access and stale direct table, sequence, function, and schema-create grants from the source login",
        "migration 541 removes stale public-schema CREATE from the NOLOGIN source reader as well as the source login",
        "migration 544 removes stale public-schema CREATE from the deterministic source login in addition to its relation, sequence, and function grants",
        "deterministic summary source login can call only the signed context setter; its reader selects 13 security-barrier wrappers filtered to exact location scope, retains only shared crop/expense catalogs, and cannot read raw/private tables or write",
        "migration 545 exposes only the required EBF evidence-gap columns under an exact ebf_scorecard/read location grant; migration 580 moves it to a dedicated reader/login pair",
        "migration 546 exposes six minimal CIDS projections only under cids_export/read and migration 580 moves them to a dedicated reader/login pair",
        "migration 547 exposes exact-location AI-summary list previews and the legacy digest input under ai_summary/read, works under forced RLS, and denies raw-table access",
        "migration 548 exposes only consented, thresholded Delphi aggregates under delphi/read; migration 580 moves it to a dedicated reader/login pair",
        "migration 580 gives EBF, CIDS, and Delphi independent SET-only logins and exact read-only projection roles; their login credentials cannot read synthesis or one another's views",
        "migration 580 replay restores the task-specific grants after replaying migration 548 and removes Delphi access from the general synthesis reader",
        "migration 581 splits summary inspection from deterministic reads and exposes digest metadata without summary content",
        "migration 581 replay removes stale raw-content, deterministic-reader, public-view, and schema-create grants while retaining the exact inspection projections",
        "migration 582 isolates organic readiness to a task-specific signed login and exactly fifteen location-filtered source projections",
        "migration 582 replay removes stale PUBLIC/shared synthesis access, extra source projections, direct table grants, and schema CREATE privileges",
        "organic readiness source returns no rows without signed context and returns only the granted location after context setup",
        "migration 583 isolates ecological modeling to a task-specific signed login and exactly twenty-seven calculation/provenance projections",
        "migration 583 replay removes stale PUBLIC/shared synthesis access, extra source projections, direct table grants, and schema CREATE privileges",
        "ecological modeling source returns no rows without signed context and returns only the granted location across all twenty-seven projections",
        "migration 584 isolates holistic wellbeing to its three consent-filtered public summaries and removes them from the shared synthesis reader",
        "migration 584 replay removes stale PUBLIC/shared grants, unrelated feedback/capital projections, raw feedback table access, and schema CREATE privileges",
        "holistic wellbeing source returns no rows without signed context and returns only the granted location while excluding foreign-location records",
        "migration 585 isolates feedback synthesis to its one consent-safe public summary and removes it from the shared synthesis reader",
        "migration 585 replay removes stale PUBLIC/shared grants, unrelated wellbeing/capital projections, raw feedback access, and schema CREATE privileges",
        "feedback source returns no rows without signed context and only the owned location after signed scope, excluding foreign feedback",
        "migration 586 isolates Commons Liberation to four location-filtered projections and removes them from the shared synthesis reader",
        "migration 586 replay removes stale PUBLIC/shared grants, unrelated wellbeing/capital projections, raw source access, and schema CREATE privileges",
        "Commons Liberation source returns no rows without signed context and only owned rows across its four views, excluding foreign locations",
        "migration 587 isolates GNH Alignment to five location-filtered public summaries and removes them from the shared synthesis reader",
        "migration 587 replay removes stale PUBLIC/shared grants, unrelated feedback/capital projections, raw source access, and schema CREATE privileges",
        "GNH Alignment source returns no rows without signed context and only owned rows across its five views, excluding foreign locations",
        "migration 588 isolates Regenerator synthesis to four location-filtered public projections and removes them from the shared synthesis reader",
        "migration 588 replay removes stale PUBLIC/shared grants, unrelated feedback/capital projections, raw source access, and schema CREATE privileges",
        "Regenerator source returns no rows without signed context and only owned rows across its four views, excluding foreign locations",
        "migration 589 isolates Capital Efficiency synthesis to four location-filtered public projections and removes them from the shared synthesis reader",
        "migration 589 replay removes stale PUBLIC/shared grants, unrelated feedback/Regenerator projections, raw source access, and schema CREATE privileges",
        "Capital Efficiency source returns no rows without signed context and only owned rows across its four views, excluding foreign locations",
        "migration 590 isolates Financial Resilience to three location-filtered projections and one public network publication view",
        "migration 590 replay removes stale PUBLIC/shared grants, unrelated Regenerator/Capital Efficiency projections, raw source access, and schema CREATE privileges",
        "Financial Resilience location views exclude foreign rows while signed context permits the network-wide Green Paper publication projection",
        "migration 591 isolates Bio Factory to four location-filtered projections and one public regional-input catalogue",
        "migration 591 replay removes stale PUBLIC/shared grants, unrelated projections, raw source access, and schema CREATE privileges",
        "Bio Factory location views exclude foreign rows while signed context permits the network-wide regional-input catalogue",
        "migration 592 isolates Open Source Capitalist to three location-or-network views and two network-wide public catalogs",
        "migration 592 replay removes stale PUBLIC/shared grants, unrelated projections, raw source access, and schema CREATE privileges",
        "Open Source Capitalist mixed views return owned plus unassigned rows and exclude foreign rows; network catalogs require signed context",
        "migration 542 and 544 replay remove stale private-summary, raw-source, and write grants before reapplying the deterministic wrapper allowlist",
        "legacy unattributed drafts remain blocked from approval; lifecycle review is operator-attributed",
        "runtime and Directus cannot call worker draft functions or read private worker receipts",
    ]
    evidence: dict[str, object] = {
        "result": "failed",
        "migrations": [path.name for path in MIGRATIONS],
        "database_target": "new disposable PostgreSQL 16 container with network disabled",
        "postgres_image": IMAGE,
        "requested_platform": PLATFORM or "native",
        "candidate_or_legacy_modified": False,
        "credential_note": "only a synthetic high-entropy credential is hashed in the disposable fixture",
        "review_context_note": "operator review uses a synthetic context stub in the disposable SQL fixture; production worker code uses the database-signed context helper",
        "source_lineage_note": "synthesis source manifests distinguish exact-location, network-wide public-catalogue, and location-plus-unassigned scopes; network references are validated through migration-owned ID-only public-view grants and are not relabeled as farm-owned",
        "source_reader_note": "shared synthesis, deterministic summary generation, summary inspection, organic readiness, ecological modeling, holistic wellbeing, feedback, Commons Liberation, GNH Alignment, Regenerator, Capital Efficiency, Financial Resilience, Bio Factory, and Open Source Capitalist use separate database-signed ai_summary/read identities as appropriate. Summary inspection sees only bounded previews and digest metadata, not operational sources or raw summary content. Organic readiness sees fifteen task-specific projections; ecological modeling sees twenty-seven task-specific calculation/provenance projections; holistic wellbeing sees three consent-filtered summaries; feedback sees its consent-safe stakeholder summary; Commons Liberation sees four location-filtered views; GNH Alignment sees five location-filtered public summaries; Regenerator and Capital Efficiency each see four location-filtered public summaries; Financial Resilience sees three location-filtered views and one public network-wide Green Paper status view; Bio Factory sees four location-filtered views and one public network-wide regional input catalogue; Open Source Capitalist sees three location-or-network views and two network-wide public catalogs. The remaining shared reader retains five Kokonut Commons projections. EBF, CIDS, and Delphi use separate credentials/logins and exact reader roles for their own projections. Signed resource/location scope remains enforced by security-barrier views. Runtime credentials are not provisioned by these disposable checks.",
        "organic_projection_fixture_note": "Because this focused disposable chain does not apply the historical farm schema migrations, fifteen synthetic security-barrier projections stand in for migration 549's outputs. They contain own/foreign location sentinels filtered by the real signed current_worker_scope function; the repository candidate and legacy database are untouched.",
        "ecological_projection_fixture_note": "Because this focused disposable chain does not apply historical farm/ecology schema migrations 550-551, twenty-seven synthetic security-barrier projections stand in for those outputs. They contain own/foreign location sentinels filtered by the real signed current_worker_scope function; the repository candidate and legacy database are untouched.",
        "holistic_wellbeing_projection_fixture_note": "Migrations 535 and 543 create the real consent-filtered and signed security-barrier source projections in this disposable chain. Synthetic own/foreign rows are added to the fixture source tables before migration 584; no live stakeholder data or candidate/legacy database is used.",
        "feedback_projection_fixture_note": "Migrations 535 and 543 create the signed stakeholder-feedback summary from the disposable consent-safe view. The focused fixture already contains one consented owned row, one private row, and one consented foreign row; the signed security-barrier view must reveal only the owned row. No live feedback or candidate/legacy database is used.",
        "commons_liberation_projection_fixture_note": "Migrations 534 and 543 create the real location-filtered security-barrier projections. The fixture adds one synthetic published foreign-location row to each of four source tables, alongside one owned fixture row, and the real signed scope function must return only the owned rows.",
        "gnh_alignment_projection_fixture_note": "Migrations 534 and 543 create the real location-filtered security-barrier projections. The fixture adds one synthetic published foreign-location row to each of five source tables, alongside one owned fixture row, and the real signed scope function must return only the owned rows.",
        "capital_efficiency_projection_fixture_note": "Migration 543 creates the real location-filtered security-barrier projections. The fixture adds one synthetic published foreign-location row to each of four source tables, alongside one owned fixture row, and the real signed scope function must return only the owned rows.",
        "financial_resilience_projection_fixture_note": "Migrations 534 and 543 create the three location-filtered security-barrier views and the network-wide Green Paper status projection. The fixture adds one synthetic published foreign row to each location source table; signed location context returns only the owned rows while allowing the explicitly public network view.",
        "bio_factory_projection_fixture_note": "Migrations 534 and 543 create four location-filtered security-barrier views and one network-wide regional input catalogue. The fixture adds one synthetic published foreign row to each location source table; signed location context returns only the owned rows while preserving the explicit public catalogue.",
        "open_source_capitalist_projection_fixture_note": "Migrations 534 and 543 create three location-or-network security-barrier views and two network-wide catalogs. Synthetic null-scope and foreign rows verify declared visibility under signed location context; no candidate or legacy database is used.",
        "regenerator_projection_fixture_note": "Migrations 533 and 543 create the real location-filtered security-barrier projections. The fixture adds one synthetic published foreign-location row to each of four source tables, alongside one owned fixture row, and the real signed scope function must return only the owned rows.",
        "checks": checks,
    }
    if PLATFORM == "linux/arm64" and IMAGE == "sogis/postgis:16-3.4":
        evidence["postgis_acl_fixture_note"] = (
            "This ARM64 PostGIS image grants PUBLIC access to raster_columns and "
            "raster_overviews unlike the AMD64 image used by the native replay. "
            "The disposable fixture revokes those two metadata grants before "
            "migration 541 to match the repository's explicit three-catalog "
            "source-reader contract; no external database or image is modified."
        )
    stage = "container_start"
    try:
        docker_run = [docker, "run"]
        if PLATFORM:
            docker_run.extend(["--platform", PLATFORM])
        docker_run.extend([
            "--rm", "--detach", "--name", container,
            "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
        ])
        base.run(docker_run)
        base.wait_ready(docker, container)
        evidence["container_uname"] = base.run([docker, "exec", container, "uname", "-m"])
        expected_architecture = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(PLATFORM)
        if expected_architecture and evidence["container_uname"] != expected_architecture:
            raise RuntimeError(
                f"container architecture {evidence['container_uname']!r} does not match {PLATFORM}"
            )
        stage = "worker_fixture_and_migrations_405_419"
        base.psql(docker, container, WORKER_FIXTURE.read_text(encoding="utf-8"))
        for migration_path in MIGRATIONS[:2]:
            sql = migration_path.read_text(encoding="utf-8")
            base.psql(docker, container, sql)
        stage = "ai_summary_fixture_and_migrations_521_522_523_524_529_530_531_532_533_534_535_536_537_539_540_541_542_543_544_545_546_547_548_580_581_582_583_584_585_586_587_588_589_590"
        base.psql(docker, container, AI_SUMMARY_FIXTURE.read_text(encoding="utf-8"))
        base.psql(docker, container, EBF_SOURCE_FIXTURE)
        for migration_path in MIGRATIONS[2:]:
            sql = migration_path.read_text(encoding="utf-8")
            if migration_path.name.startswith("548_"):
                stage = "delphi_agent_source_fixture"
                base.psql(
                    docker,
                    container,
                    DELPHI_SOURCE_FIXTURE.read_text(encoding="utf-8"),
                )
                stage = "migration_548_apply"
            if migration_path.name.startswith("580_"):
                stage = "migration_580_apply"
            if migration_path.name.startswith("581_"):
                stage = "migration_581_apply"
            if migration_path.name.startswith("582_"):
                stage = "organic_source_projection_fixture"
                base.psql(docker, container, _organic_source_projection_fixture())
                stage = "migration_582_apply"
            if migration_path.name.startswith("583_"):
                stage = "ecological_source_projection_fixture"
                base.psql(docker, container, _ecological_source_projection_fixture())
                stage = "migration_583_apply"
            if migration_path.name.startswith("584_"):
                stage = "holistic_wellbeing_foreign_location_fixture"
                base.psql(
                    docker, container, _holistic_wellbeing_source_projection_fixture()
                )
                stage = "migration_584_apply"
            if migration_path.name.startswith("585_"):
                stage = "migration_585_apply"
            if migration_path.name.startswith("586_"):
                stage = "commons_liberation_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _commons_liberation_source_projection_fixture(),
                )
                stage = "migration_586_apply"
            if migration_path.name.startswith("587_"):
                stage = "gnh_alignment_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _gnh_alignment_source_projection_fixture(),
                )
                stage = "migration_587_apply"
            if migration_path.name.startswith("588_"):
                stage = "regenerator_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _regenerator_source_projection_fixture(),
                )
                stage = "migration_588_apply"
            if migration_path.name.startswith("589_"):
                stage = "capital_efficiency_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _capital_efficiency_source_projection_fixture(),
                )
                stage = "migration_589_apply"
            if migration_path.name.startswith("590_"):
                stage = "financial_resilience_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _financial_resilience_source_projection_fixture(),
                )
                stage = "migration_590_apply"
            if migration_path.name.startswith("591_"):
                stage = "bio_factory_foreign_location_fixture"
                base.psql(
                    docker,
                    container,
                    _bio_factory_source_projection_fixture(),
                )
                stage = "migration_591_apply"
            if migration_path.name.startswith("592_"):
                stage = "open_source_capitalist_mixed_scope_fixture"
                base.psql(
                    docker,
                    container,
                    _open_source_capitalist_projection_fixture(),
                )
                stage = "migration_592_apply"
            if migration_path.name.startswith("546_"):
                stage = "cids_source_fixture"
                base.psql(docker, container, CIDS_SOURCE_FIXTURE)
                stage = "migration_546_apply"
            if (
                migration_path.name.startswith("541_")
                and PLATFORM == "linux/arm64"
                and IMAGE == "sogis/postgis:16-3.4"
            ):
                stage = "arm64_postgis_public_raster_metadata_acl_fixture"
                base.psql(
                    docker,
                    container,
                    "DO $$ BEGIN "
                    "IF to_regclass('public.raster_columns') IS NOT NULL THEN "
                    "EXECUTE 'REVOKE SELECT ON TABLE public.raster_columns FROM PUBLIC'; END IF; "
                    "IF to_regclass('public.raster_overviews') IS NOT NULL THEN "
                    "EXECUTE 'REVOKE SELECT ON TABLE public.raster_overviews FROM PUBLIC'; END IF; "
                    "END $$;",
                )
                stage = "migration_541_apply"
            if migration_path.name.startswith("541_"):
                stage = "pg_stat_statements_public_grant_fixture"
                base.psql(
                    docker,
                    container,
                    "DO $$ BEGIN "
                    "IF to_regclass('public.pg_stat_statements') IS NULL THEN "
                    "CREATE TABLE public.pg_stat_statements (query text); END IF; "
                    "IF to_regclass('public.pg_stat_statements_info') IS NULL THEN "
                    "CREATE TABLE public.pg_stat_statements_info (dealloc bigint); END IF; "
                    "END $$; "
                    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles "
                    "WHERE rolname = 'kokonut_agent_summary_source_reader') THEN "
                    "CREATE ROLE kokonut_agent_summary_source_reader NOLOGIN NOINHERIT "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; "
                    "END IF; END $$; "
                    "GRANT CREATE ON SCHEMA public TO kokonut_agent_summary_source_reader; "
                    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles "
                    "WHERE rolname = 'kokonut_agent_summary_source_login') THEN "
                    "CREATE ROLE kokonut_agent_summary_source_login NOLOGIN NOINHERIT "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; "
                    "END IF; END $$; "
                    "GRANT SELECT ON TABLE public.pg_stat_statements, "
                    "public.pg_stat_statements_info TO PUBLIC; "
                    "GRANT SELECT ON TABLE public.pg_stat_statements, "
                    "public.pg_stat_statements_info "
                    "TO kokonut_agent_summary_source_login; "
                    "CREATE SEQUENCE public.kokonut_agent_source_acl_fixture_seq; "
                    "GRANT USAGE, SELECT, UPDATE ON SEQUENCE "
                    "public.kokonut_agent_source_acl_fixture_seq "
                    "TO kokonut_agent_summary_source_login; "
                    "CREATE FUNCTION public.kokonut_agent_source_acl_fixture_fn() "
                    "RETURNS integer LANGUAGE SQL IMMUTABLE AS 'SELECT 1'; "
                    "REVOKE ALL ON FUNCTION public.kokonut_agent_source_acl_fixture_fn() "
                    "FROM PUBLIC; "
                    "GRANT EXECUTE ON FUNCTION public.kokonut_agent_source_acl_fixture_fn() "
                    "TO kokonut_agent_summary_source_login; "
                    "GRANT CREATE ON SCHEMA public "
                    "TO kokonut_agent_summary_source_login;",
                )
                stage = "migration_541_apply"
            base.psql(docker, container, sql)
            if migration_path.name.startswith("582_"):
                stage = "migration_582_signed_scope_acceptance"
                base.psql(docker, container, _organic_source_scope_acceptance())
                stage = "migration_582_stale_grant_replay"
                base.psql(docker, container, _organic_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(docker, container, _organic_source_scope_acceptance())
            if migration_path.name.startswith("583_"):
                stage = "migration_583_signed_scope_acceptance"
                base.psql(docker, container, _ecological_source_scope_acceptance())
                stage = "migration_583_stale_grant_replay"
                base.psql(docker, container, _ecological_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(docker, container, _ecological_source_scope_acceptance())
            if migration_path.name.startswith("584_"):
                stage = "migration_584_signed_scope_acceptance"
                base.psql(docker, container, _holistic_wellbeing_source_scope_acceptance())
                stage = "migration_584_stale_grant_replay"
                base.psql(docker, container, _holistic_wellbeing_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(docker, container, _holistic_wellbeing_source_scope_acceptance())
            if migration_path.name.startswith("585_"):
                stage = "migration_585_signed_scope_acceptance"
                base.psql(docker, container, _feedback_source_scope_acceptance())
                stage = "migration_585_stale_grant_replay"
                base.psql(docker, container, _feedback_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(docker, container, _feedback_source_scope_acceptance())
            if migration_path.name.startswith("586_"):
                stage = "migration_586_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _commons_liberation_source_scope_acceptance(),
                )
                stage = "migration_586_stale_grant_replay"
                base.psql(docker, container, _commons_liberation_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _commons_liberation_source_scope_acceptance(),
                )
            if migration_path.name.startswith("587_"):
                stage = "migration_587_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _gnh_alignment_source_scope_acceptance(),
                )
                stage = "migration_587_stale_grant_replay"
                base.psql(docker, container, _gnh_alignment_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _gnh_alignment_source_scope_acceptance(),
                )
            if migration_path.name.startswith("588_"):
                stage = "migration_588_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _regenerator_source_scope_acceptance(),
                )
                stage = "migration_588_stale_grant_replay"
                base.psql(docker, container, _regenerator_source_stale_grants())
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _regenerator_source_scope_acceptance(),
                )
            if migration_path.name.startswith("589_"):
                stage = "migration_589_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _capital_efficiency_source_scope_acceptance(),
                )
                stage = "migration_589_stale_grant_replay"
                base.psql(
                    docker,
                    container,
                    _capital_efficiency_source_stale_grants(),
                )
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _capital_efficiency_source_scope_acceptance(),
                )
            if migration_path.name.startswith("590_"):
                stage = "migration_590_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _financial_resilience_source_scope_acceptance(),
                )
                stage = "migration_590_stale_grant_replay"
                base.psql(
                    docker,
                    container,
                    _financial_resilience_source_stale_grants(),
                )
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _financial_resilience_source_scope_acceptance(),
                )
            if migration_path.name.startswith("591_"):
                stage = "migration_591_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _bio_factory_source_scope_acceptance(),
                )
                stage = "migration_591_stale_grant_replay"
                base.psql(
                    docker,
                    container,
                    _bio_factory_source_stale_grants(),
                )
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _bio_factory_source_scope_acceptance(),
                )
            if migration_path.name.startswith("592_"):
                stage = "migration_592_signed_scope_acceptance"
                base.psql(
                    docker,
                    container,
                    _open_source_capitalist_source_scope_acceptance(),
                )
                stage = "migration_592_stale_grant_replay"
                base.psql(
                    docker,
                    container,
                    _open_source_capitalist_source_stale_grants(),
                )
                base.psql(docker, container, sql)
                base.psql(
                    docker,
                    container,
                    _open_source_capitalist_source_scope_acceptance(),
                )
                base.psql(
                    docker,
                    container,
                    "DELETE FROM public.adoption_barrier_assessment "
                    "WHERE id IN ('e0000000-0000-4000-8000-000000000810', "
                    "'e0000000-0000-4000-8000-000000000811'); "
                    "DELETE FROM public.perpetual_value_stress_test "
                    "WHERE id IN ('e0000000-0000-4000-8000-000000000812', "
                    "'e0000000-0000-4000-8000-000000000813');",
                )
            if migration_path.name.startswith("541_"):
                stage = "pg_stat_statements_public_grant_acceptance"
                base.psql(
                    docker,
                    container,
                    "DO $$ DECLARE relation_name text; relation_oid oid; "
                    "BEGIN FOREACH relation_name IN ARRAY ARRAY["
                    "'pg_stat_statements', 'pg_stat_statements_info'] LOOP "
                    "relation_oid := to_regclass(format('public.%I', relation_name)); "
                    "IF has_table_privilege('kokonut_agent_summary_source_reader', "
                    "relation_oid, 'SELECT') THEN "
                    "RAISE EXCEPTION 'source reader inherited query statistics access'; "
                    "END IF; "
                    "IF has_table_privilege('kokonut_agent_summary_source_login', "
                    "relation_oid, 'SELECT') THEN "
                    "RAISE EXCEPTION 'source login retained query-statistics access'; "
                    "END IF; "
                    "IF EXISTS (SELECT 1 FROM pg_class AS relation "
                    "CROSS JOIN LATERAL aclexplode(relation.relacl) AS acl "
                    "WHERE relation.oid = relation_oid AND acl.grantee = 0 "
                    "AND acl.privilege_type = 'SELECT') THEN "
                    "RAISE EXCEPTION 'PUBLIC retained query statistics access'; "
                    "END IF; END LOOP; "
                    "IF has_sequence_privilege('kokonut_agent_summary_source_login', "
                    "'public.kokonut_agent_source_acl_fixture_seq', 'USAGE') THEN "
                    "RAISE EXCEPTION 'source login retained a direct sequence grant'; "
                    "END IF; "
                    "IF has_function_privilege('kokonut_agent_summary_source_login', "
                    "'public.kokonut_agent_source_acl_fixture_fn()', 'EXECUTE') THEN "
                    "RAISE EXCEPTION 'source login retained a direct function grant'; "
                    "END IF; "
                    "IF has_schema_privilege('kokonut_agent_summary_source_reader', "
                    "'public', 'CREATE') THEN "
                    "RAISE EXCEPTION 'source reader retained public schema CREATE'; "
                    "END IF; "
                    "IF has_schema_privilege('kokonut_agent_summary_source_login', "
                    "'public', 'CREATE') THEN "
                    "RAISE EXCEPTION 'source login retained public schema CREATE'; "
                    "END IF; END $$;",
                )
            if migration_path.name.startswith("542_"):
                stage = "deterministic_reader_stale_schema_acl_fixture"
                base.psql(
                    docker,
                    container,
                    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles "
                    "WHERE rolname = 'kokonut_agent_summary_deterministic_reader') THEN "
                    "CREATE ROLE kokonut_agent_summary_deterministic_reader NOLOGIN NOINHERIT "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; "
                    "END IF; END $$; "
                    "GRANT CREATE ON SCHEMA public "
                    "TO kokonut_agent_summary_deterministic_reader;",
                )
            if migration_path.name.startswith(("530_", "531_", "532_", "533_", "534_", "535_", "536_", "537_", "539_", "540_", "541_", "542_", "543_", "544_", "545_", "546_", "547_", "548_")):
                if migration_path.name.startswith("545_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT ON public.v_ebf_evidence_gap_summary "
                        "TO kokonut_agent_summary_source_reader, "
                        "kokonut_agent_summary_source_login; "
                        "GRANT SELECT, INSERT, UPDATE, DELETE "
                        "ON kokonut_agent_source.v_ebf_evidence_gap_summary "
                        "TO kokonut_agent_summary_source_reader, "
                        "kokonut_agent_summary_source_login; "
                        "GRANT USAGE ON SCHEMA kokonut_agent_source "
                        "TO kokonut_agent_summary_source_login;",
                    )
                if migration_path.name.startswith("546_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT ON public.stakeholder_feedback, public.impact_claim "
                        "TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login; "
                        "GRANT INSERT, UPDATE, DELETE ON kokonut_agent_source.cids_location "
                        "TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login; "
                        "GRANT USAGE ON SCHEMA kokonut_agent_source "
                        "TO kokonut_agent_summary_source_login;",
                    )
                if migration_path.name.startswith("542_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT, INSERT ON public.ai_summary "
                        "TO kokonut_agent_summary_deterministic_reader;",
                    )
                if migration_path.name.startswith("543_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT, INSERT ON public.ai_summary "
                        "TO kokonut_agent_summary_source_reader;",
                    )
                if migration_path.name.startswith("544_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT, INSERT ON public.harvest_event "
                        "TO kokonut_agent_summary_deterministic_reader, "
                        "kokonut_agent_summary_deterministic_source_login; "
                        "GRANT CREATE ON SCHEMA public "
                        "TO kokonut_agent_summary_deterministic_source_login;",
                    )
                if migration_path.name.startswith("547_"):
                    base.psql(
                        docker,
                        container,
                        "GRANT SELECT, INSERT ON public.ai_summary "
                        "TO kokonut_agent_summary_deterministic_reader, "
                        "kokonut_agent_summary_deterministic_source_login; "
                        "GRANT SELECT, INSERT, UPDATE, DELETE "
                        "ON kokonut_agent_source.ai_summary_list, "
                        "kokonut_agent_source.ai_summary_inspection "
                        "TO kokonut_agent_summary_deterministic_reader, "
                        "kokonut_agent_summary_deterministic_source_login; "
                        "GRANT USAGE ON SCHEMA kokonut_agent_source "
                        "TO kokonut_agent_summary_deterministic_source_login;",
                    )
                base.psql(docker, container, sql)
        stage = "synthesis_source_reader_role_acceptance"
        base.psql(docker, container, _source_reader_acceptance())
        stage = "synthesis_source_reader_signed_location_scope_acceptance"
        base.psql(docker, container, _source_reader_scope_acceptance())
        stage = "ebf_evidence_gap_signed_source_scope_acceptance"
        base.psql(docker, container, _ebf_source_scope_acceptance())
        stage = "cids_export_signed_source_scope_acceptance"
        base.psql(docker, container, _cids_source_acceptance())
        stage = "deterministic_summary_signed_source_view_acceptance"
        base.psql(docker, container, _deterministic_source_reader_acceptance())
        stage = "deterministic_summary_inspection_signed_source_acceptance"
        base.psql(docker, container, _summary_inspection_acceptance())
        stage = "summary_inspection_stale_grant_replay"
        base.psql(
            docker,
            container,
            "GRANT SELECT ON public.ai_summary TO "
            "kokonut_agent_summary_inspection_reader, kokonut_agent_summary_inspection_login; "
            "GRANT SELECT ON kokonut_agent_source.ai_summary_inspection "
            "TO PUBLIC, kokonut_agent_summary_deterministic_reader, "
            "kokonut_agent_summary_inspection_reader, kokonut_agent_summary_inspection_login; "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON kokonut_agent_source.ai_summary_digest "
            "TO kokonut_agent_summary_inspection_reader, kokonut_agent_summary_inspection_login; "
            "GRANT EXECUTE ON FUNCTION public.digest(bytea,text) "
            "TO kokonut_agent_summary_inspection_reader, kokonut_agent_summary_inspection_login; "
            "GRANT CREATE ON SCHEMA kokonut_agent_source "
            "TO kokonut_agent_summary_inspection_reader, kokonut_agent_summary_inspection_login;",
        )
        migration_581 = next(path for path in MIGRATIONS if path.name.startswith("581_"))
        base.psql(docker, container, migration_581.read_text(encoding="utf-8"))
        base.psql(
            docker,
            container,
            "DO $$ BEGIN "
            "IF has_table_privilege('kokonut_agent_summary_inspection_reader', 'public.ai_summary', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_inspection_login', 'public.ai_summary', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_deterministic_reader', 'kokonut_agent_source.ai_summary_list', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_deterministic_reader', 'kokonut_agent_source.ai_summary_digest', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_inspection_reader', 'kokonut_agent_source.ai_summary_inspection', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_inspection_login', 'kokonut_agent_source.ai_summary_digest', 'SELECT') "
            "OR has_schema_privilege('kokonut_agent_summary_inspection_login', 'kokonut_agent_source', 'CREATE') "
            "OR has_schema_privilege('kokonut_agent_summary_inspection_reader', 'kokonut_agent_source', 'CREATE') "
            "THEN RAISE EXCEPTION 'migration 581 replay retained stale summary inspection access'; END IF; "
            "IF EXISTS (SELECT 1 FROM pg_class AS relation CROSS JOIN LATERAL aclexplode(relation.relacl) AS acl "
            "WHERE relation.oid = 'kokonut_agent_source.ai_summary_inspection'::regclass "
            "AND acl.grantee = 0 AND acl.privilege_type = 'SELECT') THEN "
            "RAISE EXCEPTION 'migration 581 replay retained PUBLIC raw-content access'; END IF; "
            "IF NOT has_table_privilege('kokonut_agent_summary_inspection_reader', 'kokonut_agent_source.ai_summary_list', 'SELECT') "
            "OR NOT has_table_privilege('kokonut_agent_summary_inspection_reader', 'kokonut_agent_source.ai_summary_digest', 'SELECT') "
            "THEN RAISE EXCEPTION 'migration 581 replay removed the exact inspection projections'; END IF; END $$;",
        )
        stage = "delphi_agent_signed_source_acceptance"
        base.psql(docker, container, _delphi_agent_source_acceptance())
        stage = "delphi_agent_stale_grant_replay"
        base.psql(
            docker,
            container,
            "GRANT SELECT ON public.delphi_study, public.delphi_item, "
            "public.delphi_contribution, public.delphi_panel_member "
            "TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login; "
            "GRANT INSERT, UPDATE, DELETE ON kokonut_agent_source.delphi_live_summary "
            "TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login; "
            "GRANT USAGE ON SCHEMA kokonut_agent_source "
            "TO kokonut_agent_summary_source_login;",
        )
        migration_548 = next(path for path in MIGRATIONS if path.name.startswith("548_"))
        migration_580 = next(path for path in MIGRATIONS if path.name.startswith("580_"))
        base.psql(docker, container, migration_548.read_text(encoding="utf-8"))
        base.psql(docker, container, migration_580.read_text(encoding="utf-8"))
        base.psql(
            docker,
            container,
            "DO $$ BEGIN "
            "IF has_table_privilege('kokonut_agent_summary_source_reader', 'public.delphi_contribution', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_source_login', 'public.delphi_contribution', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_source_reader', 'kokonut_agent_source.delphi_live_summary', 'SELECT') "
            "OR has_table_privilege('kokonut_agent_summary_source_reader', 'kokonut_agent_source.delphi_live_summary', 'INSERT') "
            "OR has_table_privilege('kokonut_agent_summary_source_reader', 'kokonut_agent_source.delphi_live_summary', 'UPDATE') "
            "OR has_table_privilege('kokonut_agent_summary_source_reader', 'kokonut_agent_source.delphi_live_summary', 'DELETE') "
            "OR has_schema_privilege('kokonut_agent_summary_source_login', 'kokonut_agent_source', 'USAGE') "
            "THEN RAISE EXCEPTION 'migration 580 replay retained a stale Delphi source grant'; END IF; "
            "IF NOT has_table_privilege('kokonut_agent_delphi_source_reader', "
            "'kokonut_agent_source.delphi_live_summary', 'SELECT') THEN "
            "RAISE EXCEPTION 'migration 580 replay removed the dedicated Delphi read grant'; "
            "END IF; END $$;",
        )
        base.psql(docker, container, _delphi_agent_source_acceptance())
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
