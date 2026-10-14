#!/usr/bin/env python3
"""Accept mobile credential and signed-context migrations on isolated PostgreSQL 16."""

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
    ROOT / "docs/refactor/builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json"
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
CONTEXT_TOKEN_HASH = "8" * 64
CONTEXT_ENROLLMENT_HASH = "9" * 64


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
    previous_start_time = None
    stable_samples = 0
    for _ in range(50):
        ready = subprocess.run(
            [
                "docker", "exec", container, "psql", "-X", "-qAt",
                "-U", "postgres", "-d", "postgres",
                "-c", "SELECT pg_postmaster_start_time()::text",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0 and ready.stdout.strip():
            current_start_time = ready.stdout.strip()
            stable_samples = stable_samples + 1 if current_start_time == previous_start_time else 1
            previous_start_time = current_start_time
            if stable_samples >= 2:
                return
        else:
            previous_start_time = None
            stable_samples = 0
        time.sleep(0.25)
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
            NULL, NULL, '1.0.0', '{"6" * 64}'
        );
        SELECT pg_sleep(0.75);
        COMMIT;
    """
    second_sql = f"""
        SET ROLE {APP_ROLE};
        SELECT result FROM kokonut_security.redeem_mobile_enrollment(
            '{CONCURRENT_CODE_HASH}', 'concurrent-device-b', 'Test', 'phone',
            NULL, NULL, '1.0.0', '{"7" * 64}'
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


def forced_rls_context_assertions(container: str) -> None:
    sql(
        container,
        f"""
        INSERT INTO public.mobile_device (
            device_id, user_id, location_id, tenant_organization_id,
            device_token_hash, status
        ) VALUES (
            'context-device', 'worker', '{CONCURRENT_LOCATION}', '{OWNER_ORG}',
            '{CONTEXT_TOKEN_HASH}', 'active'
        );
        INSERT INTO public.mobile_device_enrollment (
            code_hash, user_id, location_id, tenant_organization_id,
            created_by, expires_at
        ) VALUES (
            '{CONTEXT_ENROLLMENT_HASH}', 'worker', '{CONCURRENT_LOCATION}',
            '{OWNER_ORG}', 'rls-test', NOW() + INTERVAL '1 hour'
        );

        DO $$
        DECLARE
            resolved_tenant UUID;
        BEGIN
            SELECT context.tenant_id INTO resolved_tenant
              FROM kokonut_security.set_mobile_device_context(
                  '{CONTEXT_TOKEN_HASH}', 'context-device', '{CONCURRENT_LOCATION}'::uuid
              ) AS context;
            IF resolved_tenant IS DISTINCT FROM '{OWNER_ORG}'::uuid THEN
                RAISE EXCEPTION 'mobile context function failed before forced RLS';
            END IF;
        END;
        $$;

        CREATE TABLE public.mobile_context_probe (
            tenant_organization_id UUID NOT NULL,
            value TEXT NOT NULL
        );
        INSERT INTO public.mobile_context_probe VALUES
            ('{OWNER_ORG}', 'owner-visible'),
            ('{NEW_ORG}', 'other-tenant-hidden');
        CREATE POLICY mobile_context_probe_scope
            ON public.mobile_context_probe
            FOR SELECT TO {APP_ROLE}
            USING (
                EXISTS (
                    SELECT 1
                      FROM kokonut_security.current_tenant_context() AS context
                     WHERE context.tenant_id = tenant_organization_id
                )
            );
        GRANT SELECT ON public.mobile_context_probe TO {APP_ROLE};

        ALTER TABLE public.mobile_device ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.mobile_device FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.mobile_device_enrollment ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.mobile_device_enrollment FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.mobile_context_probe ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.mobile_context_probe FORCE ROW LEVEL SECURITY;
        """,
    )

    sql(
        container,
        f"""
        SET ROLE kokonut_mobile_context_owner;
        DO $$
        DECLARE
            matching_rows INTEGER;
            device_rows INTEGER;
            location_rows INTEGER;
            owner_rows INTEGER;
            tenant_rows INTEGER;
        BEGIN
            SELECT COUNT(*) INTO device_rows
              FROM public.mobile_device
             WHERE device_id = 'context-device'
               AND device_token_hash = '{CONTEXT_TOKEN_HASH}';
            SELECT COUNT(*) INTO location_rows
              FROM public.location
             WHERE id = '{CONCURRENT_LOCATION}'::uuid;
            SELECT COUNT(*) INTO owner_rows
              FROM public.location_tenant_owner_verification
             WHERE location_id = '{CONCURRENT_LOCATION}'::uuid
               AND organization_id = '{OWNER_ORG}'::uuid
               AND revoked_at IS NULL;
            SELECT COUNT(*) INTO tenant_rows
              FROM public.organization
             WHERE id = '{OWNER_ORG}'::uuid AND status = 'active';
            IF device_rows <> 1 OR location_rows <> 1
               OR owner_rows <> 1 OR tenant_rows <> 1 THEN
                RAISE EXCEPTION 'context owner RLS visibility: device %, location %, owner %, organization %',
                    device_rows, location_rows, owner_rows, tenant_rows;
            END IF;

            SELECT COUNT(*) INTO matching_rows
              FROM (
                  SELECT device.id
                    FROM public.mobile_device AS device
                    JOIN public.location AS location ON location.id = device.location_id
                    JOIN public.location_tenant_owner_verification AS owner
                      ON owner.location_id = location.id
                     AND owner.organization_id = location.organization_id
                     AND owner.revoked_at IS NULL
                    JOIN public.organization AS tenant
                      ON tenant.id = owner.organization_id
                     AND tenant.status = 'active'
                   WHERE device.device_id = 'context-device'
                     AND device.device_token_hash = '{CONTEXT_TOKEN_HASH}'
                     AND device.tenant_organization_id = location.organization_id
                     AND location.id = '{CONCURRENT_LOCATION}'::uuid
                   FOR SHARE OF device, location, owner, tenant
              ) AS matching;
            IF matching_rows <> 1 THEN
                RAISE EXCEPTION 'context owner sees % matching locked owner/device rows under forced RLS', matching_rows;
            END IF;
        END;
        $$;
        RESET ROLE;
        """,
    )

    sql(
        container,
        f"""
        SET ROLE {APP_ROLE};
        BEGIN;
        DO $$
        DECLARE
            visible_count INTEGER;
            resolved_tenant UUID;
            current_owner BOOLEAN;
            redemption_result TEXT;
            denied BOOLEAN := FALSE;
        BEGIN
            PERFORM set_config('kokonut.tenant_id', '{OWNER_ORG}', TRUE);
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'caller-controlled tenant GUC granted row access';
            END IF;

            SELECT context.tenant_id INTO resolved_tenant
              FROM kokonut_security.set_mobile_device_context(
                  '{CONTEXT_TOKEN_HASH}', 'context-device', '{CONCURRENT_LOCATION}'::uuid
              ) AS context;
            IF resolved_tenant IS DISTINCT FROM '{OWNER_ORG}'::uuid THEN
                RAISE EXCEPTION 'valid device credential did not establish context';
            END IF;
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 1 THEN
                RAISE EXCEPTION 'signed context did not restrict access to the device tenant';
            END IF;

            PERFORM set_config(
                'kokonut.context_payload',
                (current_setting('kokonut.context_payload')::jsonb
                    || jsonb_build_object('tenant_id', '{NEW_ORG}'))::text,
                TRUE
            );
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'tampered tenant payload passed HMAC validation';
            END IF;

            SELECT context.tenant_id INTO resolved_tenant
              FROM kokonut_security.set_mobile_device_context(
                  '{CONTEXT_TOKEN_HASH}', 'context-device', '{CONCURRENT_LOCATION}'::uuid
              ) AS context;
            PERFORM set_config('kokonut.context_signature', repeat('0', 64), TRUE);
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'forged context signature granted row access';
            END IF;

            SELECT context.tenant_id INTO resolved_tenant
              FROM kokonut_security.set_mobile_device_context(
                  '{CONTEXT_TOKEN_HASH}', 'context-device', '{CONCURRENT_LOCATION}'::uuid
              ) AS context;
            SELECT resolved.owner_binding_current INTO current_owner
              FROM kokonut_security.resolve_mobile_device_token('{CONTEXT_TOKEN_HASH}') AS resolved
             WHERE resolved.device_id = 'context-device';
            IF current_owner IS DISTINCT FROM TRUE THEN
                RAISE EXCEPTION 'credential resolver failed under forced RLS';
            END IF;

            SELECT redeemed.result INTO redemption_result
              FROM kokonut_security.redeem_mobile_enrollment(
                  '{CONTEXT_ENROLLMENT_HASH}', 'context-registered-device', 'Test', 'phone',
                  NULL, NULL, '1.0.0', '{'a' * 64}'
              ) AS redeemed;
            IF redemption_result IS DISTINCT FROM 'registered' THEN
                RAISE EXCEPTION 'credential redemption failed under forced RLS: %', redemption_result;
            END IF;

            BEGIN
                PERFORM 1 FROM public.mobile_device;
            EXCEPTION WHEN insufficient_privilege THEN
                denied := TRUE;
            END;
            IF NOT denied THEN
                RAISE EXCEPTION 'ordinary app role read mobile_device directly under forced RLS';
            END IF;

            denied := FALSE;
            BEGIN
                PERFORM 1 FROM kokonut_security.mobile_context_hmac_key;
            EXCEPTION WHEN insufficient_privilege THEN
                denied := TRUE;
            END;
            IF NOT denied THEN
                RAISE EXCEPTION 'ordinary app role read the private mobile context signing key';
            END IF;

            PERFORM set_config(
                'kokonut.context_payload',
                jsonb_build_object(
                    'backend_pid', pg_backend_pid(),
                    'transaction_id', txid_current(),
                    'tenant_id', '{OWNER_ORG}',
                    'location_id', '{CONCURRENT_LOCATION}',
                    'actor_id', 'a0000000-0000-0000-0000-000000000999',
                    'actor_type', 'mobile_device',
                    'nonce', 'forged'
                )::text,
                TRUE
            );
            PERFORM set_config('kokonut.context_signature', repeat('0', 64), TRUE);
            PERFORM set_config('kokonut.tenant_id', '{OWNER_ORG}', TRUE);
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'forged custom settings bypassed the signed context accessor';
            END IF;

            SELECT context.tenant_id INTO resolved_tenant
              FROM kokonut_security.set_mobile_device_context(
                  repeat('0', 64), 'context-device', '{CONCURRENT_LOCATION}'::uuid
              ) AS context;
            IF resolved_tenant IS NOT NULL THEN
                RAISE EXCEPTION 'invalid token hash unexpectedly established context';
            END IF;
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'invalid context attempt retained an earlier signature';
            END IF;
        END;
        $$;
        COMMIT;

        BEGIN;
        DO $$
        DECLARE
            visible_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO visible_count FROM public.mobile_context_probe;
            IF visible_count <> 0 THEN
                RAISE EXCEPTION 'signed transaction context survived transaction end';
            END IF;
        END;
        $$;
        COMMIT;
        RESET ROLE;
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
        "migrations 392 and 393 replay idempotently after roles and functions are installed",
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
        "forced RLS accepts only a valid device-token HMAC context and filters cross-tenant rows",
        "caller-controlled GUC, tampered payload/signature, invalid token, and ended-transaction context all fail closed",
        "credential resolution and single-use redemption continue working under forced RLS through non-login roles",
        "definer roles retain forced-RLS row-lock access through narrow column grants",
        "the application role cannot read the private context-signing key or credential tables",
        "migrations 391-393 leave application-table RLS disabled",
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
            "393_mobile_tenant_context_proof.sql",
            "393_mobile_tenant_context_proof.sql",
        ):
            sql(container, (MIGRATIONS / migration).read_text())
        sql(
            container,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                      FROM pg_class AS relation
                      JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                     WHERE namespace.nspname = 'public'
                       AND relation.relname IN (
                           'mobile_device', 'mobile_device_enrollment',
                           'location', 'location_tenant_owner_verification', 'organization'
                       )
                       AND relation.relrowsecurity
                ) THEN
                    RAISE EXCEPTION 'credential/context migrations enabled application-table RLS';
                END IF;
                IF EXISTS (
                    SELECT 1
                      FROM pg_roles AS role
                     WHERE role.rolname IN (
                         'kokonut_mobile_credential_owner', 'kokonut_mobile_context_owner'
                     )
                       AND (role.rolcanlogin OR role.rolsuper OR role.rolcreatedb
                            OR role.rolcreaterole OR role.rolreplication OR role.rolbypassrls)
                ) THEN
                    RAISE EXCEPTION 'a credential/context function owner has unsafe role attributes';
                END IF;
                IF EXISTS (
                    SELECT 1
                      FROM pg_auth_members AS membership
                      JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
                      JOIN pg_roles AS member_role ON member_role.oid = membership.member
                     WHERE granted_role.rolname IN (
                               'kokonut_mobile_credential_owner', 'kokonut_mobile_context_owner'
                           )
                        OR member_role.rolname IN (
                               'kokonut_mobile_credential_owner', 'kokonut_mobile_context_owner'
                           )
                ) THEN
                    RAISE EXCEPTION 'a credential/context function owner has role membership';
                END IF;
            END;
            $$;
            """,
        )
        sql(container, seed_and_assertions())
        concurrent_redemption(container)
        forced_rls_context_assertions(container)

        report = {
            "result": "passed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL 16 disposable container with Docker networking disabled",
            "migrations": [
                "391_mobile_device_tenant_binding.sql",
                "392_mobile_credential_functions.sql",
                "392_mobile_credential_functions.sql (idempotency replay)",
                "393_mobile_tenant_context_proof.sql",
                "393_mobile_tenant_context_proof.sql (idempotency replay)",
            ],
            "checks": checks,
            "candidate_database_touched": False,
            "legacy_database_touched": False,
            "external_network_requests": 0,
            "synthetic_rows_remaining": 0,
            "rls_enabled": False,
            "disposable_forced_rls": True,
            "scope_limit": "Proves mobile credential functions under disposable forced RLS and signed transaction-context behavior only. It does not enable application-table RLS on the candidate, validate operator/Gateway context, or close legacy CLI, worker, Directus, or view access.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - report the disposable acceptance failure plainly.
        print(f"MOBILE CREDENTIAL FUNCTION ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        if started:
            logs = subprocess.run(
                ["docker", "logs", container],
                text=True,
                capture_output=True,
                check=False,
            )
            if logs.stdout or logs.stderr:
                print("DISPOSABLE POSTGRES LOGS:", file=sys.stderr)
                print(logs.stdout, file=sys.stderr, end="")
                print(logs.stderr, file=sys.stderr, end="")
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
