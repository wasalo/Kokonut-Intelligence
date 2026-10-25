#!/usr/bin/env python3
"""Apply/replay pollinator review migrations and verify isolation in disposable PostgreSQL 16."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIGRATIONS = tuple(
    ROOT / "schemas/postgres" / name
    for name in (
        "155_pollinator_health.sql",
        "602_pollinator_health_kernel_alignment.sql",
        "619_location_pollinator_observation_capture.sql",
        "620_location_pesticide_impact_capture.sql",
        "621_location_pollinator_habitat_capture.sql",
        "622_location_pollinator_hive_capture.sql",
        "623_location_pollinator_hive_inspection_capture.sql",
        "624_location_pollinator_habitat_lifecycle.sql",
        "625_location_pollinator_hive_lifecycle.sql",
        "626_location_pollinator_independent_review.sql",
        "627_location_pollinator_hive_inspection_review.sql",
    )
)
PLATFORM = os.environ.get("POLLINATOR_REVIEW_TEST_PLATFORM")
OUTPUT_SUFFIX = "-arm64" if PLATFORM == "linux/arm64" else ""
OUTPUT = ROOT / (
    "docs/refactor/builds/2026-10-25-recovery/"
    f"cap-006-pollinator-inspection-review{OUTPUT_SUFFIX}-disposable.json"
)
IMAGE = os.environ.get("POLLINATOR_REVIEW_TEST_IMAGE", "postgres:16")


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]} …\n{details}")
    return result.stdout.strip()


def expect_error(connection, statement: str, params: tuple, expected: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE kokonut_runtime")
            cursor.execute(statement, params)
        connection.commit()
    except psycopg2.Error as exc:
        if exc.pgcode != expected:
            connection.rollback()
            raise AssertionError(f"expected SQLSTATE {expected}, got {exc.pgcode}") from exc
        connection.rollback()
        return
    raise AssertionError(f"expected SQLSTATE {expected}, statement succeeded")


def set_context(cursor, operator_id: str | None, location_id: str | None, actor_type="operator") -> None:
    cursor.execute("SELECT set_config('kokonut.actor_id', %s, true)", (operator_id or "",))
    cursor.execute("SELECT set_config('kokonut.location_id', %s, true)", (location_id or "",))
    cursor.execute("SELECT set_config('kokonut.actor_type', %s, true)", (actor_type or "",))


def call_queue(connection, operator_id: str, location_id: str, limit=25, offset=0):
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE kokonut_runtime")
        set_context(cursor, operator_id, location_id)
        cursor.execute(
            "SELECT kokonut_security.list_location_pollinator_review_queue(%s, %s, %s)",
            (location_id, limit, offset),
        )
        value = cursor.fetchone()[0]
    connection.commit()
    return value


def call_review(
    connection, operator_id: str, location_id: str, record_type: str, record_id: str,
    request_id: str, expected_updated_at, decision="reviewed", reason="Independent review completed",
):
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE kokonut_runtime")
        set_context(cursor, operator_id, location_id)
        if record_type == "hive_inspection":
            cursor.execute(
                "SELECT kokonut_security.review_location_pollinator_hive_inspection("
                "%s, %s, %s, %s, %s, %s)",
                (location_id, record_id, request_id, expected_updated_at, decision, reason),
            )
        else:
            cursor.execute(
                "SELECT kokonut_security.review_location_pollinator_record("
                "%s, %s, %s, %s, %s, %s, %s)",
                (location_id, record_type, record_id, request_id, expected_updated_at, decision, reason),
            )
        value = cursor.fetchone()[0]
    connection.commit()
    return value


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-pollinator-review-{os.getpid()}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(24)
    started = False
    connection = None
    checks: list[str] = []
    reviewer_id, reporter_id = str(uuid.uuid4()), str(uuid.uuid4())
    location_id, other_location_id = str(uuid.uuid4()), str(uuid.uuid4())
    observation_id, pesticide_id, own_observation_id, foreign_observation_id = (
        str(uuid.uuid4()) for _ in range(4)
    )
    unknown_observation_id = str(uuid.uuid4())
    hive_record_id, own_hive_record_id, unknown_hive_record_id, foreign_hive_record_id = (
        str(uuid.uuid4()) for _ in range(4)
    )
    inspection_id, own_inspection_id, unknown_inspection_id, foreign_inspection_id = (
        str(uuid.uuid4()) for _ in range(4)
    )
    observation_request_id, pesticide_request_id = str(uuid.uuid4()), str(uuid.uuid4())
    inspection_request_id = str(uuid.uuid4())
    try:
        command = [docker, "run"]
        if PLATFORM:
            command.extend(["--platform", PLATFORM])
        command.extend([
            "--detach", "--rm", "--name", container,
            "--env", f"POSTGRES_PASSWORD={password}",
            "--publish", "127.0.0.1::5432", IMAGE,
        ])
        run(command)
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [docker, "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
                text=True, capture_output=True, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        architecture = run([docker, "exec", container, "uname", "-m"])
        mapping = json.loads(run([docker, "inspect", "--format", "{{json .NetworkSettings.Ports}}", container]))
        port = int(mapping["5432/tcp"][0]["HostPort"])
        connection = psycopg2.connect(
            host="127.0.0.1", port=port, dbname="postgres", user="postgres",
            password=password, connect_timeout=5,
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION pgcrypto")
            cursor.execute("CREATE ROLE kokonut_runtime NOLOGIN")
            cursor.execute("CREATE ROLE kokonut_directus_runtime NOLOGIN")
            cursor.execute("CREATE SCHEMA kokonut_security")
            cursor.execute("CREATE TABLE location (id UUID PRIMARY KEY, name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE operator_identity (id UUID PRIMARY KEY)")
            cursor.execute("CREATE TABLE farm (id UUID PRIMARY KEY, location_id UUID NOT NULL REFERENCES location(id), name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE plot (id UUID PRIMARY KEY, farm_id UUID NOT NULL REFERENCES farm(id), name TEXT NOT NULL)")
            cursor.execute("CREATE TABLE operator_scope_grant (operator_id UUID, location_id UUID, resource TEXT, action TEXT, revoked_at TIMESTAMPTZ)")
            cursor.execute(
                """CREATE FUNCTION kokonut_security.current_tenant_context()
                   RETURNS TABLE(actor_id UUID, location_id UUID, actor_type TEXT)
                   LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
                   AS $$ SELECT nullif(current_setting('kokonut.actor_id', true), '')::uuid,
                                    nullif(current_setting('kokonut.location_id', true), '')::uuid,
                                    nullif(current_setting('kokonut.actor_type', true), '') $$"""
            )
            cursor.execute(
                """CREATE FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
                   RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY DEFINER SET search_path = pg_catalog
                   AS $$ SELECT EXISTS (
                       SELECT 1 FROM public.operator_scope_grant AS grant_row
                        WHERE grant_row.operator_id = $1 AND grant_row.resource = $2
                          AND grant_row.action = $3 AND grant_row.location_id = $4
                          AND grant_row.revoked_at IS NULL
                   ) $$"""
            )
            cursor.execute("GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, kokonut_directus_runtime")
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON location, farm, plot TO kokonut_runtime, kokonut_directus_runtime")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text())
            cursor.execute(
                "INSERT INTO location (id, name) VALUES (%s, 'Review fixture'), (%s, 'Foreign fixture')",
                (location_id, other_location_id),
            )
            cursor.execute(
                "INSERT INTO operator_identity (id) VALUES (%s), (%s)", (reviewer_id, reporter_id)
            )
            cursor.execute(
                "INSERT INTO operator_scope_grant (operator_id, location_id, resource, action) "
                "VALUES (%s, %s, 'pollinator_health', 'review')",
                (reviewer_id, location_id),
            )
            cursor.execute(
                "INSERT INTO hive_record (id, location_id, hive_id, status, created_by_operator_id) "
                "VALUES (%s, %s, 'Hive-7', 'active', %s), "
                "(%s, %s, 'Hive-Own', 'active', %s), "
                "(%s, %s, 'Hive-Legacy', 'active', NULL), "
                "(%s, %s, 'Hive-Foreign', 'active', %s)",
                (hive_record_id, location_id, reporter_id,
                 own_hive_record_id, location_id, reviewer_id,
                 unknown_hive_record_id, location_id,
                 foreign_hive_record_id, other_location_id, reporter_id),
            )
            cursor.execute(
                "INSERT INTO pollinator_hive_inspection "
                "(id, location_id, hive_record_id, inspection_date, colony_strength, "
                "colony_strength_score, queen_status, queen_seen, varroa_count, brood_pattern, "
                "notes, status, created_by_operator_id) "
                "VALUES (%s, %s, %s, CURRENT_DATE, 'moderate', 6, 'present', TRUE, 2, "
                "'even', 'Recorded field inspection', 'recorded', %s), "
                "(%s, %s, %s, CURRENT_DATE, 'weak', 3, 'unknown', FALSE, 5, "
                "'sparse', 'Own inspection', 'recorded', %s), "
                "(%s, %s, %s, CURRENT_DATE, 'moderate', 5, 'present', TRUE, 1, "
                "'even', 'Legacy submitter unknown', 'recorded', NULL), "
                "(%s, %s, %s, CURRENT_DATE, 'strong', 8, 'present', TRUE, 0, "
                "'even', 'Foreign inspection', 'recorded', %s)",
                (inspection_id, location_id, hive_record_id, reporter_id,
                 own_inspection_id, location_id, own_hive_record_id, reviewer_id,
                 unknown_inspection_id, location_id, unknown_hive_record_id,
                 foreign_inspection_id, other_location_id, foreign_hive_record_id, reporter_id),
            )
            cursor.execute(
                "INSERT INTO pollinator_observation "
                "(id, location_id, observation_date, pollinator_type, count, observation_method, "
                "duration_minutes, notes, status, created_by_operator_id) "
                "VALUES (%s, %s, CURRENT_DATE, 'wild_bee', 12, 'transect', 15, 'Reviewer evidence', 'recorded', %s), "
                "(%s, %s, CURRENT_DATE, 'butterfly', 4, 'visual_count', 8, 'Own record', 'recorded', %s), "
                "(%s, %s, CURRENT_DATE, 'bird', 2, 'visual_count', 4, 'Foreign location', 'recorded', %s), "
                "(%s, %s, CURRENT_DATE, 'wild_bee', 3, 'transect', 5, 'Legacy submitter unknown', 'recorded', NULL)",
                (observation_id, location_id, reporter_id,
                 own_observation_id, location_id, reviewer_id,
                 foreign_observation_id, other_location_id, reporter_id,
                 unknown_observation_id, location_id),
            )
            cursor.execute(
                "INSERT INTO pesticide_impact_log "
                "(id, location_id, application_date, product_name, active_ingredient, toxicity_class, "
                "pollinator_mortality_observed, notes, status, created_by_operator_id) "
                "VALUES (%s, %s, CURRENT_DATE, 'Synthetic product', 'Synthetic ingredient', 'moderate', "
                "FALSE, 'Completed application report', 'recorded', %s)",
                (pesticide_id, location_id, reporter_id),
            )
        checks.append("migrations 155/602/619–627 apply")

        connection.autocommit = False
        for migration in (MIGRATIONS[-1], MIGRATIONS[-1]):
            with connection.cursor() as cursor:
                cursor.execute(migration.read_text())
            connection.commit()
        checks.append("migration 627 replays cleanly")

        queue = call_queue(connection, reviewer_id, location_id, limit=1, offset=0)
        if queue["total"] != 3 or len(queue["items"]) != 1 or not queue["has_more"]:
            raise AssertionError(f"unexpected bounded review page: {queue!r}")
        visible_types = {item["record_type"] for item in queue["items"]}
        if not visible_types <= {"observation", "pesticide_impact", "hive_inspection"}:
            raise AssertionError(f"unexpected review record type: {visible_types!r}")
        page_two = call_queue(connection, reviewer_id, location_id, limit=1, offset=1)
        if len(page_two["items"]) != 1 or not page_two["has_more"]:
            raise AssertionError(f"unexpected second review page: {page_two!r}")
        page_three = call_queue(connection, reviewer_id, location_id, limit=1, offset=2)
        if len(page_three["items"]) != 1 or page_three["has_more"]:
            raise AssertionError(f"unexpected third review page: {page_three!r}")
        visible_ids = {
            item["record_id"]
            for item in (*queue["items"], *page_two["items"], *page_three["items"])
        }
        if own_observation_id in visible_ids:
            raise AssertionError("review queue exposed the caller's own record")
        if foreign_observation_id in visible_ids:
            raise AssertionError("review queue exposed a foreign-location record")
        if own_observation_id in visible_ids or unknown_observation_id in visible_ids:
            raise AssertionError("review queue exposed a self-authored or unattributed observation")
        if own_inspection_id in visible_ids or unknown_inspection_id in visible_ids:
            raise AssertionError("review queue exposed a self-authored or unattributed inspection")
        if foreign_inspection_id in visible_ids:
            raise AssertionError("review queue exposed a foreign-location inspection")
        if inspection_id not in visible_ids:
            raise AssertionError("review queue omitted an independently reviewable inspection")
        inspection_item = next(item for item in (*queue["items"], *page_two["items"], *page_three["items"]) if item["record_id"] == inspection_id)
        if inspection_item["details"].get("hive_id") != "Hive-7":
            raise AssertionError(f"inspection queue omitted its same-location hive label: {inspection_item!r}")
        checks.append("signed review queue pages observations, pesticide reports, and hive inspections while excluding self, unattributed, and foreign submissions")

        denied_context = str(uuid.uuid4())
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE kokonut_runtime")
                set_context(cursor, denied_context, location_id)
                cursor.execute(
                    "SELECT kokonut_security.list_location_pollinator_review_queue(%s, 25, 0)",
                    (location_id,),
                )
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"expected missing-grant denial 42501, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("operator without review grant received the review queue")
        checks.append("operator without exact location review grant is denied")

        source_time = {}
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, updated_at FROM pollinator_observation WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pesticide_impact_log WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pollinator_hive_inspection WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pollinator_hive_inspection WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pollinator_hive_inspection WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pollinator_hive_inspection WHERE id = %s "
                "UNION ALL SELECT id, updated_at FROM pollinator_observation WHERE id = %s",
                (observation_id, pesticide_id, inspection_id, own_inspection_id,
                 unknown_inspection_id, foreign_inspection_id, unknown_observation_id),
            )
            source_time = {str(record_id): updated_at for record_id, updated_at in cursor.fetchall()}

        observation_result = call_review(
            connection, reviewer_id, location_id, "observation", observation_id,
            observation_request_id, source_time[observation_id], "reviewed", "Count reconciled with field sheet",
        )
        if observation_result["status"] != "reviewed" or observation_result["replayed"]:
            raise AssertionError(f"unexpected observation review result: {observation_result!r}")
        observation_retry = call_review(
            connection, reviewer_id, location_id, "observation", observation_id,
            observation_request_id, source_time[observation_id], "reviewed", "Count reconciled with field sheet",
        )
        if observation_retry["decision_id"] != observation_result["decision_id"] or not observation_retry["replayed"]:
            raise AssertionError("exact review retry did not return the immutable original decision")
        checks.append("independent observation review updates only recorded status and exact retries replay")

        pesticide_result = call_review(
            connection, reviewer_id, location_id, "pesticide_impact", pesticide_id,
            pesticide_request_id, source_time[pesticide_id], "dismissed", "Duplicate application report",
        )
        if pesticide_result["status"] != "dismissed" or pesticide_result["replayed"]:
            raise AssertionError(f"unexpected pesticide review result: {pesticide_result!r}")
        checks.append("pesticide report can be reviewed or dismissed without an approval/safety state")

        inspection_result = call_review(
            connection, reviewer_id, location_id, "hive_inspection", inspection_id,
            inspection_request_id, source_time[inspection_id], "reviewed",
            "Colony indicators were independently checked against the field log",
        )
        inspection_retry = call_review(
            connection, reviewer_id, location_id, "hive_inspection", inspection_id,
            inspection_request_id, source_time[inspection_id], "reviewed",
            "Colony indicators were independently checked against the field log",
        )
        if inspection_result["status"] != "reviewed" or inspection_result["replayed"]:
            raise AssertionError(f"unexpected inspection review result: {inspection_result!r}")
        if inspection_retry["decision_id"] != inspection_result["decision_id"] or not inspection_retry["replayed"]:
            raise AssertionError("exact inspection review retry did not replay the original decision")
        checks.append("independent hive-inspection review records a reasoned decision and exact retries replay")

        try:
            call_review(
                connection, reviewer_id, location_id, "observation", observation_id,
                observation_request_id, source_time[observation_id], "dismissed", "Changed payload",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "23505":
                raise AssertionError(f"expected request-collision 23505, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("changed-input request ID reuse was accepted")
        try:
            call_review(
                connection, reviewer_id, location_id, "observation", observation_id,
                str(uuid.uuid4()), source_time[observation_id], "reviewed", "Stale decision",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "40001":
                raise AssertionError(f"expected stale-update 40001, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("stale review timestamp was accepted")
        checks.append("request ID input collisions and stale/non-recorded decisions fail closed")

        try:
            call_review(
                connection, reviewer_id, location_id, "observation", own_observation_id,
                str(uuid.uuid4()), source_time[observation_id], "reviewed", "Self review",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"expected self-review denial 42501, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("reviewer was allowed to review their own submission")
        try:
            call_review(
                connection, reviewer_id, location_id, "observation", foreign_observation_id,
                str(uuid.uuid4()), source_time[observation_id], "reviewed", "Cross-location review",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "P0002":
                raise AssertionError(f"expected cross-location denial P0002, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("cross-location review was accepted")
        checks.append("self-review and foreign-location decisions are denied")
        try:
            call_review(
                connection, reviewer_id, location_id, "hive_inspection", unknown_inspection_id,
                str(uuid.uuid4()), source_time[unknown_inspection_id], "reviewed",
                "Unknown legacy submitter",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"expected unknown-submitter denial 42501, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("inspection with unknown submitting operator was reviewable")
        try:
            call_review(
                connection, reviewer_id, location_id, "hive_inspection", own_inspection_id,
                str(uuid.uuid4()), source_time[own_inspection_id], "reviewed", "Self review",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"expected inspection self-review denial 42501, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("reviewer was allowed to review their own hive inspection")
        try:
            call_review(
                connection, reviewer_id, location_id, "hive_inspection", foreign_inspection_id,
                str(uuid.uuid4()), source_time[foreign_inspection_id], "reviewed", "Cross-location review",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "P0002":
                raise AssertionError(f"expected inspection cross-location denial P0002, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("cross-location inspection review was accepted")
        checks.append("unknown-submitter, self-review, and foreign inspection decisions are denied")
        try:
            call_review(
                connection, reviewer_id, location_id, "observation", unknown_observation_id,
                str(uuid.uuid4()), source_time[unknown_observation_id], "reviewed",
                "Legacy submitter unknown",
            )
        except psycopg2.Error as exc:
            if exc.pgcode != "42501":
                raise AssertionError(f"expected unattributed observation denial 42501, got {exc.pgcode}") from exc
            connection.rollback()
        else:
            raise AssertionError("observation with unknown submitting operator was reviewable")
        checks.append("legacy observation with unknown submitter fails closed at immutable ledger guard")

        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute("SELECT status FROM pollinator_observation WHERE id = %s", (observation_id,))
            observation_status = cursor.fetchone()[0]
            cursor.execute("SELECT status FROM pesticide_impact_log WHERE id = %s", (pesticide_id,))
            pesticide_status = cursor.fetchone()[0]
            cursor.execute("SELECT status FROM pollinator_hive_inspection WHERE id = %s", (inspection_id,))
            inspection_status = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*), count(DISTINCT request_id), count(*) FILTER (WHERE status_before = 'recorded') "
                "FROM pollinator_review_decision"
            )
            ledger = cursor.fetchone()
        if observation_status != "reviewed" or pesticide_status != "dismissed" or inspection_status != "reviewed" or ledger != (3, 3, 3):
            raise AssertionError(f"decision, source status, and audit ledger diverged: {observation_status!r}, {pesticide_status!r}, {inspection_status!r}, {ledger!r}")
        checks.append("review decision, source status, and immutable audit event commit atomically")

        connection.commit()
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(MIGRATIONS[-1].read_text())
            cursor.execute("SELECT count(*) FROM pollinator_review_decision")
            retained_decisions = cursor.fetchone()[0]
        connection.autocommit = False
        if retained_decisions != 3:
            raise AssertionError("migration replay changed existing review decision history")
        checks.append("migration replay preserves immutable pollinator review history")

        for role in ("kokonut_runtime", "kokonut_directus_runtime"):
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            connection.commit()
            for statement, arguments in (
                ("UPDATE pollinator_observation SET status = 'dismissed' WHERE id = %s", (observation_id,)),
                ("UPDATE pesticide_impact_log SET status = 'reviewed' WHERE id = %s", (pesticide_id,)),
                ("UPDATE pollinator_hive_inspection SET status = 'dismissed' WHERE id = %s", (inspection_id,)),
                ("SELECT * FROM pollinator_review_decision", ()),
                ("UPDATE pollinator_review_decision SET reason = 'altered'", ()),
                ("DELETE FROM pollinator_review_decision", ()),
            ):
                expect_error(connection, statement, arguments, "42501")
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
            connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin, rolinherit, rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname = 'kokonut_pollinator_review_writer'"
            )
            role_profile = cursor.fetchone()
            cursor.execute(
                "SELECT has_function_privilege('kokonut_runtime', "
                "'kokonut_security.list_location_pollinator_review_queue(uuid,integer,integer)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.list_location_pollinator_review_queue(uuid,integer,integer)', 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.review_location_pollinator_record(uuid,text,uuid,uuid,timestamp with time zone,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.review_location_pollinator_record(uuid,text,uuid,uuid,timestamp with time zone,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_runtime', "
                "'kokonut_security.review_location_pollinator_hive_inspection(uuid,uuid,uuid,timestamp with time zone,text,text)', 'EXECUTE'), "
                "has_function_privilege('kokonut_directus_runtime', "
                "'kokonut_security.review_location_pollinator_hive_inspection(uuid,uuid,uuid,timestamp with time zone,text,text)', 'EXECUTE')"
            )
            function_privileges = cursor.fetchone()
        if role_profile != (False, False, False) or function_privileges != (True, False, True, False, True, False):
            raise AssertionError(f"unexpected review role/function grants: {role_profile!r} / {function_privileges!r}")
        checks.append("runtime reaches bounded review functions; Directus and direct table/ledger access are denied")

        evidence = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container",
            "architecture": architecture,
            "migrations": [path.name for path in MIGRATIONS],
            "migration_627_replayed": True,
            "checks": checks,
            "assertions_passed": len(checks),
            "candidate_database_touched": False,
            "legacy_database_touched": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if connection is not None:
            connection.close()
        if started:
            subprocess.run([docker, "stop", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
