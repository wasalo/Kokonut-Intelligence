#!/usr/bin/env python3
"""Exercise migration 478 with redacted sequential evidence fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_CHECK = ROOT / "scripts/check-sequential-decision-summary-disposable.py"
MIGRATION = ROOT / "schemas/postgres/478_location_sequential_evidence_timeline.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/cap-036-sequential-evidence-timeline-disposable.json"
spec = importlib.util.spec_from_file_location("sequential_decision_summary_disposable", SUMMARY_CHECK)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the sequential-decision disposable fixture")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
run = helper.run
psql = helper.psql
wait_ready = helper.wait_ready

SCHEMA_EXTENSIONS = r"""
ALTER TABLE public.decision_hypothesis ADD COLUMN created_at timestamptz;
ALTER TABLE public.decision_evidence_event
    ADD COLUMN source_type text,
    ADD COLUMN source_id uuid,
    ADD COLUMN observed_at timestamptz,
    ADD COLUMN ingested_at timestamptz,
    ADD COLUMN evidence_class text,
    ADD COLUMN source_reliability numeric,
    ADD COLUMN dependence_group text,
    ADD COLUMN created_by_party_id uuid,
    ADD COLUMN created_at timestamptz;
ALTER TABLE public.decision_posterior_update
    ADD COLUMN calculation_version text,
    ADD COLUMN effective_evidence_count numeric,
    ADD COLUMN created_at timestamptz;
"""

TIMELINE_FIXTURES = r"""
UPDATE public.decision_hypothesis SET created_at = CASE id
    WHEN 'd0000000-0000-4000-8000-000000000001' THEN '2026-10-01 00:00:00+00'::timestamptz
    WHEN 'd0000000-0000-4000-8000-000000000002' THEN '2026-10-02 00:00:00+00'::timestamptz
    WHEN 'd0000000-0000-4000-8000-000000000003' THEN '2026-10-03 00:00:00+00'::timestamptz
    ELSE '2026-10-04 00:00:00+00'::timestamptz END;
UPDATE public.decision_evidence_event SET
    source_type = 'private_source_type',
    source_id = 'f1000000-0000-4000-8000-000000000001',
    observed_at = CASE id
        WHEN 'e0000000-0000-4000-8000-000000000001' THEN '2026-10-01 01:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000002' THEN '2026-10-02 01:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000003' THEN '2026-10-03 01:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000006' THEN '2026-10-04 01:00:00+00'::timestamptz
        ELSE '2026-10-05 01:00:00+00'::timestamptz END,
    ingested_at = CASE id
        WHEN 'e0000000-0000-4000-8000-000000000001' THEN '2026-10-01 02:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000002' THEN '2026-10-02 02:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000003' THEN '2026-10-03 02:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000006' THEN '2026-10-04 02:00:00+00'::timestamptz
        ELSE '2026-10-05 02:00:00+00'::timestamptz END,
    evidence_class = 'field_observation',
    created_at = CASE id
        WHEN 'e0000000-0000-4000-8000-000000000001' THEN '2026-10-01 03:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000002' THEN '2026-10-02 03:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000003' THEN '2026-10-03 03:00:00+00'::timestamptz
        WHEN 'e0000000-0000-4000-8000-000000000006' THEN '2026-10-04 03:00:00+00'::timestamptz
        ELSE '2026-10-05 03:00:00+00'::timestamptz END;
UPDATE public.decision_posterior_update SET
    calculation_version = 'odds-v1',
    effective_evidence_count = 1,
    created_at = CASE id
        WHEN 'e1000000-0000-4000-8000-000000000001' THEN '2026-10-01 04:00:00+00'::timestamptz
        WHEN 'e1000000-0000-4000-8000-000000000002' THEN '2026-10-03 04:00:00+00'::timestamptz
        ELSE '2026-10-05 04:00:00+00'::timestamptz END;
INSERT INTO public.decision_evidence_event (
    id, hypothesis_id, quality_status, source_ref, value,
    likelihood_hypothesis, likelihood_alternative, source_type, source_id,
    observed_at, ingested_at, evidence_class, source_reliability,
    dependence_group, created_at
) VALUES (
    'e0000000-0000-4000-8000-000000000006',
    'd0000000-0000-4000-8000-000000000003', 'verified',
    'PRIVATE SOLUTION SOURCE', '{"secret":"PRIVATE SOLUTION VALUE"}', 0.8, 0.2,
    'private_source_type', 'f1000000-0000-4000-8000-000000000001',
    '2026-10-04 01:00:00+00', '2026-10-04 02:00:00+00', 'field_observation',
    0.9, 'PRIVATE DEPENDENCE GROUP', '2026-10-04 03:00:00+00'
);
INSERT INTO public.decision_posterior_update (
    id, hypothesis_id, evidence_event_id, calculation_version,
    effective_evidence_count, created_at
) VALUES (
    'e1000000-0000-4000-8000-000000000004',
    'd0000000-0000-4000-8000-000000000001',
    'e0000000-0000-4000-8000-000000000002', 'odds-v1', 2,
    '2026-10-02 04:00:00+00'
);
"""

ACCEPTANCE = r"""
SET ROLE kokonut_runtime;
BEGIN;
SELECT set_config('kokonut.tenant_id', 'f0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.location_id', 'b0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000001', true);
SELECT set_config('kokonut.actor_type', 'operator', true);
DO $$
DECLARE first_page jsonb; second_page jsonb; empty_page jsonb; denied boolean := false;
BEGIN
    first_page := kokonut_security.location_sequential_evidence_timeline(
        'b0000000-0000-4000-8000-000000000001', 2, 0
    );
    IF jsonb_array_length(first_page->'items') <> 2
       OR first_page->>'has_more' <> 'true'
       OR (first_page->>'next_offset')::int <> 2
       OR first_page->'items'->0->>'subject_type' <> 'strategy_plan'
       OR (first_page->'items'->0->>'evidence_sequence')::int <> 1
       OR (first_page->'items'->0->>'posterior_update_sequence')::int <> 1
       OR (first_page->'items'->1->>'evidence_sequence')::int <> 2
       OR (first_page->'items'->1->>'posterior_update_sequence')::int <> 2 THEN
        RAISE EXCEPTION 'first evidence page has incorrect sequence or pagination: %', first_page;
    END IF;
    IF first_page::text ~* '(SECRET|PRIVATE|UNSCOPED|OTHER LOCATION|source_id|source_ref|likelihood|probability|party_id|e0000000|d0000000)' THEN
        RAISE EXCEPTION 'first page exposed narrative, source, evidence, probability, identity, or row identifiers';
    END IF;

    second_page := kokonut_security.location_sequential_evidence_timeline(
        'b0000000-0000-4000-8000-000000000001', 2, 2
    );
    IF jsonb_array_length(second_page->'items') <> 2
       OR second_page->>'has_more' <> 'false'
       OR second_page->'next_offset' <> 'null'::jsonb
       OR second_page->'items'->0->>'subject_type' <> 'threat'
       OR second_page->'items'->1->>'subject_type' <> 'solution'
       OR (second_page->'items'->0->>'hypothesis_sequence')::int <> 2
       OR (second_page->'items'->1->>'hypothesis_sequence')::int <> 3 THEN
        RAISE EXCEPTION 'second evidence page lost scoped subject lineage or stable ordering: %', second_page;
    END IF;
    IF second_page::text ~* '(SECRET|PRIVATE|UNSCOPED|OTHER LOCATION|source_id|source_ref|likelihood|probability|party_id|e0000000|d0000000)' THEN
        RAISE EXCEPTION 'second page exposed narrative, source, evidence, probability, identity, or row identifiers';
    END IF;

    empty_page := kokonut_security.location_sequential_evidence_timeline(
        'b0000000-0000-4000-8000-000000000001', 2, 100
    );
    IF jsonb_array_length(empty_page->'items') <> 0
       OR empty_page->>'has_more' <> 'false' THEN
        RAISE EXCEPTION 'empty evidence page contract is incorrect: %', empty_page;
    END IF;

    denied := false;
    BEGIN
        PERFORM kokonut_security.location_sequential_evidence_timeline(
            'b0000000-0000-4000-8000-000000000002', 2, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'cross-location timeline context was accepted'; END IF;

    denied := false;
    BEGIN
        PERFORM kokonut_security.location_sequential_evidence_timeline(
            'b0000000-0000-4000-8000-000000000001', 0, 0
        );
    EXCEPTION WHEN invalid_parameter_value THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'invalid SQL-level page limit was accepted'; END IF;

    PERFORM set_config('kokonut.actor_id', 'a0000000-0000-4000-8000-000000000002', true);
    denied := false;
    BEGIN
        PERFORM kokonut_security.location_sequential_evidence_timeline(
            'b0000000-0000-4000-8000-000000000001', 2, 0
        );
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'operator without a current location grant was accepted'; END IF;

    denied := false;
    BEGIN PERFORM 1 FROM public.decision_evidence_event;
    EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
    IF NOT denied THEN RAISE EXCEPTION 'runtime can directly read the evidence ledger'; END IF;
END $$;
COMMIT;
RESET ROLE;

DO $$
BEGIN
    IF NOT has_function_privilege(
          'kokonut_runtime',
          'kokonut_security.location_sequential_evidence_timeline(uuid,integer,integer)',
          'EXECUTE'
       )
       OR has_function_privilege(
          'kokonut_directus_runtime',
          'kokonut_security.location_sequential_evidence_timeline(uuid,integer,integer)',
          'EXECUTE'
       )
       OR has_table_privilege('kokonut_runtime', 'public.decision_evidence_event', 'SELECT')
       OR has_table_privilege('kokonut_sequential_reader', 'public.party', 'SELECT')
       OR has_table_privilege('kokonut_sequential_reader', 'public.decision_evidence_event', 'UPDATE') THEN
        RAISE EXCEPTION 'timeline function or reader privilege boundary failed';
    END IF;
END $$;
"""


def main() -> int:
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    container = f"kokonut-sequential-timeline-{uuid.uuid4().hex[:8]}"
    evidence: dict[str, object] = {
        "result": "failed",
        "migration": MIGRATION.name,
        "database_target": "new disposable PostgreSQL 16 container",
        "candidate_or_legacy_modified": False,
        "checks": [
            "migrations 460 and 478 apply; migration 478 replays",
            "sequence pages include only exact location strategy-plan, threat, and linked/origin solution lineages",
            "event and posterior update order are stable across pages",
            "source text, IDs, raw values, likelihoods, probabilities, and party identity remain omitted",
            "signed exact-location read grants, page bounds, runtime execution, and Directus denial are enforced",
        ],
    }
    try:
        run([docker, "run", "--detach", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=local-only-disposable", "postgres:16"])
        wait_ready(container, docker)
        psql(docker, container, helper.FIXTURE + SCHEMA_EXTENSIONS)
        summary_migration = (ROOT / "schemas/postgres/460_location_scoped_sequential_decision_summary.sql").read_text()
        migration = MIGRATION.read_text(encoding="utf-8")
        psql(docker, container, summary_migration)
        psql(docker, container, migration)
        psql(docker, container, migration)
        psql(docker, container, helper.ACCEPTANCE)
        psql(docker, container, TIMELINE_FIXTURES)
        psql(docker, container, ACCEPTANCE)
        evidence["result"] = "passed"
        evidence["acceptance_groups_passed"] = 8
        print("PASS: migration 478 applies/replays and all eight disposable PostgreSQL acceptance groups passed")
        result = 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = 1
    finally:
        subprocess.run([docker, "rm", "--force", container], text=True, capture_output=True, check=False)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
