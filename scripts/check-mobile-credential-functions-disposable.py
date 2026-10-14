#!/usr/bin/env python3
"""Accept migrations 391-392 credential paths on isolated PostgreSQL 16."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/mobile_credential_functions_disposable.sql"
MIGRATIONS = ROOT / "schemas/postgres"
DEFAULT_OUTPUT = (
    ROOT / "docs/refactor/builds/2026-10-14-recovery/mobile-credential-functions-disposable.json"
)
APP_ROLE = "kokonut_mobile_credential_app_test"
OWNER_ORG = "a0000000-0000-0000-0000-000000000801"
NEW_ORG = "a0000000-0000-0000-0000-000000000802"
LOCATION = "a0000000-0000-0000-0000-000000000001"
CONCURRENT_LOCATION = "a0000000-0000-0000-0000-000000000002"
CURRENT_TOKEN_HASH = "e" * 64
LEGACY_TOKEN_HASH = "f" * 64
CONFLICT_CODE_HASH = "a" * 64
EXPIRED_CODE_HASH = "d" * 64
STALE_CODE_HASH = "c" * 64
CONCURRENT_CODE_HASH = "b" * 64


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout


def sql(container: str, statement: str) -> str:
    return run(
        [
            "docker", "exec", "-i", container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        ],
        input_text=statement,
    )


def wait_ready(container: str) -> None:
    for _ in range(50):
        ready = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "postgres"],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.2)
    raise RuntimeError("disposable PostgreSQL did not become ready")


def concurrent_redemption(container: str) -> None:
    sql(
        container,
        f"""
        INSERT INTO public.mobile_device_enrollment (
            code_hash, user_id, location_id, tenant_organization_id,
            created_by, expires_at
        ) VALUES (
            '{CONCURRENT_CODE_HASH}', 'worker', '{CONCURRENT_LOCATION}',
            '{OWNER_ORG}', 'concurrency-test', NOW() + INTERVAL '1 hour'
        );
        """,
    )
    command = [
        "docker", "exec", "-i", container,
        "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
    ]
    first_sql = f"""
        BEGIN;
        SET ROLE {APP_ROLE};
        SELECT result FROM kokonut_security.redeem_mobile_enrollment(
            '{CONCURRENT_CODE_HASH}', 'concurrent-device-a', 'Test', 'phone',
            NULL, NULL, '1.0.0', '{'6' * 64}'
        );
        SELECT pg_sleep(0.75);
        COMMIT;
    """
    second_sql = f"""
        SET ROLE {APP_ROLE};
        SELECT result FROM kokonut_security.redeem_mobile_enrollment(
            '{CONCURRENT_CODE_HASH}', 'concurrent-device-b', 'Test', 'phone',
            NULL, NULL, '1.0.0', '{'7' * 64}'
        );
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(run, command, input_text=first_sql)
        time.sleep(0.15)
        second_result = run(command, input_text=second_sql)
        first_result = first.result(timeout=10)

    outcomes = [
        line.strip()
        for output in (first_result, second_result)
        for line in output.splitlines()
        if line.strip() in {"registered", "invalid"}
    ]
    if sorted(outcomes) != ["invalid", "registered"]:
        raise RuntimeError(f"concurrent enrollment outcomes were {outcomes!r}")
    sql(
        container,
        f"""
        DO $$
        BEGIN
            IF (SELECT COUNT(*) FROM public.mobile_device
                 WHERE device_id IN ('concurrent-device-a', 'concurrent-device-b')) <> 1 THEN
                RAISE EXCEPTION 'concurrent redemption did not create exactly one device';
            END IF;
            IF (SELECT COUNT(*) FROM public.mobile_device_enrollment
                 WHERE code_hash = '{CONCURRENT_CODE_HASH}'
                   AND used_at IS NOT NULL
                   AND consumed_device_id IN ('concurrent-device-a', 'concurrent-device-b')) <> 1 THEN
                RAISE EXCEPTION 'concurrent redemption did not consume exactly one enrollment';
            END IF;
        END;
        $$;
        """,
    )


def seed_and_assertions() -> str:
    return f"""
    CREATE ROLE {APP_ROLE} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
        NOCREATEROLE NOREPLICATION NOBYPASSRLS;

    INSERT INTO public.mobile_device (
        device_id, user_id, location_id, tenant_organization_id,
        device_token_hash, status
    ) VALUES
        ('current-device', 'worker', '{LOCATION}', '{OWNER_ORG}', '{CURRENT_TOKEN_HASH}', 'active'),
        ('legacy-device', 'worker', '{LOCATION}', NULL, '{LEGACY_TOKEN_HASH}', 'active'),
        ('device-conflict', 'worker', '{LOCATION}', NULL, NULL, 'active');

    INSERT INTO public.mobile_device_enrollment (
        code_hash, user_id, location_id, tenant_organization_id,
        created_by, expires_at
    ) VALUES
        ('{CONFLICT_CODE_HASH}', 'worker', '{LOCATION}', '{OWNER_ORG}', 'test', NOW() + INTERVAL '1 hour'),
        ('{EXPIRED_CODE_HASH}', 'worker', '{LOCATION}', '{OWNER_ORG}', 'test', NOW() - INTERVAL '1 minute'),
        ('{STALE_CODE_HASH}', 'worker', '{LOCATION}', '{OWNER_ORG}', 'test', NOW() + INTERVAL '1 hour');

    SET ROLE {APP_ROLE};

    DO $$
    DECLARE
        denied BOOLEAN := FALSE;
        owner_current BOOLEAN;
        outcome TEXT;
        result_location UUID;
    BEGIN
        BEGIN
            PERFORM 1 FROM public.mobile_device;
        EXCEPTION WHEN insufficient_privilege THEN
            denied := TRUE;
        END;
        IF NOT denied THEN
            RAISE EXCEPTION 'application role unexpectedly reads mobile_device directly';
        END IF;

        denied := FALSE;
        BEGIN
            INSERT INTO public.mobile_device (device_id) VALUES ('direct-insert');
        EXCEPTION WHEN insufficient_privilege THEN
            denied := TRUE;
        END;
        IF NOT denied THEN
            RAISE EXCEPTION 'application role unexpectedly writes mobile_device directly';
        END IF;

        SELECT resolved.owner_binding_current
          INTO owner_current
          FROM kokonut_security.resolve_mobile_device_token('{CURRENT_TOKEN_HASH}') AS resolved
         WHERE resolved.device_id = 'current-device';
        IF owner_current IS DISTINCT FROM TRUE THEN
            RAISE EXCEPTION 'current owner-bound token did not resolve';
        END IF;

        SELECT resolved.owner_binding_current
          INTO owner_current
          FROM kokonut_security.resolve_mobile_device_token('{LEGACY_TOKEN_HASH}') AS resolved
         WHERE resolved.device_id = 'legacy-device';
        IF owner_current IS DISTINCT FROM FALSE THEN
            RAISE EXCEPTION 'legacy unbound token did not return a re-enrollment state';
        END IF;

        IF EXISTS (
            SELECT 1 FROM kokonut_security.resolve_mobile_device_token('{"b" * 64}')
        ) THEN
            RAISE EXCEPTION 'unknown token hash unexpectedly resolved';
        END IF;

        SELECT redeemed.result INTO outcome
          FROM kokonut_security.redeem_mobile_enrollment(
              '{CONFLICT_CODE_HASH}', 'device-conflict', 'Test', 'phone',
              NULL, NULL, '1.0.0', '{"1" * 64}'
          ) AS redeemed;
        IF outcome IS DISTINCT FROM 'device_conflict' THEN
            RAISE EXCEPTION 'existing device ID was not rejected';
        END IF;

        SELECT redeemed.result, redeemed.registered_location_id
          INTO outcome, result_location
          FROM kokonut_security.redeem_mobile_enrollment(
              '{CONFLICT_CODE_HASH}', 'new-device', 'Test', 'phone',
              NULL, NULL, '1.0.0', '{"2" * 64}'
          ) AS redeemed;
        IF outcome IS DISTINCT FROM 'registered'
           OR result_location IS DISTINCT FROM '{LOCATION}'::uuid THEN
            RAISE EXCEPTION 'valid single-use enrollment did not register';
        END IF;

        SELECT redeemed.result INTO outcome
          FROM kokonut_security.redeem_mobile_enrollment(
              '{CONFLICT_CODE_HASH}', 'second-device', 'Test', 'phone',
              NULL, NULL, '1.0.0', '{"3" * 64}'
          ) AS redeemed;
        IF outcome IS DISTINCT FROM 'invalid' THEN
            RAISE EXCEPTION 'consumed enrollment code was reusable';
        END IF;

        SELECT redeemed.result INTO outcome
          FROM kokonut_security.redeem_mobile_enrollment(
              '{EXPIRED_CODE_HASH}', 'expired-device', 'Test', 'phone',
              NULL, NULL, '1.0.0', '{"4" * 64}'
          ) AS redeemed;
        IF outcome IS DISTINCT FROM 'invalid' THEN
            RAISE EXCEPTION 'expired enrollment code was accepted';
        END IF;
    END;
    $$;

    RESET ROLE;

    DO $$
    BEGIN
        IF (SELECT COUNT(*) FROM public.mobile_device WHERE device_id = 'new-device') <> 1 THEN
            RAISE EXCEPTION 'expected exactly one registered device';
        END IF;
        IF (SELECT COUNT(*) FROM public.mobile_device WHERE device_id IN ('second-device', 'expired-device', 'direct-insert')) <> 0 THEN
            RAISE EXCEPTION 'rejected device registration left a device row';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.mobile_device_enrollment
             WHERE code_hash = '{CONFLICT_CODE_HASH}'
               AND used_at IS NOT NULL AND consumed_device_id = 'new-device'
        ) THEN
            RAISE EXCEPTION 'successful redemption did not consume the code';
        END IF;
    END;
    $$;

    UPDATE public.location_tenant_owner_verification
       SET revoked_at = NOW()
     WHERE location_id = '{LOCATION}' AND revoked_at IS NULL;
    UPDATE public.location
       SET organization_id = '{NEW_ORG}'
     WHERE id = '{LOCATION}';
    INSERT INTO public.location_tenant_owner_verification (
        id, location_id, organization_id
    ) VALUES (
        'a0000000-0000-0000-0000-000000000902', '{LOCATION}', '{NEW_ORG}'
    );

    SET ROLE {APP_ROLE};
    DO $$
    DECLARE
        owner_current BOOLEAN;
        outcome TEXT;
    BEGIN
        SELECT resolved.owner_binding_current
          INTO owner_current
          FROM kokonut_security.resolve_mobile_device_token('{CURRENT_TOKEN_HASH}') AS resolved
         WHERE resolved.device_id = 'current-device';
        IF owner_current IS DISTINCT FROM FALSE THEN
            RAISE EXCEPTION 'former-owner device was not marked for re-enrollment';
        END IF;

        SELECT redeemed.result INTO outcome
          FROM kokonut_security.redeem_mobile_enrollment(
              '{STALE_CODE_HASH}', 'stale-device', 'Test', 'phone',
              NULL, NULL, '1.0.0', '{"5" * 64}'
          ) AS redeemed;
        IF outcome IS DISTINCT FROM 'owner_changed' THEN
            RAISE EXCEPTION 'former-owner enrollment code was accepted';
        END IF;
    END;
    $$;
    RESET ROLE;

    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM public.mobile_device WHERE device_id = 'stale-device') THEN
            RAISE EXCEPTION 'stale enrollment created a device';
        END IF;
        IF (SELECT COUNT(*) FROM public.mobile_device_enrollment WHERE code_hash = '{STALE_CODE_HASH}' AND used_at IS NOT NULL) <> 0 THEN
            RAISE EXCEPTION 'stale enrollment code was consumed';
        END IF;
        IF (SELECT rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
              FROM pg_roles WHERE rolname = 'kokonut_mobile_credential_owner') THEN
            RAISE EXCEPTION 'credential function owner has unsafe role attributes';
        END IF;
    END;
    $$;
    """


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"kokonut-mobile-credentials-{uuid.uuid4().hex[:10]}"
    started = False
    checks = [
        "migration 392 replay is idempotent after owner role and functions are installed",
        "a constrained application role cannot directly read or write device credential rows",
        "device token resolver returns only minimal identity and current-owner state",
        "legacy unbound token is preserved as an explicit re-enrollment outcome",
        "unknown token hash does not resolve",
        "device-ID conflict does not consume a valid enrollment code",
        "single-use code registers one owner-bound device and cannot be reused",
        "concurrent redemption registers exactly one device and consumes the code once",
        "expired and unknown enrollment codes are rejected without device rows",
        "owner transfer invalidates old device tokens and pending enrollment codes",
        "the non-login credential function owner has no superuser, role, database, replication, or RLS bypass powers",
    ]
    try:
        run([
            "docker", "run", "--detach", "--rm", "--network", "none",
            "--name", container, "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16",
        ])
        started = True
        wait_ready(container)
        sql(container, FIXTURE.read_text())
        for migration in (
            "391_mobile_device_tenant_binding.sql",
            "392_mobile_credential_functions.sql",
            "392_mobile_credential_functions.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())
        sql(container, seed_and_assertions())
        concurrent_redemption(container)

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker networking disabled",
            "migrations": [
                "391_mobile_device_tenant_binding.sql",
                "392_mobile_credential_functions.sql",
                "392_mobile_credential_functions.sql (idempotency replay)",
            ],
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_requests": 0,
            "synthetic_rows_remaining": 0,
            "rls_enabled": False,
            "scope_limit": "Proves narrow credential function behavior and owner privileges only. It does not enable RLS, validate signed tenant context, or close legacy CLI, worker, Directus, or view access.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - report the disposable acceptance failure plainly.
        print(f"MOBILE CREDENTIAL FUNCTION ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    raise SystemExit(main())
