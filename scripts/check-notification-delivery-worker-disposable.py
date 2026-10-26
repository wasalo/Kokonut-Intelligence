#!/usr/bin/env python3
"""Replay migration 647 and exercise isolated notification lease functions."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/647_isolated_notification_delivery_worker.sql"
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-25-recovery/notification-delivery-worker-disposable.json"

FIXTURE = """
CREATE TABLE public.notification_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('webhook','directus','email')),
    destination_key VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','retryable','succeeded','dead_letter','resolved','discarded')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    retry_cycle_attempts INTEGER NOT NULL DEFAULT 0 CHECK (retry_cycle_attempts >= 0),
    replay_count INTEGER NOT NULL DEFAULT 0 CHECK (replay_count >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(150),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error_class VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    UNIQUE (source_event_id, channel, destination_key),
    CHECK ((status='processing' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL
            AND lease_expires_at IS NOT NULL)
        OR (status<>'processing' AND lease_owner IS NULL AND lease_token IS NULL
            AND lease_expires_at IS NULL))
);
CREATE TABLE public.notification_outbox_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id UUID NOT NULL REFERENCES public.notification_outbox(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    lease_owner VARCHAR(150) NOT NULL,
    lease_token UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing','succeeded','failed','lease_lost')),
    error_class VARCHAR(100),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (outbox_id, attempt_number)
);
CREATE SEQUENCE public.synthetic_notification_delivery_sequence;
ALTER TABLE public.notification_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox_attempt FORCE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.notification_outbox, public.notification_outbox_attempt TO PUBLIC;
INSERT INTO public.notification_outbox (id,source_event_id,event_type,channel,destination_key,payload)
VALUES
 ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','sensor_alert','email','primary','{"subject":"ok"}'),
 ('00000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002','sensor_alert','webhook','primary','{"text":"retry"}'),
 ('00000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000003','data_stale','directus','primary','{"message":"max"}'),
 ('00000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000004','data_stale','directus','primary','{"subject":"expired-one"}'),
 ('00000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000005','data_stale','directus','primary','{"subject":"expired-two"}');
UPDATE public.notification_outbox
   SET attempt_count=7, retry_cycle_attempts=7
 WHERE id='00000000-0000-0000-0000-000000000003';
UPDATE public.notification_outbox
   SET status='processing', attempt_count=2, retry_cycle_attempts=2,
       lease_owner='expired-worker', lease_token='20000000-0000-0000-0000-000000000004',
       lease_expires_at=NOW()-INTERVAL '1 minute'
 WHERE id='00000000-0000-0000-0000-000000000004';
UPDATE public.notification_outbox
   SET status='processing', attempt_count=2, retry_cycle_attempts=2,
       lease_owner='expired-worker', lease_token='20000000-0000-0000-0000-000000000005',
       lease_expires_at=NOW()-INTERVAL '1 minute'
 WHERE id='00000000-0000-0000-0000-000000000005';
INSERT INTO public.notification_outbox_attempt (outbox_id,attempt_number,lease_owner,lease_token)
VALUES
 ('00000000-0000-0000-0000-000000000004',2,'expired-worker','20000000-0000-0000-0000-000000000004'),
 ('00000000-0000-0000-0000-000000000005',2,'expired-worker','20000000-0000-0000-0000-000000000005');
"""

LOGIN_PREFLIGHT = """
DO $$
BEGIN
    IF session_user <> 'kokonut_notification_delivery_login' THEN
        RAISE EXCEPTION 'dedicated notification identity was not established';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.claim_notification_outbox_batch('worker',101,300,ARRAY['email']);
        RAISE EXCEPTION 'oversized claim was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM * FROM kokonut_security.claim_notification_outbox_batch('worker',1,29,ARRAY['email']);
        RAISE EXCEPTION 'short lease was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM * FROM kokonut_security.claim_notification_outbox_batch('worker',1,300,ARRAY['pg_read_file']);
        RAISE EXCEPTION 'unapproved channel was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM 1 FROM public.notification_outbox;
        RAISE EXCEPTION 'direct outbox read was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM 1 FROM public.notification_outbox_attempt;
        RAISE EXCEPTION 'direct attempt read was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        INSERT INTO public.notification_outbox (
            source_event_id,event_type,channel,destination_key,payload
        ) VALUES (
            '10000000-0000-0000-0000-000000000099','synthetic','email','primary','{}'
        );
        RAISE EXCEPTION 'direct outbox insert was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        UPDATE public.notification_outbox SET status='succeeded'
         WHERE id='00000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'direct outbox update was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        DELETE FROM public.notification_outbox_attempt;
        RAISE EXCEPTION 'direct attempt deletion was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        PERFORM nextval('public.synthetic_notification_delivery_sequence');
        RAISE EXCEPTION 'direct sequence access was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END;
$$;
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def docker_login_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
         "-F", "\t", "-v", "ON_ERROR_STOP=1", "-U",
         "kokonut_notification_delivery_login", "-d", "postgres"],
        input_text=statement,
    ).strip()


def claim(docker: str, container: str, worker_id: str, channels: str) -> tuple[str, int, str, str] | None:
    output = docker_login_sql(
        docker,
        container,
        "SELECT id, attempt_count, lease_owner, lease_token "
        "FROM kokonut_security.claim_notification_outbox_batch("
        f"'{worker_id}', 1, 300, {channels});",
    )
    if not output:
        return None
    fields = output.split("\t")
    if len(fields) != 4:
        raise RuntimeError(f"unexpected claim result shape: {output!r}")
    return fields[0], int(fields[1]), fields[2], fields[3]


def finish_attempt(
    docker: str,
    container: str,
    row: tuple[str, int, str, str],
    worker_id: str,
    token: str,
    *,
    succeeded: bool,
    error_class: str | None = None,
    retry_delay: int = 0,
) -> str:
    error_sql = "NULL" if error_class is None else f"'{error_class}'"
    return docker_login_sql(
        docker,
        container,
        "SELECT kokonut_security.finish_notification_outbox_attempt("
        f"'{row[0]}'::uuid, '{worker_id}', '{token}'::uuid, {row[1]}, "
        f"{str(succeeded).upper()}, {error_sql}, {retry_delay});",
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "psql", "-X", "-q", "-t", "-A",
             "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
             "-c", "SELECT 1"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default="postgres:16")
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-notification-delivery-{secrets.token_hex(4)}"
    migration = MIGRATION.read_text(encoding="utf-8")
    created = False
    try:
        command = [docker, "run", "-d", "--rm", "--network", "none", "--name", container]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(("-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", args.image))
        run(command)
        created = True
        wait_ready(docker, container)
        architecture = run([docker, "exec", container, "uname", "-m"]).strip()
        expected = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(args.platform)
        if expected is not None and architecture != expected:
            raise RuntimeError("disposable PostgreSQL container architecture mismatch")
        docker_sql(docker, container, FIXTURE)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, migration)
        docker_sql(
            docker,
            container,
            "ALTER ROLE kokonut_notification_delivery_login WITH LOGIN PASSWORD "
            "'synthetic-notification-delivery-password';",
        )
        docker_login_sql(docker, container, LOGIN_PREFLIGHT)

        first = claim(docker, container, "worker-one", "ARRAY['email','webhook']")
        second = claim(docker, container, "worker-two", "ARRAY['email','webhook']")
        if first is None or second is None or first[0] == second[0]:
            raise RuntimeError("bounded claims did not issue distinct leases")
        if first[1] != 1 or second[1] != 1:
            raise RuntimeError("initial claim attempt counters are incorrect")

        if finish_attempt(
            docker, container, first, "wrong-worker", first[3], succeeded=True
        ) != "lease_lost":
            raise RuntimeError("wrong worker completed a lease")
        docker_sql(
            docker,
            container,
            f"DO $$ BEGIN IF (SELECT status FROM public.notification_outbox_attempt "
            f"WHERE outbox_id='{first[0]}' AND attempt_number=1)<>'processing' THEN "
            "RAISE EXCEPTION 'wrong worker modified attempt receipt'; END IF; END $$;",
        )
        if finish_attempt(
            docker,
            container,
            first,
            "worker-one",
            "30000000-0000-0000-0000-000000000099",
            succeeded=True,
        ) != "lease_lost":
            raise RuntimeError("wrong lease token completed a lease")
        if finish_attempt(
            docker, container, first, "worker-one", first[3], succeeded=True
        ) != "succeeded":
            raise RuntimeError("valid success was rejected")
        if finish_attempt(
            docker, container, first, "worker-one", first[3], succeeded=True
        ) != "lease_lost":
            raise RuntimeError("duplicate completion changed a row")

        if finish_attempt(
            docker,
            container,
            second,
            "worker-two",
            second[3],
            succeeded=False,
            error_class="TimeoutError",
        ) != "failed":
            raise RuntimeError("retryable failure was rejected")
        retry = claim(docker, container, "worker-three", "ARRAY['email','webhook']")
        if retry is None or retry[0] != second[0] or retry[1] != 2:
            raise RuntimeError(
                f"retry did not preserve cumulative attempt numbering: "
                f"expected {second!r}, received {retry!r}"
            )
        if finish_attempt(
            docker, container, retry, "worker-three", retry[3], succeeded=True
        ) != "succeeded":
            raise RuntimeError("successful retry was rejected")

        terminal = claim(docker, container, "worker-terminal", "ARRAY['directus']")
        if (
            terminal is None
            or terminal[0] != "00000000-0000-0000-0000-000000000003"
            or terminal[1] != 8
        ):
            raise RuntimeError("terminal attempt did not reach retry ceiling")
        if finish_attempt(
            docker,
            container,
            terminal,
            "worker-terminal",
            terminal[3],
            succeeded=False,
            error_class="TimeoutError",
        ) != "failed":
            raise RuntimeError("terminal failure completion was rejected")

        for _ in range(2):
            claim(docker, container, "recovery", "ARRAY[]::text[]")
        docker_sql(
            docker,
            container,
            "DO $$ BEGIN "
            "IF (SELECT count(*) FROM public.notification_outbox WHERE status='retryable' "
            "AND id IN ('00000000-0000-0000-0000-000000000004',"
            "'00000000-0000-0000-0000-000000000005'))<>2 THEN "
            "RAISE EXCEPTION 'expired recovery did not process both bounded rows'; END IF; "
            "IF (SELECT count(*) FROM public.notification_outbox_attempt "
            "WHERE status='lease_lost' AND error_class='LeaseExpired')<>2 THEN "
            "RAISE EXCEPTION 'expired attempts were not closed'; END IF; "
            "IF (SELECT status FROM public.notification_outbox WHERE id="
            "'00000000-0000-0000-0000-000000000001')<>'succeeded' OR "
            "(SELECT status FROM public.notification_outbox WHERE id="
            "'00000000-0000-0000-0000-000000000002')<>'succeeded' OR "
            "(SELECT status FROM public.notification_outbox WHERE id="
            "'00000000-0000-0000-0000-000000000003')<>'dead_letter' THEN "
            "RAISE EXCEPTION 'success, retry, or terminal transition is incorrect'; END IF; "
            "END $$;",
        )

        attempts_before = int(
            docker_sql(
                docker,
                container,
                "SELECT count(*) FROM public.notification_outbox_attempt;",
            ).strip()
        )
        docker_login_sql(
            docker,
            container,
            "BEGIN; SELECT * FROM kokonut_security.claim_notification_outbox_batch("
            "'rollback-check',1,300,ARRAY['email']); ROLLBACK;",
        )
        attempts_after = int(
            docker_sql(
                docker,
                container,
                "SELECT count(*) FROM public.notification_outbox_attempt;",
            ).strip()
        )
        if attempts_before != attempts_after:
            raise RuntimeError("rolled-back claim left an attempt receipt")

        docker_sql(docker, container, migration)
        docker_sql(
            docker,
            container,
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace "
            "WHERE n.nspname='public' AND r.relkind IN ('r','p','v','m','f') AND "
            "(has_table_privilege('kokonut_notification_delivery_login',r.oid,'SELECT') OR "
            "has_table_privilege('kokonut_notification_delivery_login',r.oid,'INSERT') OR "
            "has_table_privilege('kokonut_notification_delivery_login',r.oid,'UPDATE') OR "
            "has_table_privilege('kokonut_notification_delivery_login',r.oid,'DELETE') OR "
            "has_any_column_privilege('kokonut_notification_delivery_login',r.oid,'SELECT') OR "
            "has_any_column_privilege('kokonut_notification_delivery_login',r.oid,'INSERT') OR "
            "has_any_column_privilege('kokonut_notification_delivery_login',r.oid,'UPDATE'))) THEN "
            "RAISE EXCEPTION 'dedicated login has direct relation access'; END IF; "
            "IF EXISTS (SELECT 1 FROM pg_class s JOIN pg_namespace n ON n.oid=s.relnamespace "
            "WHERE s.relkind='S' AND n.nspname='public' AND "
            "(has_sequence_privilege('kokonut_notification_delivery_login',s.oid,'USAGE') OR "
            "has_sequence_privilege('kokonut_notification_delivery_login',s.oid,'SELECT') OR "
            "has_sequence_privilege('kokonut_notification_delivery_login',s.oid,'UPDATE'))) THEN "
            "RAISE EXCEPTION 'dedicated login has direct sequence access'; END IF; "
            "IF EXISTS (SELECT 1 FROM pg_class r "
            "CROSS JOIN LATERAL aclexplode(COALESCE(r.relacl,acldefault('r',r.relowner))) a "
            "WHERE r.oid IN ('public.notification_outbox'::regclass,"
            "'public.notification_outbox_attempt'::regclass) AND a.grantee=0) THEN "
            "RAISE EXCEPTION 'notification tables retain PUBLIC privileges'; END IF; "
            "IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='kokonut_security' AND p.prosecdef AND "
            "has_function_privilege('kokonut_notification_delivery_login',p.oid,'EXECUTE'))<>2 THEN "
            "RAISE EXCEPTION 'dedicated login lacks the exact bounded function set'; END IF; "
            "IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
            "WHERE n.nspname='kokonut_security' AND p.prosecdef AND a.grantee=0 "
            "AND a.privilege_type='EXECUTE') THEN "
            "RAISE EXCEPTION 'SECURITY DEFINER function remains executable by PUBLIC'; END IF; "
            "END $$;",
        )
        evidence = {
            "date": "2026-10-25",
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "database": "PostgreSQL 16 disposable container; Docker network disabled",
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "checks": [
                "migration 647 applies and replays while both notification tables are FORCE RLS",
                "migration removes PUBLIC table privileges from the private notification outbox relations",
                "the actual dedicated login enforces claim limits/channel allowlists and denies direct table, column, and sequence access",
                "bounded claim receipts, rollback, expired recovery, worker/token fencing, retry, and terminal dead-letter transitions pass",
                "migration replay preserves forced-RLS function ownership and the login has exactly two non-public bounded functions",
            ],
            "result": "passed",
            "isolation": "Synthetic schema and rows only; no candidate, legacy, provider, credential, or network access.",
        }
        output = args.output or EVIDENCE
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
