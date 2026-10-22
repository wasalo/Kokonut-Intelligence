#!/usr/bin/env python3
"""Replay migration 550 against isolated PostgreSQL 16 source fixtures."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_549 = ROOT / "schemas/postgres/549_signed_organic_readiness_synthesis_source.sql"
MIGRATION_550 = ROOT / "schemas/postgres/550_signed_ecological_modeling_synthesis_source.sql"
OUTPUT = Path(os.environ.get(
    "KOKONUT_ECOLOGICAL_WORKER_TEST_OUTPUT",
    ROOT / "docs/refactor/builds/2026-10-22-recovery/cap-038-ecological-modeling-source-disposable.json",
))
PLATFORM = os.environ.get("KOKONUT_ECOLOGICAL_WORKER_TEST_PLATFORM", "")
if PLATFORM not in {"", "linux/amd64", "linux/arm64"}:
    raise SystemExit("KOKONUT_ECOLOGICAL_WORKER_TEST_PLATFORM must be linux/amd64 or linux/arm64")
IMAGE = os.environ.get(
    "KOKONUT_ECOLOGICAL_WORKER_TEST_IMAGE",
    "sogis/postgis:16-3.4" if PLATFORM == "linux/arm64" else "postgis/postgis:16-3.4",
)
LOCATION_ID = "a0000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "a0000000-0000-4000-8000-000000000002"

ORGANIC_SCRIPT = ROOT / "scripts/check-organic-readiness-synthesis-disposable.py"
SPEC = importlib.util.spec_from_file_location("organic_synthesis_fixture", ORGANIC_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load the preceding signed-worker fixture")
ORGANIC_FIXTURE_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORGANIC_FIXTURE_MODULE)

ECOLOGICAL_FIXTURE = f"""
CREATE TABLE public.location (id UUID PRIMARY KEY, name TEXT, status TEXT);
CREATE TABLE public.farm_registry_record (location_id UUID, status TEXT);
INSERT INTO public.location VALUES
('{LOCATION_ID}', 'Farm A', 'active'), ('{OTHER_LOCATION_ID}', 'Farm B', 'active');
INSERT INTO public.farm_registry_record VALUES
('{LOCATION_ID}', 'verified'), ('{OTHER_LOCATION_ID}', 'published');

CREATE TABLE public.ecological_interaction (
 id UUID, location_id UUID, interaction_type TEXT, interaction_strength NUMERIC,
 status TEXT, notes TEXT);
CREATE TABLE public.energy_flow_measurement (
 id UUID, location_id UUID, from_trophic_level TEXT, to_trophic_level TEXT,
 biomass_transferred_kg NUMERIC, conversion_efficiency_pct NUMERIC, status TEXT,
 notes TEXT);
CREATE TABLE public.population_dynamics_record (
 id UUID, location_id UUID, species_name TEXT, species_common_name TEXT,
 trophic_level TEXT, record_date DATE, population_count INTEGER, status TEXT,
 notes TEXT);
CREATE TABLE public.soil_input_application (
 id UUID, location_id UUID, input_type TEXT, input_name TEXT,
 quantity_kg NUMERIC, residual_pct NUMERIC, application_date DATE,
 residual_measurement_date DATE, status TEXT, notes TEXT);
CREATE TABLE public.pest_observation (
 id UUID, location_id UUID, observation_date DATE, pest_species TEXT,
 pest_common_name TEXT, pest_category TEXT, severity TEXT,
 incidence_count INTEGER, affected_area_pct NUMERIC,
 outbreak_probability_pct NUMERIC, temperature_c NUMERIC, humidity_pct NUMERIC,
 predator_count INTEGER, natural_enemy_present BOOLEAN, status TEXT, notes TEXT,
 observer TEXT);
CREATE TABLE public.biocontrol_release (
 id UUID, location_id UUID, release_date DATE, predator_species TEXT,
 predator_common_name TEXT, predator_category TEXT, target_pest TEXT,
 release_count INTEGER, effectiveness_pct NUMERIC, pest_reduction_pct NUMERIC,
 release_density_per_m2 NUMERIC, follow_up_date DATE, status TEXT, notes TEXT);
CREATE TABLE public.resource_consumption (
 id UUID, location_id UUID, resource_type TEXT, unit TEXT, component TEXT,
 quantity NUMERIC, is_estimated BOOLEAN, status TEXT, notes TEXT);
CREATE TABLE public.harvest_event (
 id UUID, location_id UUID, quantity NUMERIC, status TEXT, notes TEXT);
CREATE TABLE public.species_observation (
 id UUID, location_id UUID, species_name TEXT, conservation_status TEXT,
 count INTEGER, status TEXT, observer TEXT, notes TEXT, evidence_urls TEXT[]);
CREATE TABLE public.livestock_group (
 id UUID PRIMARY KEY, location_id UUID, group_name TEXT, species TEXT,
 breed TEXT, animal_count INTEGER, feed_type TEXT, average_weight_kg NUMERIC,
 status TEXT, notes TEXT);
CREATE TABLE public.feed_intake_record (
 id UUID, location_id UUID, livestock_group_id UUID, record_date DATE,
 quantity_kg NUMERIC, per_animal_kg NUMERIC, status TEXT, notes TEXT);
CREATE TABLE public.token_reward_distribution (
 id UUID, location_id UUID, reward_type TEXT, token_type TEXT,
 token_amount NUMERIC, usd_value NUMERIC, linked_metric_key TEXT,
 linked_metric_value NUMERIC, distribution_method TEXT, is_onchain BOOLEAN,
 status TEXT, recipient_name TEXT, notes TEXT);
CREATE TABLE public.reward_calibration_model (
 id UUID, location_id UUID, model_name TEXT, model_type TEXT, run_date DATE,
 input_metrics JSONB, output_weights JSONB, calibration_score NUMERIC,
 total_tokens_distributed NUMERIC, token_per_unit_output NUMERIC,
 epoch INTEGER, confidence_level NUMERIC, status TEXT, notes TEXT);

INSERT INTO public.ecological_interaction VALUES
('b0000000-0000-4000-8000-000000000101','{LOCATION_ID}','mutualism',0.8,'verified','private note'),
('b0000000-0000-4000-8000-000000000201','{OTHER_LOCATION_ID}','competition',0.3,'published','foreign note');
INSERT INTO public.energy_flow_measurement VALUES
('b0000000-0000-4000-8000-000000000102','{LOCATION_ID}','producer','primary_consumer',10,15,'verified','private note'),
('b0000000-0000-4000-8000-000000000202','{OTHER_LOCATION_ID}','producer','primary_consumer',30,15,'published','foreign note');
INSERT INTO public.population_dynamics_record VALUES
('b0000000-0000-4000-8000-000000000103','{LOCATION_ID}','sp-a','species a','producer',CURRENT_DATE,5,'verified','private note'),
('b0000000-0000-4000-8000-000000000203','{OTHER_LOCATION_ID}','sp-b','species b','producer',CURRENT_DATE,7,'published','foreign note');
INSERT INTO public.soil_input_application VALUES
('b0000000-0000-4000-8000-000000000104','{LOCATION_ID}','compost','compost',5,20,CURRENT_DATE,CURRENT_DATE,'verified','private note'),
('b0000000-0000-4000-8000-000000000204','{OTHER_LOCATION_ID}','compost','compost',8,20,CURRENT_DATE,CURRENT_DATE,'published','foreign note');
INSERT INTO public.pest_observation VALUES
('b0000000-0000-4000-8000-000000000105','{LOCATION_ID}',CURRENT_DATE,'pest-a','pest a','insect','low',2,3,0.1,25,60,1,true,'verified','private note','observer a'),
('b0000000-0000-4000-8000-000000000205','{OTHER_LOCATION_ID}',CURRENT_DATE,'pest-b','pest b','insect','low',3,4,0.2,26,61,2,true,'published','foreign note','observer b');
INSERT INTO public.biocontrol_release VALUES
('b0000000-0000-4000-8000-000000000106','{LOCATION_ID}',CURRENT_DATE,'pred-a','pred a','predator','pest-a',4,80,50,2,CURRENT_DATE,'verified','private note'),
('b0000000-0000-4000-8000-000000000206','{OTHER_LOCATION_ID}',CURRENT_DATE,'pred-b','pred b','predator','pest-b',5,80,50,2,CURRENT_DATE,'published','foreign note');
INSERT INTO public.resource_consumption VALUES
('b0000000-0000-4000-8000-000000000107','{LOCATION_ID}','water_liters','L','irrigation',100,false,'verified','private note'),
('b0000000-0000-4000-8000-000000000207','{OTHER_LOCATION_ID}','water_liters','L','irrigation',200,false,'published','foreign note');
INSERT INTO public.harvest_event VALUES
('b0000000-0000-4000-8000-000000000108','{LOCATION_ID}',12,'verified','private note'),
('b0000000-0000-4000-8000-000000000208','{OTHER_LOCATION_ID}',24,'published','foreign note');
INSERT INTO public.species_observation VALUES
('b0000000-0000-4000-8000-000000000109','{LOCATION_ID}','species-a','endangered',3,'verified','observer a','private note',ARRAY['private']),
('b0000000-0000-4000-8000-000000000209','{OTHER_LOCATION_ID}','species-b','vulnerable',4,'published','observer b','foreign note',ARRAY['private']);
INSERT INTO public.livestock_group VALUES
('b0000000-0000-4000-8000-000000000110','{LOCATION_ID}','group-a','goat','local',2,'hay',30,'active','private note'),
('b0000000-0000-4000-8000-000000000210','{OTHER_LOCATION_ID}','group-b','goat','local',3,'hay',31,'active','foreign note');
INSERT INTO public.feed_intake_record VALUES
('b0000000-0000-4000-8000-000000000111','{LOCATION_ID}','b0000000-0000-4000-8000-000000000110',CURRENT_DATE,2,1,'verified','private note'),
('b0000000-0000-4000-8000-000000000211','{OTHER_LOCATION_ID}','b0000000-0000-4000-8000-000000000210',CURRENT_DATE,3,1,'published','foreign note');
INSERT INTO public.token_reward_distribution VALUES
('b0000000-0000-4000-8000-000000000112','{LOCATION_ID}','harvest','KOKO',1,1,'yield',2,'manual',false,'verified','private recipient','private note'),
('b0000000-0000-4000-8000-000000000212','{OTHER_LOCATION_ID}','harvest','KOKO',2,2,'yield',3,'manual',false,'published','foreign recipient','foreign note');
INSERT INTO public.reward_calibration_model VALUES
('b0000000-0000-4000-8000-000000000113','{LOCATION_ID}','model-a','linear',CURRENT_DATE,'{{}}','{{}}',0.8,1,2,1,90,'verified','private note'),
('b0000000-0000-4000-8000-000000000213','{OTHER_LOCATION_ID}','model-b','linear',CURRENT_DATE,'{{}}','{{}}',0.9,2,3,2,91,'published','foreign note');

CREATE VIEW public.v_public_ecological_interaction_summary AS SELECT row.id,row.location_id,row.interaction_type,row.interaction_strength,row.status FROM public.ecological_interaction row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_energy_flow_summary AS SELECT row.id,row.location_id,row.from_trophic_level,row.to_trophic_level,row.biomass_transferred_kg,row.conversion_efficiency_pct,row.status FROM public.energy_flow_measurement row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_population_dynamics_summary AS SELECT row.id,row.location_id,row.species_name,row.species_common_name,row.trophic_level,row.record_date,row.population_count,row.status FROM public.population_dynamics_record row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_soil_input_retention AS SELECT row.id,row.location_id,row.input_type,row.input_name,row.quantity_kg,row.residual_pct,row.application_date,row.residual_measurement_date,row.status FROM public.soil_input_application row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_pest_trends AS SELECT row.id,row.location_id,row.observation_date,row.pest_species,row.pest_common_name,row.pest_category,row.severity,row.incidence_count,row.affected_area_pct,row.outbreak_probability_pct,row.temperature_c,row.humidity_pct,row.predator_count,row.natural_enemy_present,row.status FROM public.pest_observation row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_biocontrol_effectiveness AS SELECT row.id,row.location_id,row.predator_species,row.predator_common_name,row.release_count,row.target_pest,row.release_date,row.follow_up_date,row.effectiveness_pct,row.pest_reduction_pct,row.status FROM public.biocontrol_release row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_resource_efficiency AS SELECT row.id,row.location_id,row.resource_type,row.unit,row.component,row.quantity,row.is_estimated,row.status FROM public.resource_consumption row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_livestock_feed_intake AS SELECT intake.id,intake.location_id,intake.livestock_group_id,intake.record_date,intake.quantity_kg,intake.per_animal_kg,intake.status FROM public.feed_intake_record intake JOIN public.location farm ON farm.id=intake.location_id JOIN public.livestock_group livestock ON livestock.id=intake.livestock_group_id WHERE farm.status='active' AND intake.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_token_reward_distribution AS SELECT row.id,row.location_id,row.reward_type,row.token_type,row.token_amount,row.usd_value,row.linked_metric_key,row.linked_metric_value,row.distribution_method,row.is_onchain,row.status FROM public.token_reward_distribution row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
CREATE VIEW public.v_public_reward_calibration AS SELECT row.id,row.location_id,row.model_name,row.model_type,row.run_date,row.input_metrics,row.output_weights,row.calibration_score,row.total_tokens_distributed,row.token_per_unit_output,row.epoch,row.confidence_level,row.status FROM public.reward_calibration_model row JOIN public.location farm ON farm.id=row.location_id WHERE farm.status='active' AND row.status IN ('verified','published') AND EXISTS (SELECT 1 FROM public.farm_registry_record registry WHERE registry.location_id=farm.id AND registry.status IN ('verified','published'));
"""


def run(command: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        summary = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {summary[-4500:]}")
    return result.stdout.strip()


def psql(docker: str, container: str, sql: str) -> str:
    return run([docker, "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"], sql)


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker CLI is unavailable")
    container = f"kokonut-ecological-source-{uuid.uuid4().hex[:10]}"
    evidence: dict[str, object] = {
        "check": "CAP-038 ecological-modeling signed source migration 550",
        "image": IMAGE,
        "requested_platform": PLATFORM or "native",
        "candidate_or_legacy_modified": False,
        "real_credentials_used": False,
        "result": "failed",
        "assertions": [],
    }
    checks: list[str] = []
    stage = "container startup"
    try:
        command = [docker, "run", "--rm", "--detach", "--name", container, "--network", "none", "--env", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE]
        if PLATFORM:
            command[2:2] = ["--platform", PLATFORM]
        run(command)
        from time import monotonic, sleep
        deadline = monotonic() + 120
        while monotonic() < deadline:
            ready = subprocess.run([docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], text=True, capture_output=True, check=False)
            if ready.returncode == 0:
                break
            sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        evidence["server_architecture"] = run([docker, "exec", container, "uname", "-m"])
        stage = "base signed-worker fixture"
        psql(docker, container, ORGANIC_FIXTURE_MODULE.FIXTURE)
        stage = "ecological fixture schema and projections"
        psql(docker, container, ECOLOGICAL_FIXTURE)
        stage = "migration 549 prerequisite replay"
        psql(docker, container, MIGRATION_549.read_text(encoding="utf-8"))
        stage = "seed synthetic stale ecological grants"
        psql(docker, container, """
GRANT SELECT ON TABLE public.ecological_interaction, public.location,
    public.v_public_ecological_interaction_summary
TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login;
GRANT CREATE ON SCHEMA kokonut_agent_source
TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login,
   kokonut_agent_summary_source_view_owner;
""")
        stage = "migration 550 initial apply"
        psql(docker, container, MIGRATION_550.read_text(encoding="utf-8"))
        stage = "seed synthetic stale grants before replay"
        psql(docker, container, """
GRANT SELECT ON TABLE public.v_public_ecological_species_conservation
TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login;
GRANT CREATE ON SCHEMA kokonut_agent_source
TO kokonut_agent_summary_source_reader, kokonut_agent_summary_source_login,
   kokonut_agent_summary_source_view_owner;
""")
        stage = "migration 550 replay"
        psql(docker, container, MIGRATION_550.read_text(encoding="utf-8"))
        checks.append("migration 550 applies and replays on isolated PostgreSQL 16")
        psql(docker, container, """
INSERT INTO public.ai_summary_agent_draft_request(summary_type)
VALUES ('ecological_modeling');
DO $$ BEGIN
    IF (SELECT count(*) FROM kokonut_security.ai_summary_source_reference_view
         WHERE source_table IN (
             'ecological_interaction', 'energy_flow_measurement',
             'population_dynamics_record', 'soil_input_application',
             'pest_observation', 'biocontrol_release', 'resource_consumption',
             'species_observation', 'token_reward_distribution',
             'reward_calibration_model'
         )) <> 10 THEN
        RAISE EXCEPTION 'ecological source-reference registry is incomplete';
    END IF;
END $$;
""")
        checks.append("worker receipt and ten-source provenance registries accept the task")
        psql(docker, container, f"""
BEGIN;
SELECT set_config('kokonut.test_location', '{LOCATION_ID}', TRUE);
SET LOCAL ROLE kokonut_agent_summary_source_reader;
DO $$ DECLARE n BIGINT; source_view TEXT;
BEGIN
    IF (SELECT count(*) FROM kokonut_agent_source.ecological_interaction) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.energy_flow_measurement) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.population_dynamics_record) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.soil_input_application) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.pest_observation) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.biocontrol_release) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.resource_consumption) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.harvest_event) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.location) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.species_observation) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.livestock_group) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.feed_intake_record) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.token_reward_distribution) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.reward_calibration_model) <> 1 THEN
        RAISE EXCEPTION 'one or more source projections did not enforce exact location scope';
    END IF;
    IF EXISTS (SELECT 1 FROM kokonut_agent_source.ecological_interaction WHERE location_id <> '{LOCATION_ID}')
       OR EXISTS (SELECT 1 FROM kokonut_agent_source.feed_intake_record WHERE location_id <> '{LOCATION_ID}') THEN
        RAISE EXCEPTION 'source projection returned a foreign-location row';
    END IF;
    IF (SELECT count(*) FROM kokonut_agent_source.v_public_ecological_interaction_summary) <> 1
       OR (SELECT count(*) FROM kokonut_agent_source.v_public_ecological_species_conservation) <> 1 THEN
        RAISE EXCEPTION 'provenance projections did not filter to the signed location';
    END IF;
    FOREACH source_view IN ARRAY ARRAY[
        'v_public_ecological_interaction_summary', 'v_public_energy_flow_summary',
        'v_public_population_dynamics_summary', 'v_public_soil_input_retention',
        'v_public_pest_trends', 'v_public_biocontrol_effectiveness',
        'v_public_resource_efficiency', 'v_public_ecological_species_conservation',
        'v_public_token_reward_distribution', 'v_public_reward_calibration'
    ] LOOP
        EXECUTE format('SELECT count(*) FROM kokonut_agent_source.%I', source_view) INTO n;
        IF n <> 1 THEN
            RAISE EXCEPTION 'provenance view % returned % rows, expected one owned row', source_view, n;
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM information_schema.columns
        WHERE table_schema='kokonut_agent_source'
          AND table_name IN ('pest_observation','biocontrol_release','species_observation','token_reward_distribution')
          AND column_name IN ('notes','observer','evidence_urls','recipient_name','source_raw')) THEN
        RAISE EXCEPTION 'scoped ecological projections expose private fields';
    END IF;
    IF has_table_privilege('kokonut_agent_summary_source_reader','public.ecological_interaction','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login','public.ecological_interaction','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_reader','public.location','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login','public.location','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_reader','public.v_public_ecological_interaction_summary','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login','public.v_public_ecological_interaction_summary','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_reader','public.v_public_ecological_species_conservation','SELECT')
       OR has_table_privilege('kokonut_agent_summary_source_login','public.v_public_ecological_species_conservation','SELECT') THEN
        RAISE EXCEPTION 'source identities retained direct table or public-view access';
    END IF;
    IF has_column_privilege('kokonut_agent_summary_source_view_owner','public.biocontrol_release','notes','SELECT')
       OR has_column_privilege('kokonut_agent_summary_source_view_owner','public.livestock_group','notes','SELECT') THEN
        RAISE EXCEPTION 'source-view owner can read unnecessary private fields';
    END IF;
    BEGIN
        PERFORM 1 FROM public.ecological_interaction;
        RAISE EXCEPTION 'source reader queried the raw ecological table';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
ROLLBACK;
""")
        checks.append("signed context scopes all 14 query projections and 10 row-reference views")
        checks.append("migration replay removes stale raw/public-view and schema-create grants")
        psql(docker, container, """
BEGIN;
SET LOCAL ROLE kokonut_agent_summary_source_reader;
DO $$ DECLARE n BIGINT; source_view TEXT;
BEGIN
    FOREACH source_view IN ARRAY ARRAY[
        'ecological_interaction', 'energy_flow_measurement',
        'population_dynamics_record', 'soil_input_application',
        'pest_observation', 'biocontrol_release', 'resource_consumption',
        'harvest_event', 'location', 'species_observation', 'livestock_group',
        'feed_intake_record', 'token_reward_distribution',
        'reward_calibration_model', 'v_public_ecological_interaction_summary',
        'v_public_energy_flow_summary', 'v_public_population_dynamics_summary',
        'v_public_soil_input_retention', 'v_public_pest_trends',
        'v_public_biocontrol_effectiveness', 'v_public_resource_efficiency',
        'v_public_ecological_species_conservation',
        'v_public_token_reward_distribution', 'v_public_reward_calibration'
    ] LOOP
        EXECUTE format('SELECT count(*) FROM kokonut_agent_source.%I', source_view) INTO n;
        IF n <> 0 THEN
            RAISE EXCEPTION 'source view % returned % rows without signed location context', source_view, n;
        END IF;
    END LOOP;
END $$;
ROLLBACK;
""")
        checks.append("all source projections fail closed without signed location context")
        evidence["result"] = "passed"
    except Exception as exc:  # noqa: BLE001 - evidence omits connection and credential values
        evidence["failure_type"] = type(exc).__name__
        evidence["failure_summary"] = str(exc)[:5000]
        evidence["failure_stage"] = stage
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
    evidence["assertions"] = checks
    evidence["assertions_passed"] = len(checks)
    evidence["scope_note"] = (
        "Synthetic current_worker_scope context is used here; cryptographic signature validation is covered by separate worker-context checks."
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
