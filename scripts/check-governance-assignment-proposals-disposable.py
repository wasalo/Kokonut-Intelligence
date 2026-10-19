#!/usr/bin/env python3
"""Exercise governance role nomination, review, definition mutation/lifecycle, and tactical actions on disposable PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/governance_tension_actions_disposable.sql"
TACTICAL_FIXTURE = ROOT / "tests/fixtures/governance_tactical_actions_disposable.sql"
MIGRATIONS = (
    ROOT / "schemas/postgres/437_governance_operator_binding_and_actions.sql",
    ROOT / "schemas/postgres/438_governance_role_assignment_proposals.sql",
    ROOT / "schemas/postgres/439_governance_role_assignment_proposal_readback.sql",
    ROOT / "schemas/postgres/440_governance_role_assignment_review.sql",
    ROOT / "schemas/postgres/441_governance_tactical_actions.sql",
    ROOT / "schemas/postgres/442_governance_definition_lifecycle.sql",
    ROOT / "schemas/postgres/443_governance_definition_mutations.sql",
    ROOT / "schemas/postgres/444_governance_tactical_session_creation.sql",
    ROOT / "schemas/postgres/445_governance_tactical_content_mutations.sql",
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-19-recovery/governance-tactical-content-mutations-disposable.json"

ORG_ID = "a0000000-0000-4000-8000-000000000101"
LOCATION_ID = "a0000000-0000-4000-8000-000000000201"
OPERATOR_ONE = "a0000000-0000-4000-8000-000000000401"
OPERATOR_TWO = "a0000000-0000-4000-8000-000000000402"
OPERATOR_THREE = "a0000000-0000-4000-8000-000000000403"
PARTY_ONE = "a0000000-0000-4000-8000-000000000501"
PARTY_TWO = "a0000000-0000-4000-8000-000000000502"
PARTY_RETIRED = "a0000000-0000-4000-8000-000000000504"
PARTY_THREE = "a0000000-0000-4000-8000-000000000505"
ROLE_LOCATION = "a0000000-0000-4000-8000-000000000811"
ROLE_NETWORK = "a0000000-0000-4000-8000-000000000812"
TACTICAL_START_ITEM = "a0000000-0000-4000-8000-000000000911"
TACTICAL_MISMATCH_ITEM = "a0000000-0000-4000-8000-000000000912"
TACTICAL_CANCEL_ITEM = "a0000000-0000-4000-8000-000000000913"
TACTICAL_ROLE_ITEM = "a0000000-0000-4000-8000-000000000914"
TACTICAL_COMPLETED_SESSION_ITEM = "a0000000-0000-4000-8000-000000000915"
TACTICAL_NETWORK_ROLE_ITEM = "a0000000-0000-4000-8000-000000000916"
DEFINITION_CIRCLE = "a0000000-0000-4000-8000-000000000917"
DEFINITION_ROLE = "a0000000-0000-4000-8000-000000000918"
MUTATION_PARENT_CIRCLE = "a0000000-0000-4000-8000-000000000801"
NETWORK_CIRCLE = "a0000000-0000-4000-8000-000000000802"


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        display_command = [
            "POSTGRES_PASSWORD=<redacted>" if part.startswith("POSTGRES_PASSWORD=") else part
            for part in command
        ]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(display_command)}\n{details}"
        )
    return result


def docker_sql(container: str, statement: str, *, check: bool = True):
    return run(
        [
            "docker", "exec", "-i", container, "psql", "-X", "-v",
            "ON_ERROR_STOP=1", "-t", "-A", "-U", "postgres", "-d", "postgres",
        ],
        input_text="\\set VERBOSITY verbose\n" + statement,
        check=check,
    )


def runtime_call(container: str, operator_id: str, sql: str):
    return docker_sql(
        container,
        f"""
        SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {sql}
        """,
    )


def assert_sqlstate(container: str, statement: str, sqlstate: str, label: str):
    result = docker_sql(container, statement, check=False)
    if result.returncode == 0 or sqlstate not in (result.stdout + result.stderr):
        raise AssertionError(
            f"{label}: expected SQLSTATE {sqlstate}, got rc={result.returncode}: "
            f"{result.stdout}{result.stderr}"
        )


def run_acceptance(container: str) -> list[str]:
    checks: list[str] = []
    docker_sql(container, FIXTURE.read_text())
    docker_sql(container, MIGRATIONS[0].read_text())
    migration_sql = MIGRATIONS[1].read_text()
    docker_sql(container, migration_sql)
    docker_sql(container, migration_sql)
    readback_sql = MIGRATIONS[2].read_text()
    docker_sql(container, readback_sql)
    docker_sql(container, readback_sql)
    review_sql = MIGRATIONS[3].read_text()
    docker_sql(container, review_sql)
    docker_sql(container, review_sql)
    docker_sql(container, TACTICAL_FIXTURE.read_text())
    tactical_sql = MIGRATIONS[4].read_text()
    docker_sql(container, tactical_sql)
    docker_sql(container, tactical_sql)
    definition_sql = MIGRATIONS[5].read_text()
    docker_sql(container, definition_sql)
    docker_sql(container, definition_sql)
    mutation_sql = MIGRATIONS[6].read_text()
    docker_sql(container, mutation_sql)
    docker_sql(container, mutation_sql)
    session_creation_sql = MIGRATIONS[7].read_text()
    docker_sql(container, session_creation_sql)
    docker_sql(container, session_creation_sql)
    tactical_content_sql = MIGRATIONS[8].read_text()
    docker_sql(container, tactical_content_sql)
    docker_sql(container, tactical_content_sql)
    checks.append("migrations 438–445 apply and replay transactionally after migration 437")

    privilege = docker_sql(
        container,
        """
        SELECT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'SELECT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'INSERT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'UPDATE')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment', 'DELETE')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'INSERT')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'UPDATE')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment', 'DELETE')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_request', 'SELECT')
           AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_request', 'INSERT')
           AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment_request', 'SELECT')
           AND has_function_privilege('kokonut_runtime',
             'kokonut_security.propose_governance_role_assignment(uuid,uuid,uuid,uuid,text,text)', 'EXECUTE')
           AND has_function_privilege('kokonut_runtime',
             'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamp with time zone,uuid)', 'EXECUTE')
           AND NOT has_function_privilege('kokonut_directus_runtime',
             'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamp with time zone,uuid)', 'EXECUTE');
        """,
    ).stdout.strip()
    if privilege != "t":
        raise AssertionError(f"role nomination ACL contract failed: {privilege}")
    checks.append("runtime retains assignment reads and bounded proposal execution but loses direct table writes and ledger access")

    docker_sql(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_ONE}', '{PARTY_ONE}', 'test administrator', 'explicit test binding'
            ); RESET ROLE;""",
    )

    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('a0000000-0000-4000-8000-000000000713', '{OPERATOR_ONE}', 'governance_tactical', 'start', '{LOCATION_ID}', '{ORG_ID}', NULL),
          ('a0000000-0000-4000-8000-000000000714', '{OPERATOR_ONE}', 'governance_tactical', 'dispose', '{LOCATION_ID}', '{ORG_ID}', NULL),
          ('a0000000-0000-4000-8000-000000000715', '{OPERATOR_ONE}', 'governance_tactical', 'cancel', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )

    def tactical_transition(operator_id, item_id, action, request_id, reason,
                            disposition_type=None, disposition_summary=None):
        disposition_type_sql = "NULL" if disposition_type is None else f"'{disposition_type}'"
        summary_sql = "NULL" if disposition_summary is None else "'" + disposition_summary.replace("'", "''") + "'"
        return runtime_call(
            container,
            operator_id,
            f"""SELECT event_id::text || '|' || item_id::text || '|' || action || '|' ||
                       prior_status || '|' || resulting_status || '|' || actor_party_id::text
                  FROM kokonut_security.transition_governance_tactical_item(
                    '{LOCATION_ID}', '{item_id}', '{request_id}', '{action}',
                    '{reason.replace("'", "''")}', {disposition_type_sql}, {summary_sql}
                  );""",
        ).stdout.strip().splitlines()[-1]

    start_request_id = str(uuid.uuid4())
    started_item = tactical_transition(
        OPERATOR_ONE, TACTICAL_START_ITEM, "start", start_request_id,
        "Assigned steward began the action.",
    )
    started_retry = tactical_transition(
        OPERATOR_ONE, TACTICAL_START_ITEM, "start", start_request_id,
        "Assigned steward began the action.",
    )
    if started_item != started_retry or not started_item.endswith(
        f"|{TACTICAL_START_ITEM}|start|open|in_progress|{PARTY_ONE}"
    ):
        raise AssertionError(f"start must transition once and replay exactly: {started_item} / {started_retry}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{TACTICAL_START_ITEM}', '{start_request_id}', 'start',
            'Changed retry reason', NULL, NULL);"""),
        "22023",
        "reject tactical action key reuse with changed content",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{TACTICAL_MISMATCH_ITEM}', '{uuid.uuid4()}', 'start',
            'Not the assigned person', NULL, NULL);"""),
        "42501",
        "reject start by a person who does not own the item",
    )
    dispose_request_id = str(uuid.uuid4())
    disposed_item = tactical_transition(
        OPERATOR_ONE, TACTICAL_START_ITEM, "dispose", dispose_request_id,
        "Verified the follow-up was completed.", "next_action",
        "The action is complete and documented.",
    )
    disposed_retry = tactical_transition(
        OPERATOR_ONE, TACTICAL_START_ITEM, "dispose", dispose_request_id,
        "Verified the follow-up was completed.", "next_action",
        "The action is complete and documented.",
    )
    if disposed_item != disposed_retry or not disposed_item.endswith(
        f"|{TACTICAL_START_ITEM}|dispose|in_progress|disposed|{PARTY_ONE}"
    ):
        raise AssertionError(f"dispose must transition once and replay exactly: {disposed_item} / {disposed_retry}")
    cancel_request_id = str(uuid.uuid4())
    cancelled_item = tactical_transition(
        OPERATOR_ONE, TACTICAL_CANCEL_ITEM, "cancel", cancel_request_id,
        "The planned action is no longer needed.",
    )
    if not cancelled_item.endswith(
        f"|{TACTICAL_CANCEL_ITEM}|cancel|open|cancelled|{PARTY_ONE}"
    ):
        raise AssertionError(f"cancel lifecycle transition failed: {cancelled_item}")
    role_start = tactical_transition(
        OPERATOR_ONE, TACTICAL_ROLE_ITEM, "start", str(uuid.uuid4()),
        "Current non-recused role holder began the action.",
    )
    if not role_start.endswith(
        f"|{TACTICAL_ROLE_ITEM}|start|open|in_progress|{PARTY_ONE}"
    ):
        raise AssertionError(f"current role holder could not start assigned action: {role_start}")
    completed_session_start = tactical_transition(
        OPERATOR_ONE, TACTICAL_COMPLETED_SESSION_ITEM, "start", str(uuid.uuid4()),
        "The follow-up continues after the meeting closed.",
    )
    if not completed_session_start.endswith(
        f"|{TACTICAL_COMPLETED_SESSION_ITEM}|start|open|in_progress|{PARTY_ONE}"
    ):
        raise AssertionError(f"completed session incorrectly blocked its action: {completed_session_start}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{TACTICAL_NETWORK_ROLE_ITEM}', '{uuid.uuid4()}', 'start',
            'Network role is outside this location scope', NULL, NULL);"""),
        "42501",
        "reject network role ownership for a location tactical action",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{TACTICAL_ROLE_ITEM}', '{uuid.uuid4()}', 'start',
            'No exact action grant', NULL, NULL);"""),
        "42501",
        "reject tactical action without exact action grant",
    )
    tactical_state = docker_sql(
        container,
        f"""SELECT status || '|' || disposition_type || '|' || disposition_summary || '|' || disposed_by_party_id::text || '|' ||
                       (SELECT count(*) FROM public.governance_tactical_action_event WHERE item_id = '{TACTICAL_START_ITEM}')
              FROM public.governance_tactical_item WHERE id = '{TACTICAL_START_ITEM}';""",
    ).stdout.strip()
    if tactical_state != f"disposed|next_action|The action is complete and documented.|{PARTY_ONE}|2":
        raise AssertionError(f"tactical lifecycle and immutable event rows diverged: {tactical_state}")
    checks.append("start, dispose, and cancel enforce signed location action grants, direct or same-location role ownership, completed-session follow-up, required reasons, exact idempotent replay, and append-only actor history")

    tactical_acl = docker_sql(
        container,
        """SELECT has_table_privilege('kokonut_governance_action_owner', 'public.governance_tactical_action_event', 'INSERT')
              AND NOT has_table_privilege('kokonut_governance_action_owner', 'public.governance_tactical_action_event', 'UPDATE')
              AND has_column_privilege('kokonut_governance_action_owner', 'public.governance_tactical_item', 'status', 'UPDATE')
              AND has_column_privilege('kokonut_governance_action_owner', 'public.governance_tactical_item', 'requested_next_action', 'UPDATE')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_item', 'INSERT')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_item', 'UPDATE')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_item', 'DELETE')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_item', 'INSERT')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_item', 'UPDATE')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_item', 'DELETE')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_action_event', 'SELECT')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_action_event', 'SELECT')
              AND has_function_privilege('kokonut_runtime',
                'kokonut_security.transition_governance_tactical_item(uuid,uuid,uuid,text,text,text,text)', 'EXECUTE')
              AND NOT has_function_privilege('kokonut_directus_runtime',
                'kokonut_security.transition_governance_tactical_item(uuid,uuid,uuid,text,text,text,text)', 'EXECUTE');""",
    ).stdout.strip()
    if tactical_acl != "t":
        raise AssertionError(f"tactical action ACL contract failed: {tactical_acl}")
    for database_role in ("kokonut_runtime", "kokonut_directus_runtime"):
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; UPDATE public.governance_tactical_item SET status = 'disposed' WHERE id = '{TACTICAL_CANCEL_ITEM}';",
            "42501",
            f"direct {database_role} tactical lifecycle write",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; SELECT * FROM public.governance_tactical_action_event;",
            "42501",
            f"private action history read by {database_role}",
        )
    assert_sqlstate(
        container,
        f"UPDATE public.governance_tactical_action_event SET reason = 'rewritten' WHERE item_id = '{TACTICAL_START_ITEM}';",
        "P0001",
        "immutable tactical action event history",
    )
    checks.append("runtime and Directus roles cannot mutate tactical lifecycle rows or read/write the private action ledger; append-only history rejects edits")

    request_id = str(uuid.uuid4())
    proposal_sql = f"""SELECT assignment_id || '|' || role_id || '|' || assignment_type || '|' || status
        FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{request_id}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL
        );"""
    created = runtime_call(container, OPERATOR_ONE, proposal_sql).stdout.strip().splitlines()[-1]
    replayed = runtime_call(container, OPERATOR_ONE, proposal_sql).stdout.strip().splitlines()[-1]
    if created != replayed or not created.endswith("|primary|proposed"):
        raise AssertionError(f"proposal must replay as the same pending assignment: {created} / {replayed}")
    assignment_id = created.split("|")[0]
    state = docker_sql(
        container,
        f"""SELECT status || '|' || COALESCE(approved_by_party_id::text, 'null') || '|' ||
                       COALESCE(effective_from::text, 'null') || '|' || assigned_by_party_id::text || '|' || party_id::text
              FROM public.governance_role_assignment WHERE id = '{assignment_id}';""",
    ).stdout.strip()
    counts = docker_sql(
        container,
        f"""SELECT (SELECT count(*) FROM public.governance_role_assignment WHERE id = '{assignment_id}') || '|' ||
                   (SELECT count(*) FROM public.governance_role_assignment_request WHERE operator_id = '{OPERATOR_ONE}' AND request_id = '{request_id}');""",
    ).stdout.strip()
    if state != f"proposed|null|null|{PARTY_ONE}|{PARTY_TWO}" or counts != "1|1":
        raise AssertionError(f"proposal must remain unapproved and create one ledger row: {state}, {counts}")
    checks.append("active bound operator creates an attributed location role nomination; exact retry returns the same proposed row without activation")

    second_request_id = str(uuid.uuid4())
    second_proposal_sql = f"""SELECT assignment_id::text || '|' || status
        FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{second_request_id}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL
        );"""
    second_created = runtime_call(container, OPERATOR_ONE, second_proposal_sql).stdout.strip().splitlines()[-1]
    second_assignment_id, second_status = second_created.split("|")
    if second_status != "proposed" or second_assignment_id == assignment_id:
        raise AssertionError(f"second operator nomination was not created as a distinct proposal: {second_created}")

    docker_sql(
        container,
        f"""SET ROLE kokonut_governance_identity_admin;
            SELECT binding_id FROM kokonut_security.bind_operator_governance_party(
                '{OPERATOR_TWO}', '{PARTY_THREE}', 'test administrator', 'explicit test binding'
            ); RESET ROLE;""",
    )
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant (
                id, operator_id, resource, action, location_id, organization_id, revoked_at
            ) VALUES
              ('a0000000-0000-4000-8000-000000000721', '{OPERATOR_ONE}', 'governance_roles', 'submit', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000722', '{OPERATOR_TWO}', 'governance_roles', 'activate', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000723', '{OPERATOR_TWO}', 'governance_roles', 'approve', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000724', '{OPERATOR_TWO}', 'governance_roles', 'suspend', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000725', '{OPERATOR_TWO}', 'governance_roles', 'retire', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000726', '{OPERATOR_ONE}', 'governance_roles', 'activate', '{LOCATION_ID}', '{ORG_ID}', NULL),
              ('a0000000-0000-4000-8000-000000000727', '{OPERATOR_ONE}', 'governance_roles', 'approve', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    docker_sql(
        container,
        f"""INSERT INTO public.governance_circle (
                id, circle_key, name, purpose, scope_type, scope_id, status, created_by_party_id
            ) VALUES (
                '{DEFINITION_CIRCLE}', 'lifecycle-{DEFINITION_CIRCLE}', 'Lifecycle test circle',
                'Test separate human lifecycle actions.', 'location', '{LOCATION_ID}', 'draft', '{PARTY_ONE}'
            );
            INSERT INTO public.governance_role (
                id, circle_id, role_key, name, purpose, status, created_by_party_id
            ) VALUES (
                '{DEFINITION_ROLE}', '{DEFINITION_CIRCLE}', 'lifecycle-role', 'Lifecycle test role',
                'Test definition transitions independently from assignments.', 'draft', '{PARTY_ONE}'
            );""",
    )

    def definition_transition(operator_id, entity_type, entity_id, action, request_id, reason):
        return runtime_call(
            container,
            operator_id,
            f"""SELECT event_id::text || '|' || entity_type || '|' || entity_id::text || '|' ||
                       action || '|' || prior_status || '|' || resulting_status || '|' || actor_party_id::text
                  FROM kokonut_security.transition_governance_definition(
                    '{LOCATION_ID}', '{entity_type}', '{entity_id}', '{request_id}',
                    '{action}', '{reason.replace("'", "''")}'
                  );""",
        ).stdout.strip().splitlines()[-1]

    circle_submit_id = str(uuid.uuid4())
    circle_submitted = definition_transition(
        OPERATOR_ONE, "circle", DEFINITION_CIRCLE, "submit", circle_submit_id,
        "Circle purpose and location scope are ready for review.",
    )
    if not circle_submitted.endswith(f"|circle|{DEFINITION_CIRCLE}|submit|draft|submitted|{PARTY_ONE}"):
        raise AssertionError(f"circle submission failed: {circle_submitted}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.transition_governance_definition(
            '{LOCATION_ID}', 'circle', '{DEFINITION_CIRCLE}', '{uuid.uuid4()}',
            'activate', 'Creator cannot activate its own circle.');"""),
        "42501",
        "reject creator self-activation of a governance circle",
    )
    circle_activated = definition_transition(
        OPERATOR_TWO, "circle", DEFINITION_CIRCLE, "activate", str(uuid.uuid4()),
        "Independent reviewer approved the circle mandate.",
    )
    if not circle_activated.endswith(f"|circle|{DEFINITION_CIRCLE}|activate|submitted|active|{PARTY_THREE}"):
        raise AssertionError(f"circle activation failed: {circle_activated}")
    role_submit_id = str(uuid.uuid4())
    role_submitted = definition_transition(
        OPERATOR_ONE, "role", DEFINITION_ROLE, "submit", role_submit_id,
        "Role purpose is ready for governance review.",
    )
    if not role_submitted.endswith(f"|role|{DEFINITION_ROLE}|submit|draft|submitted|{PARTY_ONE}"):
        raise AssertionError(f"role submission failed: {role_submitted}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.transition_governance_definition(
            '{LOCATION_ID}', 'role', '{DEFINITION_ROLE}', '{uuid.uuid4()}',
            'approve', 'Creator cannot approve its own role definition.');"""),
        "42501",
        "reject creator self-approval of governance role",
    )
    role_approve_id = str(uuid.uuid4())
    role_approved = definition_transition(
        OPERATOR_TWO, "role", DEFINITION_ROLE, "approve", role_approve_id,
        "Independent reviewer approved the role definition.",
    )
    role_approved_retry = definition_transition(
        OPERATOR_TWO, "role", DEFINITION_ROLE, "approve", role_approve_id,
        "Independent reviewer approved the role definition.",
    )
    if role_approved != role_approved_retry or not role_approved.endswith(
        f"|role|{DEFINITION_ROLE}|approve|submitted|approved|{PARTY_THREE}"
    ):
        raise AssertionError(f"role approval must be independently attributed and replay exactly: {role_approved}")
    for action, prior, resulting in (("activate", "approved", "active"),
                                    ("suspend", "active", "suspended"),
                                    ("retire", "suspended", "retired")):
        transition = definition_transition(
            OPERATOR_TWO, "role", DEFINITION_ROLE, action, str(uuid.uuid4()),
            f"Reviewed the role definition before {action}.",
        )
        if not transition.endswith(
            f"|role|{DEFINITION_ROLE}|{action}|{prior}|{resulting}|{PARTY_THREE}"
        ):
            raise AssertionError(f"role {action} transition failed: {transition}")
    for action, prior, resulting in (("suspend", "active", "suspended"),
                                    ("retire", "suspended", "retired")):
        transition = definition_transition(
            OPERATOR_TWO, "circle", DEFINITION_CIRCLE, action, str(uuid.uuid4()),
            f"Reviewed the circle mandate before {action}.",
        )
        if not transition.endswith(
            f"|circle|{DEFINITION_CIRCLE}|{action}|{prior}|{resulting}|{PARTY_THREE}"
        ):
            raise AssertionError(f"circle {action} transition failed: {transition}")
    collision = runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.transition_governance_definition(
        '{LOCATION_ID}', 'role', '{DEFINITION_ROLE}', '{role_approve_id}',
        'approve', 'Changed reason.');""")
    assert_sqlstate(container, collision, "22023", "reject changed governance request-key replay")
    state_and_count = docker_sql(
        container,
        f"""SELECT circle.status || '|' || (circle.retired_at IS NOT NULL)::text || '|' || role.status || '|' ||
                   (SELECT count(*) FROM public.governance_definition_action_event
                     WHERE entity_id IN ('{DEFINITION_CIRCLE}', '{DEFINITION_ROLE}'))
              FROM public.governance_circle AS circle
              JOIN public.governance_role AS role ON role.circle_id = circle.id
             WHERE circle.id = '{DEFINITION_CIRCLE}';""",
    ).stdout.strip()
    if state_and_count != "retired|true|retired|9":
        raise AssertionError(f"definition lifecycle state and action ledger diverged: {state_and_count}")
    for database_role in ("kokonut_runtime", "kokonut_directus_runtime"):
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; UPDATE public.governance_role SET status = 'active' WHERE id = '{DEFINITION_ROLE}';",
            "42501",
            f"direct {database_role} governance status update",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; INSERT INTO public.governance_role (id, circle_id, role_key, name, status) VALUES ('{uuid.uuid4()}', '{DEFINITION_CIRCLE}', 'bypass-{uuid.uuid4().hex[:8]}', 'Bypass', 'active');",
            "42501",
            f"direct {database_role} active governance role insertion",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; SELECT * FROM public.governance_definition_action_event;",
            "42501",
            f"private definition action history read by {database_role}",
        )
    docker_sql(
        container,
        "GRANT UPDATE (status) ON TABLE public.governance_role TO kokonut_runtime;",
    )
    assert_sqlstate(
        container,
        f"SET ROLE kokonut_runtime; UPDATE public.governance_role SET status = 'active' WHERE id = '{DEFINITION_ROLE}';",
        "P0001",
        "governance lifecycle trigger blocks direct status update despite column grant",
    )
    docker_sql(
        container,
        "REVOKE UPDATE (status) ON TABLE public.governance_role FROM kokonut_runtime;",
    )
    assert_sqlstate(
        container,
        f"UPDATE public.governance_definition_action_event SET reason = 'rewritten' WHERE entity_id = '{DEFINITION_CIRCLE}';",
        "P0001",
        "immutable governance definition action history",
    )
    definition_acl = docker_sql(
        container,
        """SELECT has_table_privilege('kokonut_governance_action_owner', 'public.governance_definition_action_event', 'INSERT')
                  AND NOT has_table_privilege('kokonut_governance_action_owner', 'public.governance_definition_action_event', 'UPDATE')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_definition_action_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_definition_action_event', 'SELECT')
                  AND has_function_privilege('kokonut_runtime',
                    'kokonut_security.transition_governance_definition(uuid,text,uuid,uuid,text,text)', 'EXECUTE')
                  AND NOT has_function_privilege('kokonut_directus_runtime',
                    'kokonut_security.transition_governance_definition(uuid,text,uuid,uuid,text,text)', 'EXECUTE');""",
    ).stdout.strip()
    if definition_acl != "t":
        raise AssertionError(f"governance definition lifecycle ACL contract failed: {definition_acl}")
    checks.append("circle/role definition transitions require exact signed location grants and independent human review, replay idempotently, block assignment conflicts, keep immutable actor history, and deny runtime/Directus direct status changes")

    # Draft-definition writes use a separate create/update grant and immutable
    # mutation history. The fixture's active circle is used for the new role.
    mutation_update_grant = "a0000000-0000-4000-8000-000000000720"
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('{mutation_update_grant}', '{OPERATOR_ONE}', 'governance_roles', 'update', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    circle_request = str(uuid.uuid4())
    circle_key = f"cap024_{uuid.uuid4().hex[:10]}"
    circle_payload = json.dumps({
        "circle_key": circle_key,
        "name": "Kernel Draft Circle",
        "purpose": "Coordinate governed operations for the acceptance fixture.",
        "description": "Synthetic acceptance record.",
        "parent_circle_id": MUTATION_PARENT_CIRCLE,
    }, separators=(",", ":"))
    # Use the known active location circle as parent.
    created_circle = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text || '|' || (result->>'status')
             FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'circle', NULL, '{circle_request}', 'create',
               '{circle_payload}'::jsonb, 'Create a synthetic location circle.');""",
    ).stdout.strip().splitlines()[-1]
    created_circle_id, created_circle_status = created_circle.split("|", 1)
    if created_circle_status != "draft":
        raise AssertionError(f"circle creation did not force draft state: {created_circle}")
    circle_retry = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'circle', NULL, '{circle_request}', 'create',
               '{circle_payload}'::jsonb, 'Create a synthetic location circle.');""",
    ).stdout.strip().splitlines()[-1]
    if circle_retry != created_circle_id:
        raise AssertionError("circle create retry did not return the original definition")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_definition(
            '{LOCATION_ID}', 'circle', NULL, '{circle_request}', 'create',
            '{circle_payload}'::jsonb, 'Changed retry reason.');"""),
        "22023",
        "reject changed governance definition request-key replay",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_definition(
            '{LOCATION_ID}', 'circle', NULL, '{uuid.uuid4()}', 'create',
            '{{"circle_key":"bad-parent","name":"Bad parent","purpose":"Bad scope", "parent_circle_id":"{NETWORK_CIRCLE}"}}'::jsonb,
            'Reject a network parent.');"""),
        "22023",
        "reject a governance circle parent outside the selected location",
    )
    role_request = str(uuid.uuid4())
    role_payload = json.dumps({
        "circle_id": MUTATION_PARENT_CIRCLE,
        "role_key": f"draft_role_{uuid.uuid4().hex[:8]}",
        "name": "Kernel Draft Role",
        "purpose": "Coordinate synthetic governed work.",
    }, separators=(",", ":"))
    created_role_id = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'role', NULL, '{role_request}', 'create',
               '{role_payload}'::jsonb, 'Create a synthetic location role.');""",
    ).stdout.strip().splitlines()[-1]
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_definition(
            '{LOCATION_ID}', 'role', NULL, '{uuid.uuid4()}', 'create',
            '{{"circle_id":"{NETWORK_CIRCLE}","role_key":"bad_scope","name":"Bad scope","purpose":"Network role"}}'::jsonb,
            'Reject a network circle.');"""),
        "P0002",
        "reject a governance role circle outside the selected location",
    )
    circle_update_request = str(uuid.uuid4())
    circle_update_payload = json.dumps({"purpose": "Updated synthetic circle purpose."}, separators=(",", ":"))
    updated_circle_id = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'circle', '{created_circle_id}', '{circle_update_request}', 'update',
               '{circle_update_payload}'::jsonb, 'Clarify the synthetic circle purpose.');""",
    ).stdout.strip().splitlines()[-1]
    circle_update_retry = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'circle', '{created_circle_id}', '{circle_update_request}', 'update',
               '{circle_update_payload}'::jsonb, 'Clarify the synthetic circle purpose.');""",
    ).stdout.strip().splitlines()[-1]
    role_update_request = str(uuid.uuid4())
    role_update_payload = json.dumps({"name": "Updated Kernel Draft Role"}, separators=(",", ":"))
    updated_role_id = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT entity_id::text FROM kokonut_security.mutate_governance_definition(
               '{LOCATION_ID}', 'role', '{created_role_id}', '{role_update_request}', 'update',
               '{role_update_payload}'::jsonb, 'Clarify the synthetic role name.');""",
    ).stdout.strip().splitlines()[-1]
    if updated_circle_id != created_circle_id or circle_update_retry != created_circle_id or updated_role_id != created_role_id:
        raise AssertionError("draft edits changed their governance definition identity")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_definition(
            '{LOCATION_ID}', 'circle', '{MUTATION_PARENT_CIRCLE}', '{uuid.uuid4()}', 'update',
            '{{"name":"Cannot edit active circle"}}'::jsonb, 'Rejected active edit.');"""),
        "55000",
        "reject edit of an active governance circle",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.mutate_governance_definition(
            '{LOCATION_ID}', 'circle', NULL, '{uuid.uuid4()}', 'create',
            '{{"circle_key":"denied","name":"Denied","purpose":"Denied"}}'::jsonb,
            'No create grant.');"""),
        "42501",
        "reject governance definition create without exact create grant",
    )
    ledger_count = docker_sql(
        container,
        f"""SELECT count(*) FROM public.governance_definition_mutation_event
             WHERE entity_id IN ('{created_circle_id}', '{created_role_id}');""",
    ).stdout.strip()
    if ledger_count != "4":
        raise AssertionError(f"expected four immutable create/edit events, got {ledger_count}")
    mutation_acl = docker_sql(
        container,
        """SELECT has_table_privilege('kokonut_governance_action_owner',
                    'public.governance_definition_mutation_event', 'INSERT')
                  AND NOT has_table_privilege('kokonut_governance_action_owner',
                    'public.governance_definition_mutation_event', 'UPDATE')
                  AND NOT has_table_privilege('kokonut_runtime',
                    'public.governance_definition_mutation_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_directus_runtime',
                    'public.governance_definition_mutation_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_circle', 'INSERT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_circle', 'UPDATE')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role', 'INSERT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role', 'UPDATE')
                  AND has_function_privilege('kokonut_runtime',
                    'kokonut_security.mutate_governance_definition(uuid,text,uuid,uuid,text,jsonb,text)', 'EXECUTE')
                  AND NOT has_function_privilege('kokonut_directus_runtime',
                    'kokonut_security.mutate_governance_definition(uuid,text,uuid,uuid,text,jsonb,text)', 'EXECUTE');""",
    ).stdout.strip()
    if mutation_acl != "t":
        raise AssertionError(f"governance definition mutation ACL contract failed: {mutation_acl}")
    for database_role in ("kokonut_runtime", "kokonut_directus_runtime"):
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; UPDATE public.governance_circle SET name = 'bypass' WHERE id = '{created_circle_id}';",
            "42501",
            f"direct {database_role} governance definition update",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; INSERT INTO public.governance_circle (id, circle_key, name, purpose, scope_type, scope_id, status) VALUES ('{uuid.uuid4()}', 'bypass-{uuid.uuid4().hex[:8]}', 'Bypass', 'Bypass', 'location', '{LOCATION_ID}', 'draft');",
            "42501",
            f"direct {database_role} governance definition insert",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; SELECT * FROM public.governance_definition_mutation_event;",
            "42501",
            f"private governance definition mutation history read by {database_role}",
        )
    assert_sqlstate(
        container,
        f"UPDATE public.governance_definition_mutation_event SET reason = 'rewritten' WHERE entity_id = '{created_circle_id}';",
        "P0001",
        "immutable governance definition mutation history",
    )
    checks.append("circle and role creation always yields draft records; exact create/update grants, same-location parents, draft-only edits, idempotent retries, private append-only before/after history, and runtime/Directus direct-write denial are enforced")

    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('a0000000-0000-4000-8000-000000000716', '{OPERATOR_ONE}', 'governance_tactical', 'create', '{LOCATION_ID}', '{ORG_ID}', NULL),
          ('a0000000-0000-4000-8000-000000000718', '{OPERATOR_THREE}', 'governance_tactical', 'create', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    tactical_session_request = str(uuid.uuid4())
    tactical_session_content = json.dumps({
        "circle_id": MUTATION_PARENT_CIRCLE,
        "session_type": "weekly_review",
        "title": "Synthetic weekly review",
        "scheduled_at": "2026-10-21T14:00:00+00:00",
        "facilitator_role_id": ROLE_LOCATION,
        "agenda_scope": "Review synthetic farm operations and actions.",
    }, separators=(",", ":"))

    def create_tactical_session(operator_id, request_id, content, reason):
        content_sql = content.replace("'", "''")
        reason_sql = reason.replace("'", "''")
        return runtime_call(
            container,
            operator_id,
            f"""SELECT event_id::text || '|' || session_id::text || '|' ||
                       actor_party_id::text || '|' || status
                  FROM kokonut_security.create_governance_tactical_session(
                    '{LOCATION_ID}', '{request_id}', '{content_sql}'::jsonb, '{reason_sql}'
                  );""",
        ).stdout.strip().splitlines()[-1]

    created_session = create_tactical_session(
        OPERATOR_ONE,
        tactical_session_request,
        tactical_session_content,
        "Schedule a synthetic tactical review.",
    )
    replayed_session = create_tactical_session(
        OPERATOR_ONE,
        tactical_session_request,
        tactical_session_content,
        "Schedule a synthetic tactical review.",
    )
    if created_session != replayed_session or not created_session.endswith(f"|{PARTY_ONE}|planned"):
        raise AssertionError(f"tactical session retry did not replay exact planned result: {created_session} / {replayed_session}")
    created_event_id, created_session_id, _, _ = created_session.split("|")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{tactical_session_request}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Changed request"}}'::jsonb,
            'Schedule a synthetic tactical review.');"""),
        "22023",
        "reject changed tactical session request-key replay",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Cannot set state","status":"active"}}'::jsonb,
            'Reject caller-selected lifecycle state.');"""),
        "22023",
        "reject caller-selected tactical session lifecycle state",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Cannot set notes","notes":"Private content"}}'::jsonb,
            'Reject caller-provided notes.');"""),
        "22023",
        "reject caller-provided tactical session notes",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Timezone required","scheduled_at":"2026-10-21T14:00:00"}}'::jsonb,
            'Reject ambiguous schedule.');"""),
        "22023",
        "reject timezone-less tactical session schedule",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"No exact grant"}}'::jsonb,
            'Reject missing exact create grant.');"""),
        "42501",
        "reject tactical session creation without the exact create grant",
    )
    wrong_session_context = f"""SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', 'a0000000-0000-4000-8000-000000000299', FALSE);
        SELECT set_config('test.actor_id', '{OPERATOR_ONE}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Wrong signed context"}}'::jsonb,
            'Reject location mismatch.');"""
    assert_sqlstate(
        container,
        wrong_session_context,
        "42501",
        "reject tactical session creation with mismatched signed location context",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{NETWORK_CIRCLE}","session_type":"weekly_review","title":"Wrong scope"}}'::jsonb,
            'Reject a network circle.');"""),
        "P0002",
        "reject tactical session circle outside the location",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Wrong role","facilitator_role_id":"{ROLE_NETWORK}"}}'::jsonb,
            'Reject a role outside the selected circle.');"""),
        "P0002",
        "reject tactical session role outside the selected circle",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.create_governance_tactical_session(
            '{LOCATION_ID}', '{uuid.uuid4()}',
            '{{"circle_id":"{MUTATION_PARENT_CIRCLE}","session_type":"weekly_review","title":"Unbound actor"}}'::jsonb,
            'Reject missing person binding.');"""),
        "42501",
        "reject tactical session creation without an active person binding",
    )
    session_row = docker_sql(
        container,
        f"""SELECT status || '|' || COALESCE(notes, '<null>') || '|' ||
                   COALESCE(outcome_summary, '<null>') || '|' || created_by_party_id::text
              FROM public.governance_tactical_session WHERE id = '{created_session_id}';""",
    ).stdout.strip()
    session_event_count = docker_sql(
        container,
        f"""SELECT count(*) FROM public.governance_tactical_session_creation_event
             WHERE id = '{created_event_id}' AND session_id = '{created_session_id}';""",
    ).stdout.strip()
    if session_row != f"planned|<null>|<null>|{PARTY_ONE}" or session_event_count != "1":
        raise AssertionError(f"tactical session draft/history boundary failed: {session_row}, events={session_event_count}")
    session_acl = docker_sql(
        container,
        """SELECT NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_session', 'INSERT')
                  AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_session', 'INSERT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_session_creation_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_session_creation_event', 'SELECT')
                  AND has_function_privilege('kokonut_runtime',
                    'kokonut_security.create_governance_tactical_session(uuid,uuid,jsonb,text)', 'EXECUTE')
                  AND NOT has_function_privilege('kokonut_directus_runtime',
                    'kokonut_security.create_governance_tactical_session(uuid,uuid,jsonb,text)', 'EXECUTE');""",
    ).stdout.strip()
    if session_acl != "t":
        raise AssertionError(f"tactical session creation ACL contract failed: {session_acl}")
    for database_role in ("kokonut_runtime", "kokonut_directus_runtime"):
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; INSERT INTO public.governance_tactical_session (id,circle_id,session_type,title,status) VALUES ('{uuid.uuid4()}','{MUTATION_PARENT_CIRCLE}','weekly_review','Bypass','planned');",
            "42501",
            f"direct {database_role} tactical session insert",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; SELECT * FROM public.governance_tactical_session_creation_event;",
            "42501",
            f"private tactical session creation history read by {database_role}",
        )
        docker_sql(container, f"GRANT INSERT ON public.governance_tactical_session TO {database_role};")
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; INSERT INTO public.governance_tactical_session (id,circle_id,session_type,title,status) VALUES ('{uuid.uuid4()}','{MUTATION_PARENT_CIRCLE}','weekly_review','Trigger bypass','planned');",
            "42501",
            f"trigger guard for {database_role} tactical session insert",
        )
        docker_sql(container, f"REVOKE INSERT ON public.governance_tactical_session FROM {database_role};")
    assert_sqlstate(
        container,
        f"UPDATE public.governance_tactical_session_creation_event SET reason = 'rewritten' WHERE id = '{created_event_id}';",
        "P0001",
        "immutable tactical session creation history",
    )
    checks.append("tactical session creation requires exact signed location scope and active person binding, accepts only draft-safe fields, validates active same-location circles/roles, replays exact request keys, records immutable actor/reason history, and denies runtime/Directus direct writes")

    item_work = "a0000000-0000-4000-8000-000000000931"
    item_decision = "a0000000-0000-4000-8000-000000000932"
    item_tension = "a0000000-0000-4000-8000-000000000933"
    foreign_location = "a0000000-0000-4000-8000-000000000299"
    foreign_work = "a0000000-0000-4000-8000-000000000934"
    content_update_grant = str(uuid.uuid4())
    content_start_grant = str(uuid.uuid4())
    content_start_retry_grant = str(uuid.uuid4())
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('{content_update_grant}', '{OPERATOR_ONE}', 'governance_tactical', 'update', '{LOCATION_ID}', '{ORG_ID}', NULL),
          ('{content_start_grant}', '{OPERATOR_ONE}', 'governance_tactical', 'start', '{LOCATION_ID}', '{ORG_ID}', NULL);
        INSERT INTO public.location (id, organization_id, status)
            VALUES ('{foreign_location}', NULL, 'active');
        INSERT INTO public.work_item (id, location_id, status) VALUES
            ('{item_work}', '{LOCATION_ID}', 'draft'),
            ('{foreign_work}', '{foreign_location}', 'draft');
        INSERT INTO public.stakeholder_decision (id, scope_type, scope_id, status) VALUES
            ('{item_decision}', 'location', '{LOCATION_ID}', 'draft');
        INSERT INTO public.governance_tension (
            id, tension_key, title, description, tension_type, severity, urgency,
            scope_type, scope_id, circle_id, status
        ) VALUES (
            '{item_tension}', 'synthetic-tactical-link', 'Synthetic tension',
            'Synthetic location-scoped reference.', 'unclear_accountability', 2, 2,
            'location', '{LOCATION_ID}', '{MUTATION_PARENT_CIRCLE}', 'submitted'
        );""",
    )

    def mutate_tactical_content(operator_id, operation, target_id, request_id, content, reason):
        target_sql = "NULL" if target_id is None else f"'{target_id}'"
        content_sql = json.dumps(content, separators=(",", ":")).replace("'", "''")
        reason_sql = reason.replace("'", "''")
        return runtime_call(
            container,
            operator_id,
            f"""SELECT event_id::text || '|' || operation || '|' ||
                       COALESCE(session_id::text, '') || '|' || COALESCE(item_id::text, '')
                  FROM kokonut_security.mutate_governance_tactical_content(
                    '{LOCATION_ID}', '{operation}', {target_sql}, '{request_id}',
                    '{content_sql}'::jsonb, '{reason_sql}'
                  );""",
        ).stdout.strip().splitlines()[-1]

    item_create_request = str(uuid.uuid4())
    item_create_content = {
        "session_id": created_session_id,
        "requested_next_action": "Review irrigation repair quotes.",
        "priority": 4,
        "due_at": "2026-10-25T12:00:00+00:00",
        "tension_id": item_tension,
        "work_item_id": item_work,
        "decision_id": item_decision,
        "owner_role_id": ROLE_LOCATION,
        "owner_party_id": PARTY_ONE,
    }
    item_created = mutate_tactical_content(
        OPERATOR_ONE, "create_item", None, item_create_request, item_create_content,
        "Capture a location-owned follow-up action.",
    )
    item_created_retry = mutate_tactical_content(
        OPERATOR_ONE, "create_item", None, item_create_request, item_create_content,
        "Capture a location-owned follow-up action.",
    )
    if item_created != item_created_retry:
        raise AssertionError("tactical item create did not replay the exact request")
    item_event_id, _, item_session_id, created_item_id = item_created.split("|")
    if item_session_id != created_session_id or not created_item_id:
        raise AssertionError(f"tactical item was not attached to the selected session: {item_created}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'create_item', NULL, '{item_create_request}',
            '{{"session_id":"{created_session_id}","requested_next_action":"changed"}}'::jsonb,
            'Capture a location-owned follow-up action.');"""),
        "22023",
        "reject changed tactical item create request replay",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'create_item', NULL, '{uuid.uuid4()}',
            '{{"session_id":"{created_session_id}","requested_next_action":"Cross-location work","work_item_id":"{foreign_work}"}}'::jsonb,
            'Reject a cross-location work item.');"""),
        "P0002",
        "reject cross-location work-item linkage",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'create_item', NULL, '{uuid.uuid4()}',
            '{{"session_id":"{created_session_id}","requested_next_action":"No create grant"}}'::jsonb,
            'Reject missing create grant.');"""),
        "42501",
        "reject tactical item creation without its exact create grant",
    )
    item_state = docker_sql(
        container,
        f"""SELECT status || '|' || priority::text || '|' || requested_next_action || '|' ||
                   owner_role_id::text || '|' || work_item_id::text || '|' || decision_id::text
              FROM public.governance_tactical_item WHERE id = '{created_item_id}';""",
    ).stdout.strip()
    if item_state != f"open|4|Review irrigation repair quotes.|{ROLE_LOCATION}|{item_work}|{item_decision}":
        raise AssertionError(f"tactical item did not preserve validated content: {item_state}")

    item_update_request = str(uuid.uuid4())
    item_update_content = {"requested_next_action": "Compare verified irrigation repair quotes.", "priority": 5}
    item_updated = mutate_tactical_content(
        OPERATOR_ONE, "update_item", created_item_id, item_update_request,
        item_update_content, "Clarify the action and urgency.",
    )
    item_updated_retry = mutate_tactical_content(
        OPERATOR_ONE, "update_item", created_item_id, item_update_request,
        item_update_content, "Clarify the action and urgency.",
    )
    if item_updated != item_updated_retry:
        raise AssertionError("tactical item update did not replay the exact request")
    item_edit_audit = docker_sql(
        container,
        f"""SELECT operation || '|' || actor_party_id::text || '|' ||
                   (prior_content->>'priority') || '|' || (requested_content->>'priority')
              FROM public.governance_tactical_content_event
             WHERE id = '{item_updated.split('|')[0]}';""",
    ).stdout.strip()
    if item_edit_audit != f"update_item|{PARTY_ONE}|4|5":
        raise AssertionError(f"item edit before/after history is incomplete: {item_edit_audit}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'update_item', '{created_item_id}', '{uuid.uuid4()}',
            '{{"priority":2}}'::jsonb, 'Reject missing update grant.');"""),
        "42501",
        "reject tactical item edit without exact update grant",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{created_item_id}', '{uuid.uuid4()}', 'start',
            'Start the assigned follow-up.');"""),
        "42501",
        "do not allow an update grant to substitute for the separate start grant",
    )
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('{content_start_retry_grant}', '{OPERATOR_ONE}', 'governance_tactical', 'start', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT * FROM kokonut_security.transition_governance_tactical_item(
            '{LOCATION_ID}', '{created_item_id}', '{uuid.uuid4()}', 'start',
            'Start the assigned follow-up.');""",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'update_item', '{created_item_id}', '{uuid.uuid4()}',
            '{{"priority":2}}'::jsonb, 'Reject edit after work started.');"""),
        "55000",
        "reject tactical item content edits after lifecycle start",
    )

    session_update_request = str(uuid.uuid4())
    session_update_content = {"title": "Updated weekly review", "scheduled_at": "2026-10-22T10:00:00+00:00"}
    session_updated = mutate_tactical_content(
        OPERATOR_ONE, "update_session", created_session_id, session_update_request,
        session_update_content, "Move the planned review and clarify its title.",
    )
    session_updated_retry = mutate_tactical_content(
        OPERATOR_ONE, "update_session", created_session_id, session_update_request,
        session_update_content, "Move the planned review and clarify its title.",
    )
    if session_updated != session_updated_retry:
        raise AssertionError("planned tactical session edit did not replay the exact request")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.mutate_governance_tactical_content(
            '{LOCATION_ID}', 'update_session', '{created_session_id}', '{uuid.uuid4()}',
            '{{"status":"completed","outcome_summary":"Not approved through content update"}}'::jsonb,
            'Reject lifecycle bypass.');"""),
        "22023",
        "reject caller-selected session lifecycle or outcome fields",
    )
    session_state = docker_sql(
        container,
        f"""SELECT status || '|' || title || '|' || created_by_party_id::text
              FROM public.governance_tactical_session WHERE id = '{created_session_id}';""",
    ).stdout.strip()
    if session_state != f"planned|Updated weekly review|{PARTY_ONE}":
        raise AssertionError(f"session edit changed governed state or creator: {session_state}")
    content_acl = docker_sql(
        container,
        """SELECT has_table_privilege('kokonut_governance_action_owner', 'public.governance_tactical_content_event', 'INSERT')
                  AND NOT has_table_privilege('kokonut_governance_action_owner', 'public.governance_tactical_content_event', 'UPDATE')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_content_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_content_event', 'SELECT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_item', 'INSERT')
                  AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_tactical_item', 'INSERT')
                  AND NOT has_table_privilege('kokonut_runtime', 'public.governance_tactical_session', 'UPDATE')
                  AND has_column_privilege('kokonut_governance_action_owner',
                    'public.work_item', 'id', 'UPDATE')
                  AND NOT has_column_privilege('kokonut_governance_action_owner',
                    'public.work_item', 'status', 'UPDATE')
                  AND has_function_privilege('kokonut_runtime',
                    'kokonut_security.mutate_governance_tactical_content(uuid,text,uuid,uuid,jsonb,text)', 'EXECUTE')
                  AND NOT has_function_privilege('kokonut_directus_runtime',
                    'kokonut_security.mutate_governance_tactical_content(uuid,text,uuid,uuid,jsonb,text)', 'EXECUTE');""",
    ).stdout.strip()
    if content_acl != "t":
        raise AssertionError(f"tactical content ACL contract failed: {content_acl}")
    for database_role in ("kokonut_runtime", "kokonut_directus_runtime"):
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; UPDATE public.governance_tactical_session SET title = 'bypass' WHERE id = '{created_session_id}';",
            "42501",
            f"direct {database_role} tactical session update",
        )
        assert_sqlstate(
            container,
            f"SET ROLE {database_role}; SELECT * FROM public.governance_tactical_content_event;",
            "42501",
            f"private tactical content history read by {database_role}",
        )
    assert_sqlstate(
        container,
        f"UPDATE public.governance_tactical_content_event SET reason = 'rewritten' WHERE id = '{item_event_id}';",
        "P0001",
        "immutable tactical content history",
    )
    checks.append("tactical item creation and open-item/planned-session edits require signed exact grants, validate linked records in-location, replay only identical requests, preserve lifecycle/approval fields, and append private immutable before/after history")

    first_page = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT assignment_id::text || '|' || created_at::text
             FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 1, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    first_assignment_id, first_created_at = first_page.split("|", 1)
    next_page = runtime_call(
        container,
        OPERATOR_ONE,
        f"""SELECT assignment_id::text
             FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 2, '{first_created_at}', '{first_assignment_id}'
             );""",
    ).stdout.strip().splitlines()[-1]
    if first_assignment_id != second_assignment_id or next_page != assignment_id:
        raise AssertionError(f"proposal readback keyset order is unstable: {first_page}, {next_page}")
    other_operator_rows = runtime_call(
        container,
        OPERATOR_TWO,
        f"""SELECT count(*) FROM kokonut_security.list_my_governance_role_assignment_proposals(
                 '{LOCATION_ID}', 10, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    if other_operator_rows != "0":
        raise AssertionError(f"readback exposed another operator's proposal: {other_operator_rows}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, NULL);"""),
        "42501",
        "reject operator without exact governance role read grant",
    )
    wrong_location_context = f"""SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', 'a0000000-0000-4000-8000-000000000299', FALSE);
        SELECT set_config('test.actor_id', '{OPERATOR_ONE}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, NULL);"""
    assert_sqlstate(
        container,
        wrong_location_context,
        "42501",
        "reject readback with mismatched signed location context",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.list_my_governance_role_assignment_proposals(
            '{LOCATION_ID}', 10, NULL, '{assignment_id}');"""),
        "22023",
        "reject incomplete keyset cursor",
    )
    result_shape = docker_sql(
        container,
        """SELECT pg_get_function_result(
              'kokonut_security.list_my_governance_role_assignment_proposals(uuid,integer,timestamptz,uuid)'::regprocedure
            );""",
    ).stdout
    if "party_id" in result_shape or "mandate" in result_shape:
        raise AssertionError(f"readback projection contains nominee or mandate fields: {result_shape}")
    checks.append("read-only readback pages only the signed operator's nominations, rejects missing or mismatched scope, and omits nominee identity and mandate")

    review_queue = runtime_call(
        container,
        OPERATOR_TWO,
        f"""SELECT count(*)::text || '|' || string_agg(
                   nominee_name || ':' || submitted_by_name || ':' || assignment_type || ':' || role_key,
                   ',' ORDER BY created_at DESC, assignment_id DESC
               )
             FROM kokonut_security.list_governance_role_assignment_review_queue(
                 '{LOCATION_ID}', 10, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    if review_queue != "2|Person Two:Person One:primary:field_coordinator,Person Two:Person One:primary:field_coordinator":
        raise AssertionError(f"review queue did not return the pending proposals with review detail: {review_queue}")
    review_first_page = runtime_call(
        container,
        OPERATOR_TWO,
        f"""SELECT assignment_id::text || '|' || created_at::text
             FROM kokonut_security.list_governance_role_assignment_review_queue(
                 '{LOCATION_ID}', 1, NULL, NULL
             );""",
    ).stdout.strip().splitlines()[-1]
    review_first_id, review_first_created_at = review_first_page.split("|", 1)
    review_next_page = runtime_call(
        container,
        OPERATOR_TWO,
        f"""SELECT assignment_id::text
             FROM kokonut_security.list_governance_role_assignment_review_queue(
                 '{LOCATION_ID}', 1, '{review_first_created_at}', '{review_first_id}'
             );""",
    ).stdout.strip().splitlines()[-1]
    if {review_first_id, review_next_page} != {assignment_id, second_assignment_id}:
        raise AssertionError(f"review queue keyset paging skipped or repeated a proposal: {review_first_page}, {review_next_page}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.list_governance_role_assignment_review_queue(
            '{LOCATION_ID}', 10, NULL, NULL);"""),
        "42501",
        "reject queue access without exact review grant",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.list_governance_role_assignment_review_queue(
            '{LOCATION_ID}', 10, NULL, '{assignment_id}');"""),
        "22023",
        "reject incomplete review queue cursor",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.list_governance_role_assignment_review_queue(
            '{LOCATION_ID}', 102, NULL, NULL);"""),
        "22023",
        "reject oversized review queue page",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.decide_governance_role_assignment(
            '{LOCATION_ID}', '{ROLE_LOCATION}', '{assignment_id}', '{uuid.uuid4()}',
            'approve', 'Self approval must be denied');"""),
        "42501",
        "reject self-approval even when proposer has an approve grant",
    )
    checks.append("review queue reveals nominee, submitter, role, and mandate only to a separately granted reviewer; keyset paging is bounded, and proposers cannot decide their own proposal")

    def decide(operator_id: str, target_assignment: str, requested_decision: str, decision_request_id: str, reason: str):
        escaped_reason = reason.replace("'", "''")
        sql = f"""SELECT decision_id::text || '|' || assignment_id::text || '|' || decision || '|' ||
                          assignment_status || '|' || reviewer_party_id::text
                   FROM kokonut_security.decide_governance_role_assignment(
                       '{LOCATION_ID}', '{ROLE_LOCATION}', '{target_assignment}',
                       '{decision_request_id}', '{requested_decision}', '{escaped_reason}'
                   );"""
        return runtime_call(container, operator_id, sql).stdout.strip().splitlines()[-1]

    approve_request_id = str(uuid.uuid4())
    approved = decide(OPERATOR_TWO, assignment_id, "approve", approve_request_id, "Reviewed against the active location role")
    approved_retry = decide(OPERATOR_TWO, assignment_id, "approve", approve_request_id, "Reviewed against the active location role")
    if approved != approved_retry or not approved.endswith(f"|approve|active|{PARTY_THREE}"):
        raise AssertionError(f"approval must commit and replay exactly: {approved} / {approved_retry}")
    approved_state = docker_sql(
        container,
        f"""SELECT status || '|' || approved_by_party_id::text || '|' ||
                          (effective_from IS NOT NULL)::text
             FROM public.governance_role_assignment WHERE id = '{assignment_id}';""",
    ).stdout.strip()
    if approved_state != f"active|{PARTY_THREE}|true":
        raise AssertionError(f"approval lifecycle transition was not atomic: {approved_state}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.decide_governance_role_assignment(
            '{LOCATION_ID}', '{ROLE_LOCATION}', '{assignment_id}', '{uuid.uuid4()}',
            'reject', 'Already approved');"""),
        "55000",
        "reject a second decision for an already approved proposal",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.decide_governance_role_assignment(
            '{LOCATION_ID}', '{ROLE_LOCATION}', '{assignment_id}', '{approve_request_id}',
            'approve', 'Different reason');"""),
        "22023",
        "reject idempotency key reuse with changed content",
    )

    reject_request_id = str(uuid.uuid4())
    rejected = decide(OPERATOR_TWO, second_assignment_id, "reject", reject_request_id, "Mandate requires clarification")
    rejected_retry = decide(OPERATOR_TWO, second_assignment_id, "reject", reject_request_id, "Mandate requires clarification")
    if rejected != rejected_retry or not rejected.endswith(f"|reject|rejected|{PARTY_THREE}"):
        raise AssertionError(f"rejection must commit and replay exactly: {rejected} / {rejected_retry}")
    rejected_state = docker_sql(
        container,
        f"""SELECT status || '|' || COALESCE(approved_by_party_id::text, 'null') || '|' ||
                          COALESCE(effective_from::text, 'null')
             FROM public.governance_role_assignment WHERE id = '{second_assignment_id}';""",
    ).stdout.strip()
    if rejected_state != "rejected|null|null":
        raise AssertionError(f"rejection must not populate approval fields: {rejected_state}")
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.decide_governance_role_assignment(
            '{LOCATION_ID}', '{ROLE_LOCATION}', '{second_assignment_id}', '{uuid.uuid4()}',
            'reject', 'No reject grant');"""),
        "42501",
        "reject decision without exact role action grant",
    )
    checks.append("independent approval and rejection atomically update lifecycle state, require exact action grants and reason, reject repeat decisions, and preserve exact idempotent retries")

    decision_privileges = docker_sql(
        container,
        """SELECT has_table_privilege('kokonut_governance_action_owner', 'public.governance_role_assignment_decision', 'SELECT')
              AND has_table_privilege('kokonut_governance_action_owner', 'public.governance_role_assignment_decision', 'INSERT')
              AND NOT has_table_privilege('kokonut_governance_action_owner', 'public.governance_role_assignment_decision', 'UPDATE')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_decision', 'SELECT')
              AND NOT has_table_privilege('kokonut_runtime', 'public.governance_role_assignment_decision', 'INSERT')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment_decision', 'SELECT')
              AND NOT has_table_privilege('kokonut_directus_runtime', 'public.governance_role_assignment_decision', 'INSERT')
              AND has_function_privilege('kokonut_runtime',
                'kokonut_security.list_governance_role_assignment_review_queue(uuid,integer,timestamp with time zone,uuid)', 'EXECUTE')
              AND has_function_privilege('kokonut_runtime',
                'kokonut_security.decide_governance_role_assignment(uuid,uuid,uuid,uuid,text,text)', 'EXECUTE')
              AND NOT has_function_privilege('kokonut_directus_runtime',
                'kokonut_security.decide_governance_role_assignment(uuid,uuid,uuid,uuid,text,text)', 'EXECUTE');""",
    ).stdout.strip()
    if decision_privileges != "t":
        raise AssertionError(f"governance decision ACL contract failed: {decision_privileges}")
    for role_name in ("kokonut_runtime", "kokonut_directus_runtime"):
        for command in ("SELECT * FROM public.governance_role_assignment_decision;",
                        "INSERT INTO public.governance_role_assignment_decision(operator_id,decision_request_id,location_id,assignment_id,role_id,submitted_by_party_id,reviewer_party_id,decision,reason,result_status) VALUES ('%s','%s','%s','%s','%s','%s','%s','reject','x','rejected');" % (OPERATOR_TWO, uuid.uuid4(), LOCATION_ID, second_assignment_id, ROLE_LOCATION, PARTY_ONE, PARTY_THREE),
                        "UPDATE public.governance_role_assignment_decision SET reason = 'changed' WHERE assignment_id = '%s';" % second_assignment_id,
                        "DELETE FROM public.governance_role_assignment_decision WHERE assignment_id = '%s';" % second_assignment_id):
            assert_sqlstate(container, f"SET ROLE {role_name}; {command}", "42501", f"{role_name} direct decision ledger access")
    assert_sqlstate(
        container,
        f"UPDATE public.governance_role_assignment_decision SET reason = 'rewritten' WHERE assignment_id = '{assignment_id}';",
        "P0001",
        "append-only decision history",
    )
    checks.append("decision history is append-only and private to the bounded function owner; runtime and Directus cannot read or mutate it directly")

    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{request_id}', '{ROLE_LOCATION}', '{PARTY_ONE}', 'primary', NULL);"""),
        "22023",
        "reject reuse of a request ID with different content",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_TWO, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{uuid.uuid4()}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL);"""),
        "42501",
        "reject operator without exact governance role create grant",
    )
    docker_sql(
        container,
        f"""INSERT INTO public.operator_scope_grant VALUES
          ('a0000000-0000-4000-8000-000000000705', '{OPERATOR_THREE}', 'governance_roles', 'create', '{LOCATION_ID}', '{ORG_ID}', NULL);""",
    )
    assert_sqlstate(
        container,
        runtime_sql(OPERATOR_THREE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
            '{LOCATION_ID}', '{uuid.uuid4()}', '{ROLE_LOCATION}', '{PARTY_TWO}', 'primary', NULL);"""),
        "42501",
        "reject unbound operator",
    )
    checks.append("signed tenant context, exact location grant, active party binding, and request-content identity are enforced")

    for role_id, party_id, assignment_type, mandate, sqlstate, label in (
        (ROLE_NETWORK, PARTY_TWO, "primary", None, "22023", "network role outside requested location"),
        (ROLE_LOCATION, PARTY_RETIRED, "primary", None, "22023", "inactive nominee party"),
        (ROLE_LOCATION, PARTY_TWO, "delegate", None, "22023", "delegate without mandate"),
    ):
        mandate_sql = "NULL" if mandate is None else "'" + mandate.replace("'", "''") + "'"
        assert_sqlstate(
            container,
            runtime_sql(OPERATOR_ONE, f"""SELECT * FROM kokonut_security.propose_governance_role_assignment(
                '{LOCATION_ID}', '{uuid.uuid4()}', '{role_id}', '{party_id}', '{assignment_type}', {mandate_sql});"""),
            sqlstate,
            label,
        )
    checks.append("role location, nominee active state, and delegate mandate are validated before writing")

    for sql, label in (
        ("INSERT INTO public.governance_role_assignment(role_id, party_id, assignment_type) VALUES ('%s', '%s', 'primary');" % (ROLE_LOCATION, PARTY_TWO), "direct runtime insert"),
        ("UPDATE public.governance_role_assignment SET status = 'active' WHERE id = '%s';" % assignment_id, "direct runtime activation"),
        ("DELETE FROM public.governance_role_assignment WHERE id = '%s';" % assignment_id, "direct runtime delete"),
        ("SELECT * FROM public.governance_role_assignment_request;", "request ledger read"),
        ("INSERT INTO public.governance_role_assignment(role_id, party_id, assignment_type) VALUES ('%s', '%s', 'primary');" % (ROLE_LOCATION, PARTY_TWO), "direct Directus insert"),
        ("UPDATE public.governance_role_assignment SET status = 'active' WHERE id = '%s';" % assignment_id, "direct Directus activation"),
        ("DELETE FROM public.governance_role_assignment WHERE id = '%s';" % assignment_id, "direct Directus delete"),
        ("SELECT * FROM public.governance_role_assignment_request;", "Directus request ledger read"),
    ):
        database_role = "kokonut_directus_runtime" if label.startswith("direct Directus") or label.startswith("Directus") else "kokonut_runtime"
        assert_sqlstate(container, f"SET ROLE {database_role}; {sql}", "42501", label)
    assert_sqlstate(
        container,
        f"UPDATE public.governance_role_assignment_request SET mandate = 'rewritten' WHERE operator_id = '{OPERATOR_ONE}' AND request_id = '{request_id}';",
        "P0001",
        "immutable request history",
    )
    checks.append("runtime cannot bypass the bounded write function, activate/delete assignments, inspect the private request ledger, or rewrite request history")
    return checks


def runtime_sql(operator_id: str, sql: str) -> str:
    return f"""SET ROLE kokonut_runtime;
        SELECT set_config('test.tenant_id', '{ORG_ID}', FALSE);
        SELECT set_config('test.location_id', '{LOCATION_ID}', FALSE);
        SELECT set_config('test.actor_id', '{operator_id}', FALSE);
        SELECT set_config('test.actor_type', 'operator', FALSE);
        {sql}"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-governance-proposals-{uuid.uuid4().hex[:10]}"
    password = secrets.token_urlsafe(24)
    started = time.monotonic()
    run(["docker", "run", "-d", "--rm", "--name", container, "-e", f"POSTGRES_PASSWORD={password}", "-p", "127.0.0.1::5432", "postgres:16-alpine"])
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if run(["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"], check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        checks = run_acceptance(container)
        evidence = {
            "title": "Migrations 437-445 governance role assignment, definition lifecycle, and tactical content acceptance",
            "status": "passed",
            "checks": checks,
            "isolation": "Only a temporary PostgreSQL 16 container was used; candidate and legacy databases were not accessed.",
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
    finally:
        run(["docker", "rm", "-f", container], check=False)


if __name__ == "__main__":
    main()
