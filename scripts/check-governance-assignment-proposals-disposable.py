#!/usr/bin/env python3
"""Exercise governance role nomination, review, and tactical actions on disposable PostgreSQL 16."""

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
)
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-18-recovery/governance-lifecycle-actions-disposable.json"

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


def run(command: list[str], *, input_text: str | None = None, check: bool = True):
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
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
    checks.append("migrations 438–441 apply and replay transactionally after migration 437")

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
              AND NOT has_column_privilege('kokonut_governance_action_owner', 'public.governance_tactical_item', 'requested_next_action', 'UPDATE')
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
            "title": "Migrations 437-441 governance role assignment and tactical action acceptance",
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
