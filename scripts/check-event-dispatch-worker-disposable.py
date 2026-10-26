#!/usr/bin/env python3
"""Replay migration 648 and exercise the bounded EventBus worker API."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/648_isolated_event_dispatch_worker.sql"
LOGIN = "kokonut_event_dispatch_login"
PASSWORD = "synthetic-event-dispatch-password"

FIXTURE = """
CREATE TABLE public.platform_event (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 event_type VARCHAR(100) NOT NULL,
 source_table VARCHAR(100), source_id UUID,
 payload JSONB NOT NULL DEFAULT '{}',
 priority VARCHAR(20) NOT NULL DEFAULT 'normal'
   CHECK (priority IN ('critical','high','normal','low')),
 status VARCHAR(20) NOT NULL DEFAULT 'pending'
   CHECK (status IN ('pending','processing','completed','failed','dead_letter')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), processed_at TIMESTAMPTZ,
 worker_id VARCHAR(100), retry_count INTEGER NOT NULL DEFAULT 0,
 max_retries INTEGER NOT NULL DEFAULT 3, error_message TEXT, metadata JSONB,
 claimed_at TIMESTAMPTZ, lease_owner VARCHAR(100), lease_expires_at TIMESTAMPTZ
);
CREATE INDEX idx_platform_event_claimable
 ON public.platform_event(status, lease_expires_at, created_at);
CREATE TABLE public.event_handler (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), handler_name VARCHAR(100) NOT NULL UNIQUE,
 event_type VARCHAR(100) NOT NULL, module_path VARCHAR(200) NOT NULL,
 function_name VARCHAR(100) NOT NULL DEFAULT 'handle', is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
 priority_order INTEGER NOT NULL DEFAULT 0, timeout_seconds INTEGER NOT NULL DEFAULT 30,
 max_concurrency INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.event_handler_delivery (
 event_id UUID NOT NULL REFERENCES public.platform_event(id) ON DELETE CASCADE,
 handler_id UUID NOT NULL REFERENCES public.event_handler(id) ON DELETE CASCADE,
 status VARCHAR(20) NOT NULL DEFAULT 'pending'
   CHECK (status IN ('pending','processing','success','error','timeout')),
 attempt_count INTEGER NOT NULL DEFAULT 0, started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ, last_error TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 PRIMARY KEY(event_id, handler_id)
);
CREATE TABLE public.event_handler_log (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 event_id UUID NOT NULL REFERENCES public.platform_event(id) ON DELETE CASCADE,
 handler_id UUID NOT NULL REFERENCES public.event_handler(id) ON DELETE CASCADE,
 status VARCHAR(20) NOT NULL CHECK (status IN ('success','error','skipped','timeout')),
 duration_ms INTEGER, error_message TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE public.event_dead_letter (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), original_event_id UUID NOT NULL,
 event_type VARCHAR(100) NOT NULL, payload JSONB NOT NULL,
 failure_count INTEGER NOT NULL, last_error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 disposition VARCHAR(20) NOT NULL DEFAULT 'pending'
   CHECK (disposition IN ('pending','replayed','resolved','discarded')),
 disposition_reason TEXT, disposed_by VARCHAR(100), disposed_at TIMESTAMPTZ, replayed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_event_dead_letter_active_event
 ON public.event_dead_letter(original_event_id) WHERE disposition='pending';
INSERT INTO public.platform_event (id,event_type,payload,priority,max_retries) VALUES
 ('10000000-0000-0000-0000-000000000001','sensor_reading','{"sample":1}','high',3),
 ('10000000-0000-0000-0000-000000000002','alert_failure','{"sample":2}','normal',1),
 ('10000000-0000-0000-0000-000000000003','no_handler','{"sample":3}','low',3),
 ('10000000-0000-0000-0000-000000000004','rollback_probe','{"sample":4}','low',3);
INSERT INTO public.event_handler (id,handler_name,event_type,module_path,function_name,priority_order,timeout_seconds) VALUES
 ('20000000-0000-0000-0000-000000000001','sensor-handler','sensor_reading','services.events.handlers','handle_sensor',1,30),
 ('20000000-0000-0000-0000-000000000002','alert-handler','alert_failure','services.events.handlers','handle_alert',1,45);
ALTER TABLE public.platform_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_event FORCE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler FORCE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler_delivery FORCE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_handler_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.event_dead_letter ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_dead_letter FORCE ROW LEVEL SECURITY;
"""


def run(command: list[str], *, input_text: str | None = None, ok: bool = True) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if ok and result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    if not ok and result.returncode == 0:
        raise RuntimeError("a denied disposable command unexpectedly succeeded")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    ).strip()


def docker_login_sql(docker: str, container: str, statement: str, *, ok: bool = True) -> str:
    return run(
        [docker, "exec", "-e", f"PGPASSWORD={PASSWORD}", "-i", container,
         "psql", "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1",
         "-U", LOGIN, "-d", "postgres"],
        input_text=statement,
        ok=ok,
    ).strip()


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 120
    stable_successes = 0
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "psql", "-X", "-q", "-t", "-A",
             "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-c", "SELECT 1"],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            stable_successes += 1
            if stable_successes >= 5:
                return
        else:
            stable_successes = 0
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def _one(result: str, expected_fields: int) -> list[str]:
    fields = result.split("\t")
    if len(fields) != expected_fields:
        raise RuntimeError(f"unexpected bounded-function result shape: {result!r}")
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default="postgres:16")
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-event-dispatch-{secrets.token_hex(4)}"
    migration = MIGRATION.read_text(encoding="utf-8")
    created = False
    try:
        command = [docker, "run", "-d", "--rm", "--network", "none", "--name", container]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(("-e", "POSTGRES_PASSWORD=" + secrets.token_urlsafe(24), args.image))
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
            docker, container,
            f"ALTER ROLE {LOGIN} WITH LOGIN PASSWORD '{PASSWORD}'; GRANT CONNECT ON DATABASE postgres TO {LOGIN};",
        )

        docker_login_sql(
            docker, container,
            f"""DO $$ BEGIN
             IF session_user <> '{LOGIN}' THEN RAISE EXCEPTION 'actual login not established'; END IF;
             BEGIN PERFORM * FROM public.platform_event; RAISE EXCEPTION 'direct event read succeeded';
             EXCEPTION WHEN insufficient_privilege THEN NULL; END;
             BEGIN UPDATE public.platform_event SET status='completed'; RAISE EXCEPTION 'direct event update succeeded';
             EXCEPTION WHEN insufficient_privilege THEN NULL; END;
             BEGIN PERFORM * FROM public.event_handler; RAISE EXCEPTION 'direct handler read succeeded';
             EXCEPTION WHEN insufficient_privilege THEN NULL; END;
             BEGIN INSERT INTO public.event_handler_log(event_id,handler_id,status)
               VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','success');
               RAISE EXCEPTION 'direct log insert succeeded'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
             BEGIN PERFORM * FROM kokonut_security.claim_platform_event_batch('worker',101,300);
               RAISE EXCEPTION 'oversized claim succeeded'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
             BEGIN PERFORM * FROM kokonut_security.claim_platform_event_batch('worker',1,29);
               RAISE EXCEPTION 'short lease succeeded'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
            END $$;""",
        )

        claim = _one(docker_login_sql(
            docker, container,
            "SELECT id,event_type,retry_count,max_retries,lease_token "
            "FROM kokonut_security.claim_platform_event_batch('worker-one',1,300);",
        ), 5)
        event_id, event_type, retry_count, max_retries, token = claim
        if event_type != "sensor_reading" or retry_count != "0":
            raise RuntimeError(f"priority claim selected unexpected event: {claim!r}")
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.complete_platform_event('{event_id}','worker-one','{token}');",
        ) != "f":
            raise RuntimeError("event with pending enabled handlers completed without delivery")

        handlers = docker_login_sql(
            docker, container,
            f"SELECT handler_id,module_path,function_name,timeout_seconds,COALESCE(delivery_status,'<none>') "
            f"FROM kokonut_security.list_platform_event_handlers('{event_id}','{event_type}','worker-one','{token}');",
        )
        handler_fields = _one(handlers, 5)
        handler_id = handler_fields[0]
        if handler_fields[1:] != ["services.events.handlers", "handle_sensor", "30", "<none>"]:
            raise RuntimeError(f"handler lookup returned an unexpected registration: {handler_fields!r}")

        docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.begin_platform_event_handler('{event_id}','{handler_id}','worker-one','{token}');",
        )
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.finish_platform_event_handler('{event_id}','{handler_id}','worker-one','{token}','success',15,NULL);",
        ) != "t":
            raise RuntimeError("valid handler completion was rejected")
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.complete_platform_event('{event_id}','worker-one','{token}');",
        ) != "t":
            raise RuntimeError("valid event completion was rejected")
        docker_sql(
            docker, container,
            f"DO $$ BEGIN IF (SELECT status FROM public.platform_event WHERE id='{event_id}') <> 'completed' "
            f"OR (SELECT count(*) FROM public.event_handler_log WHERE event_id='{event_id}') <> 1 "
            "THEN RAISE EXCEPTION 'success did not write completion and one attempt log'; END IF; END $$;",
        )

        # Exact token and event-type binding prevents a worker from selecting a
        # different event's handler registry.
        docker_login_sql(
            docker, container,
            f"SELECT * FROM kokonut_security.list_platform_event_handlers('{event_id}','wrong_type','worker-one','{token}');",
            ok=False,
        )

        failure = _one(docker_login_sql(
            docker, container,
            "SELECT id,event_type,retry_count,max_retries,lease_token "
            "FROM kokonut_security.claim_platform_event_batch('worker-two',1,300);",
        ), 5)
        if failure[1] != "alert_failure":
            raise RuntimeError(f"second event claim returned unexpected source: {failure!r}")
        failed_handler = "20000000-0000-0000-0000-000000000002"
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.retry_platform_event('{failure[0]}','worker-two','{failure[4]}',1,1);",
        ) != "lease_lost":
            raise RuntimeError("event retried without a failed handler receipt")
        docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.begin_platform_event_handler('{failure[0]}','{failed_handler}','worker-two','{failure[4]}');",
        )
        docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.finish_platform_event_handler('{failure[0]}','{failed_handler}','worker-two','{failure[4]}','error',25,'Handler failed (OSError)');",
        )
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.retry_platform_event('{failure[0]}','worker-two','{failure[4]}',1,1);",
        ) != "dead_letter":
            raise RuntimeError("terminal retry did not dead-letter the event")
        docker_sql(
            docker, container,
            f"DO $$ BEGIN IF (SELECT count(*) FROM public.event_dead_letter WHERE original_event_id='{failure[0]}') <> 1 "
            "OR (SELECT status FROM public.event_handler_delivery WHERE event_id='"
            f"{failure[0]}' AND handler_id='{failed_handler}') <> 'error' "
            "THEN RAISE EXCEPTION 'failure did not atomically persist handler/dead-letter state'; END IF; END $$;",
        )

        no_handler = _one(docker_login_sql(
            docker, container,
            "SELECT id,event_type,retry_count,max_retries,lease_token "
            "FROM kokonut_security.claim_platform_event_batch('worker-three',1,300);",
        ), 5)
        if no_handler[1] != "no_handler":
            raise RuntimeError(f"third event claim returned unexpected source: {no_handler!r}")
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.complete_platform_event('{no_handler[0]}','wrong-worker','{no_handler[4]}');",
        ) != "f":
            raise RuntimeError("wrong worker completed an event lease")
        docker_sql(
            docker, container,
            f"UPDATE public.platform_event SET lease_expires_at=NOW()-INTERVAL '1 minute' WHERE id='{no_handler[0]}';",
        )
        reclaimed = _one(docker_login_sql(
            docker, container,
            "SELECT id,event_type,retry_count,max_retries,lease_token "
            "FROM kokonut_security.claim_platform_event_batch('worker-four',1,300);",
        ), 5)
        if reclaimed[0] != no_handler[0] or reclaimed[4] == no_handler[4]:
            raise RuntimeError("expired event lease was not reclaimed with a fresh token")
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.complete_platform_event('{reclaimed[0]}','worker-three','{no_handler[4]}');",
        ) != "f":
            raise RuntimeError("stale worker/token completed a reclaimed lease")
        if docker_login_sql(
            docker, container,
            f"SELECT kokonut_security.complete_platform_event('{reclaimed[0]}','worker-four','{reclaimed[4]}');",
        ) != "t":
            raise RuntimeError("current lease owner could not complete reclaimed event")

        before = docker_sql(docker, container, "SELECT count(*) FROM public.platform_event WHERE status='pending';")
        docker_login_sql(
            docker, container,
            "BEGIN; SELECT * FROM kokonut_security.claim_platform_event_batch('rollback-check',1,300); ROLLBACK;",
        )
        after = docker_sql(docker, container, "SELECT count(*) FROM public.platform_event WHERE status='pending';")
        if before != after:
            raise RuntimeError("rolled-back bounded claim left queue mutations")

        docker_sql(docker, container, migration)
        docker_sql(
            docker, container,
            f"""DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_class rel JOIN pg_namespace ns ON ns.oid=rel.relnamespace
                WHERE ns.nspname='public' AND rel.relkind IN ('r','p','v','m','f') AND
                (has_table_privilege('{LOGIN}',rel.oid,'SELECT') OR has_table_privilege('{LOGIN}',rel.oid,'INSERT') OR
                 has_table_privilege('{LOGIN}',rel.oid,'UPDATE') OR has_table_privilege('{LOGIN}',rel.oid,'DELETE') OR
                 has_any_column_privilege('{LOGIN}',rel.oid,'SELECT') OR has_any_column_privilege('{LOGIN}',rel.oid,'INSERT') OR
                 has_any_column_privilege('{LOGIN}',rel.oid,'UPDATE'))) THEN RAISE EXCEPTION 'direct relation privileges exist'; END IF;
              IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                  WHERE n.nspname='kokonut_security' AND p.prosecdef AND has_function_privilege('{LOGIN}',p.oid,'EXECUTE')) <> 7
                THEN RAISE EXCEPTION 'login does not have exactly seven bounded functions'; END IF;
              IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
                WHERE n.nspname='kokonut_security' AND p.prosecdef AND acl.grantee=0 AND acl.privilege_type='EXECUTE')
                THEN RAISE EXCEPTION 'PUBLIC can execute a security definer function'; END IF;
              IF NOT (SELECT relforcerowsecurity FROM pg_class WHERE oid='public.platform_event'::regclass)
                OR NOT (SELECT relforcerowsecurity FROM pg_class WHERE oid='public.event_handler_delivery'::regclass)
                THEN RAISE EXCEPTION 'forced RLS fixture state was not preserved'; END IF;
             END $$;""",
        )

        evidence = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "migration": MIGRATION.name,
            "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
            "database": "PostgreSQL 16 disposable container; Docker network disabled",
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "checks": [
                "migration 648 applies and replays over forced-RLS EventBus fixtures",
                "actual dedicated login has no direct relation access and only seven bounded functions",
                "claim order, bounds, handler registry binding, transaction rollback, and exact event type are enforced",
                "completion is denied until every enabled handler succeeds, and retry is denied until a handler failure receipt exists",
                "handler success/error receipts, atomic dead-letter, expiry reclaim, and stale worker/token fencing pass",
            ],
            "result": "passed",
            "isolation": "Synthetic event/handler rows only; no candidate, legacy, handler process, provider, credential, or network access.",
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
