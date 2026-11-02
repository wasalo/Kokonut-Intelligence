#!/usr/bin/env python3
"""Exercise migration 700's signed, location-scoped tension actions on disposable PG16."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/governance_tension_actions_disposable.sql"
MIGRATION_437 = ROOT / "schemas/postgres/437_governance_operator_binding_and_actions.sql"
MIGRATION_700 = ROOT / "schemas/postgres/700_governance_tension_location_actions.sql"
OUTPUT = ROOT / "docs/refactor/builds/2026-10-30-recovery/governance-tension-location-actions-700-disposable.json"

LOCATION = "a0000000-0000-4000-8000-000000000201"
OTHER_LOCATION = "a0000000-0000-4000-8000-000000000202"
ORG = "a0000000-0000-4000-8000-000000000101"
OPERATOR = "a0000000-0000-4000-8000-000000000401"
OTHER_OPERATOR = "a0000000-0000-4000-8000-000000000402"
PERSON = "a0000000-0000-4000-8000-000000000501"
OTHER_PERSON = "a0000000-0000-4000-8000-000000000502"
TENSION = "a0000000-0000-4000-8000-000000000901"
OTHER_TENSION = "a0000000-0000-4000-8000-000000000902"
WORK_ITEM = "a0000000-0000-4000-8000-000000000911"
OTHER_WORK_ITEM = "a0000000-0000-4000-8000-000000000912"
INTEREST = "a0000000-0000-4000-8000-000000000921"
NETWORK_ROLE = "a0000000-0000-4000-8000-000000000811"

ADDITIONS = f"""
ALTER TABLE public.governance_tension
    ADD COLUMN owner_role_id UUID REFERENCES public.governance_role(id),
    ADD COLUMN owner_party_id UUID REFERENCES public.party(id),
    ADD COLUMN work_item_id UUID REFERENCES public.work_item(id),
    ADD COLUMN decision_id UUID,
    ADD COLUMN grievance_id UUID,
    ADD COLUMN resolution_summary TEXT,
    ADD COLUMN deferred_until TIMESTAMPTZ,
    ADD COLUMN review_due_at TIMESTAMPTZ;
CREATE TABLE public.governance_tension_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tension_id UUID NOT NULL REFERENCES public.governance_tension(id),
    link_type VARCHAR(30) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID NOT NULL,
    summary TEXT,
    created_by_party_id UUID REFERENCES public.party(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (tension_id, link_type, entity_type, entity_id)
);
CREATE TABLE public.stakeholder_interest (
    id UUID PRIMARY KEY, scope_type TEXT NOT NULL, scope_id UUID
);
CREATE TABLE public.stakeholder_engagement_plan (
    id UUID PRIMARY KEY, scope_type TEXT NOT NULL, scope_id UUID
);
CREATE TABLE public.stakeholder_commitment (
    id UUID PRIMARY KEY, plan_id UUID NOT NULL REFERENCES public.stakeholder_engagement_plan(id)
);
CREATE TABLE public.stakeholder_decision_evidence (
    id UUID PRIMARY KEY, decision_id UUID NOT NULL REFERENCES public.stakeholder_decision(id)
);
CREATE TABLE public.stakeholder_decision_outcome (
    id UUID PRIMARY KEY, decision_id UUID NOT NULL REFERENCES public.stakeholder_decision(id)
);
CREATE TABLE public.stakeholder_engagement_outcome (
    id UUID PRIMARY KEY, plan_id UUID NOT NULL REFERENCES public.stakeholder_engagement_plan(id)
);
CREATE TABLE public.stakeholder_grievance_case (
    id UUID PRIMARY KEY, location_id UUID REFERENCES public.location(id)
);
CREATE TABLE public.grievance_evidence (
    id UUID PRIMARY KEY, case_id UUID NOT NULL REFERENCES public.stakeholder_grievance_case(id)
);
CREATE TABLE public.party_relationship (
    id UUID PRIMARY KEY, scope_type TEXT NOT NULL, scope_id UUID
);
CREATE TABLE public.governance_proposal (
    id UUID PRIMARY KEY, affected_scope_type TEXT NOT NULL, affected_scope_id UUID
);
INSERT INTO public.location (id, organization_id, status)
VALUES ('{OTHER_LOCATION}', '{ORG}', 'active');
INSERT INTO public.work_item (id, location_id, status) VALUES
    ('{WORK_ITEM}', '{LOCATION}', 'in_progress'),
    ('{OTHER_WORK_ITEM}', '{OTHER_LOCATION}', 'in_progress');
INSERT INTO public.stakeholder_interest (id, scope_type, scope_id)
VALUES ('{INTEREST}', 'location', '{LOCATION}');
INSERT INTO public.stakeholder_decision (id, scope_type, scope_id, status)
VALUES ('a0000000-0000-4000-8000-000000000922', 'location', '{LOCATION}', 'submitted');
INSERT INTO public.governance_tension (
    id, tension_key, title, description, tension_type, severity, urgency,
    scope_type, scope_id, reported_by_party_id, status
) VALUES
    ('{TENSION}', 'test:loc:1', 'Tension in location', 'Synthetic scoped tension',
     'unclear_accountability', 3, 2, 'location', '{LOCATION}', '{PERSON}', 'submitted'),
    ('{OTHER_TENSION}', 'test:loc:2', 'Tension elsewhere', 'Synthetic foreign tension',
     'unclear_accountability', 3, 2, 'location', '{OTHER_LOCATION}', '{OTHER_PERSON}', 'submitted');
INSERT INTO public.operator_governance_party_binding (
    operator_id, party_id, bound_by, binding_reason
) VALUES
    ('{OPERATOR}', '{PERSON}', 'disposable checker', 'synthetic exact mapping'),
    ('{OTHER_OPERATOR}', '{OTHER_PERSON}', 'disposable checker', 'synthetic exact mapping');
INSERT INTO public.operator_scope_grant (
    id, operator_id, resource, action, location_id, organization_id, revoked_at
) VALUES
    ('a0000000-0000-4000-8000-000000000931', '{OPERATOR}', 'governance_tension', 'triage', '{LOCATION}', '{ORG}', NULL),
    ('a0000000-0000-4000-8000-000000000932', '{OPERATOR}', 'governance_tension', 'start', '{LOCATION}', '{ORG}', NULL),
    ('a0000000-0000-4000-8000-000000000933', '{OPERATOR}', 'governance_tension', 'link', '{LOCATION}', '{ORG}', NULL),
    ('a0000000-0000-4000-8000-000000000934', '{OPERATOR}', 'governance_tension', 'link_work_item', '{LOCATION}', '{ORG}', NULL),
    ('a0000000-0000-4000-8000-000000000935', '{OPERATOR}', 'governance_tension', 'resolve', '{LOCATION}', '{ORG}', NULL),
    ('a0000000-0000-4000-8000-000000000936', '{OPERATOR}', 'governance_tension', 'defer', '{LOCATION}', '{ORG}', NULL);
"""


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def psql(container: str, statement: str, *, check: bool = True):
    return run(
        ["docker", "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-t", "-A", "-U", "postgres", "-d", "postgres"],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )


def value(container: str, statement: str) -> str:
    lines = [line.strip() for line in psql(container, statement).stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def signed(operator_id: str, location_id: str, query: str) -> str:
    return f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG}', FALSE);
        SELECT set_config('test.location_id', '{location_id}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {query.rstrip(';')};
        RESET ROLE;
    """


def deny(container: str, statement: str, expected: str, label: str) -> None:
    result = psql(container, statement, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or expected not in output:
        raise AssertionError(f"{label}: expected SQLSTATE {expected}; got {result.returncode}: {output}")


def main() -> None:
    container = f"kokonut-tension-actions-700-{uuid.uuid4().hex[:8]}"
    password = secrets.token_urlsafe(24)
    checks: list[str] = []
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    run([docker, "run", "-d", "--rm", "--network", "none", "--name", container,
         "-e", f"POSTGRES_PASSWORD={password}", "postgres:16-alpine"])
    started = time.monotonic()
    try:
        for _ in range(90):
            ready = run([docker, "exec", container, "pg_isready", "-h", "127.0.0.1",
                         "-U", "postgres", "-d", "postgres"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL 16 did not become ready")

        psql(container, FIXTURE.read_text(encoding="utf-8"))
        psql(container, MIGRATION_437.read_text(encoding="utf-8"))
        psql(container, ADDITIONS)
        migration = MIGRATION_700.read_text(encoding="utf-8")
        psql(container, migration)
        psql(container, migration)
        checks.append("migration 700 applies and replays transactionally on isolated PostgreSQL 16")

        permissions = value(container, """
            SELECT has_function_privilege('kokonut_runtime',
                'kokonut_security.mutate_governance_tension_action(uuid,uuid,text,uuid,jsonb,text)', 'EXECUTE')
             AND NOT has_table_privilege('kokonut_runtime',
                'public.governance_tension_action_request', 'SELECT')
             AND NOT has_table_privilege('kokonut_directus_runtime',
                'public.governance_tension_action_request', 'INSERT')
             AND NOT has_function_privilege('public',
                'kokonut_security.mutate_governance_tension_action(uuid,uuid,text,uuid,jsonb,text)', 'EXECUTE');
        """)
        if permissions != "t":
            raise AssertionError(f"migration 700 function/receipt privileges are incorrect: {permissions}")
        checks.append("runtime has only the bounded function entry point; public, runtime, and Directus cannot access the receipt table")

        triage_request = "a0000000-0000-4000-8000-000000000941"
        triage_content = json.dumps({
            "owner_role_id": NETWORK_ROLE,
            "owner_party_id": None,
            "review_due_at": "2026-11-15T12:00:00Z",
            "note": "Initial triage",
        }, separators=(",", ":"))
        triage_sql = f"SELECT tension_id, action, status, request_id, link_id IS NULL FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'triage', '{triage_request}', '{triage_content}'::jsonb, 'Assign for review');"
        first = value(container, signed(OPERATOR, LOCATION, triage_sql))
        replay = value(container, signed(OPERATOR, LOCATION, triage_sql))
        if first != replay or not first.endswith("|triage|triaged|" + triage_request + "|t"):
            raise AssertionError(f"triage/replay contract mismatch: {first!r}, {replay!r}")
        if value(container, "SELECT count(*) FROM public.governance_tension_action_request;") != "1":
            raise AssertionError("same-request replay wrote duplicate action receipts")
        if value(container, "SELECT count(*) FROM public.governance_tension_event;") != "1":
            raise AssertionError("same-request replay wrote duplicate lifecycle events")
        checks.append("triage validates active location role, changes only the governed state, and replay returns the saved result without duplicate audit")

        deny(container, signed(OPERATOR, LOCATION,
            triage_sql.replace("'triage',", "'triage',", 1).replace("Assign for review", "Different reason")),
            "22023", "same request with changed reason")
        deny(container, signed(OTHER_OPERATOR, LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'start', '{uuid.uuid4()}', '{{}}'::jsonb, 'start')"),
            "42501", "missing exact action grant")
        deny(container, "SET ROLE kokonut_runtime; SELECT * FROM kokonut_security.mutate_governance_tension_action("
            f"'{LOCATION}', '{TENSION}', 'start', '{uuid.uuid4()}', '{{}}'::jsonb, 'start');",
            "42501", "missing signed context")
        deny(container, signed(OPERATOR, OTHER_LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{OTHER_LOCATION}', '{TENSION}', 'start', '{uuid.uuid4()}', '{{}}'::jsonb, 'start')"),
            "42501", "mismatched signed location and missing exact grant")
        checks.append("denies changed-content retries, absent grants/context, and mismatched signed location")

        start_request = "a0000000-0000-4000-8000-000000000942"
        start = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'start', '{start_request}', '{{}}'::jsonb, 'Begin work')"))
        if start != "in_progress":
            raise AssertionError(f"start should transition triaged tension to in_progress, got {start!r}")

        link_request = "a0000000-0000-4000-8000-000000000943"
        linked = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status, link_id IS NOT NULL FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'link', '{link_request}', '{{\"link_type\":\"interest\",\"entity_type\":\"stakeholder_interest\",\"entity_id\":\"{INTEREST}\",\"summary\":\"Scoped interest\"}}'::jsonb, 'Link evidence')"))
        if linked != "in_progress|t":
            raise AssertionError(f"location-scoped link action failed: {linked!r}")
        deny(container, signed(OPERATOR, LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'link', '{uuid.uuid4()}', '{{\"link_type\":\"work_item\",\"entity_type\":\"work_item\",\"entity_id\":\"{OTHER_WORK_ITEM}\"}}'::jsonb, 'Cross-location link')"),
            "P0002", "cross-location linked work item")
        checks.append("start and link preserve the intended lifecycle, while linked references must resolve inside the same location")

        work_request = "a0000000-0000-4000-8000-000000000944"
        work_result = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status, link_id IS NOT NULL FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'link_work_item', '{work_request}', '{{\"work_item_id\":\"{WORK_ITEM}\"}}'::jsonb, 'Attach local work')"))
        if work_result != "in_progress|t":
            raise AssertionError(f"link_work_item failed: {work_result!r}")

        defer_request = "a0000000-0000-4000-8000-000000000945"
        deferred = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'defer', '{defer_request}', '{{\"deferred_until\":\"2026-12-01T00:00:00Z\"}}'::jsonb, 'Wait for evidence')"))
        if deferred != "deferred":
            raise AssertionError(f"defer transition failed: {deferred!r}")
        restarted = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'start', '{uuid.uuid4()}', '{{}}'::jsonb, 'Resume')"))
        if restarted != "in_progress":
            raise AssertionError(f"deferred tension should resume to in_progress: {restarted!r}")
        resolved = value(container, signed(OPERATOR, LOCATION,
            f"SELECT status FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'resolve', '{uuid.uuid4()}', '{{\"resolution_summary\":\"Evidence reviewed and action complete\"}}'::jsonb, 'Close the coordination gap')"))
        if resolved != "resolved":
            raise AssertionError(f"resolve transition failed: {resolved!r}")
        deny(container, signed(OPERATOR, LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{TENSION}', 'start', '{uuid.uuid4()}', '{{}}'::jsonb, 'terminal re-open')"),
            "55000", "terminal transition")
        checks.append("work-item attach, defer, resume, resolve, and terminal-state denial follow the explicit state graph")

        deny(container, signed(OPERATOR, LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{OTHER_TENSION}', 'triage', '{uuid.uuid4()}', '{{\"owner_party_id\":\"{PERSON}\"}}'::jsonb, 'wrong tenant')"),
            "P0002", "foreign tension ID")
        deny(container, signed(OPERATOR, LOCATION,
            f"SELECT * FROM kokonut_security.mutate_governance_tension_action('{LOCATION}', '{OTHER_TENSION}', 'link', '{uuid.uuid4()}', '{{\"link_type\":\"decision\",\"entity_type\":\"stakeholder_decision\",\"entity_id\":\"a0000000-0000-4000-8000-000000000922\"}}'::jsonb, 'wrong tension')"),
            "P0002", "foreign tension before reference resolution")
        deny(container, "SET ROLE kokonut_runtime; SELECT * FROM public.governance_tension_action_request;",
            "42501", "runtime receipt read")
        deny(container, "SET ROLE kokonut_runtime; INSERT INTO public.governance_tension_action_request "
            f"(operator_id, actor_party_id, location_id, tension_id, request_id, action, requested_content, reason, from_status, result_status, result_updated_at) "
            f"VALUES ('{OPERATOR}', '{PERSON}', '{LOCATION}', '{TENSION}', '{uuid.uuid4()}', 'start', '{{}}', 'x', 'triaged', 'in_progress', now());",
            "42501", "runtime receipt insert")
        checks.append("runtime cannot read/write private action receipts, and the function exposes no actor identity")

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        evidence = {
            "migration": MIGRATION_700.name,
            "status": "passed",
            "checks": checks,
            "database_target": "network-disabled temporary PostgreSQL 16 container",
            "candidate_legacy_production_touched": False,
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    finally:
        run([docker, "rm", "-f", container], check=False)


if __name__ == "__main__":
    main()
