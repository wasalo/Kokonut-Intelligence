-- Run after mobile_device_revocation_setup.sql with migration 398 and the
-- runtime-role bootstrap applied in an isolated PostgreSQL database.
BEGIN;
SET LOCAL ROLE kokonut_runtime;

DO $$
DECLARE
    outcome TEXT;
    affected_device TEXT;
    incorrect_owner_count INTEGER;
BEGIN
    IF NOT has_schema_privilege(current_user, 'kokonut_security', 'USAGE') THEN
        RAISE EXCEPTION 'runtime cannot resolve private security functions';
    END IF;

    IF has_column_privilege(current_user, 'public.mobile_device', 'status', 'UPDATE')
       OR has_column_privilege(current_user, 'public.mobile_device', 'device_token_hash', 'UPDATE')
       OR has_column_privilege(current_user, 'public.mobile_device', 'revoked_at', 'UPDATE') THEN
        RAISE EXCEPTION 'runtime retains direct device-revocation column privileges';
    END IF;

    SELECT COUNT(*) INTO incorrect_owner_count
      FROM (VALUES
          ('kokonut_security.resolve_mobile_device_token(text)', 'kokonut_mobile_credential_owner'),
          ('kokonut_security.redeem_mobile_enrollment(text,text,text,text,text,text,text,text)', 'kokonut_mobile_credential_owner'),
          ('kokonut_security.set_mobile_device_context(text,text,uuid)', 'kokonut_mobile_context_owner'),
          ('kokonut_security.current_tenant_context()', 'kokonut_mobile_context_owner'),
          ('kokonut_security.set_operator_tenant_context(text,uuid,uuid,text,text,jsonb)', 'kokonut_operator_context_owner'),
          ('kokonut_security.create_operator_session(text,text,text,text,text,text,timestamptz)', 'kokonut_operator_auth_owner'),
          ('kokonut_security.authenticate_operator_session(text)', 'kokonut_operator_auth_owner'),
          ('kokonut_security.revoke_operator_session(uuid)', 'kokonut_operator_auth_owner'),
          ('kokonut_security.set_gateway_tenant_context(text,text,uuid,text,text)', 'kokonut_gateway_context_owner'),
          ('kokonut_security.revoke_mobile_device(uuid,text,text,text,uuid,text)', 'kokonut_mobile_device_revoke_owner')
      ) AS expected(signature, owner_name)
      JOIN pg_proc AS function_row ON function_row.oid = to_regprocedure(expected.signature)
     WHERE pg_get_userbyid(function_row.proowner) IS DISTINCT FROM expected.owner_name;
    IF incorrect_owner_count <> 0 THEN
        RAISE EXCEPTION 'restored SECURITY DEFINER functions are not bound to least-privilege owners';
    END IF;

    BEGIN
        UPDATE public.mobile_device SET status = 'revoked'
         WHERE device_id = 'codex-revoke-owner';
        RAISE EXCEPTION 'runtime direct device revocation unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;

    SELECT result, device_id INTO outcome, affected_device
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-owner',
          'api_key', repeat('a', 64), NULL, NULL
      );
    IF outcome IS DISTINCT FROM 'revoked' OR affected_device IS DISTINCT FROM 'codex-revoke-owner' THEN
        RAISE EXCEPTION 'valid API-key revoke failed closed';
    END IF;

    SELECT result INTO outcome
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-cross-tenant',
          'api_key', repeat('a', 64), NULL, NULL
      );
    IF outcome IS DISTINCT FROM 'not_found' THEN
        RAISE EXCEPTION 'cross-tenant device was not hidden as not_found';
    END IF;

    SELECT result INTO outcome
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-capability',
          'api_key', repeat('b', 64), NULL, NULL
      );
    IF outcome IS DISTINCT FROM 'denied' THEN
        RAISE EXCEPTION 'wrong-action API key was not denied';
    END IF;

    SELECT result INTO outcome
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-capability',
          'capability_token', repeat('d', 64), NULL, NULL
      );
    IF outcome IS DISTINCT FROM 'revoked' THEN
        RAISE EXCEPTION 'valid capability revoke failed';
    END IF;

    SELECT result INTO outcome
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-operator',
          NULL, NULL, 'e4000000-0000-4000-8000-000000000001', repeat('e', 64)
      );
    IF outcome IS DISTINCT FROM 'revoked' THEN
        RAISE EXCEPTION 'valid operator revoke failed';
    END IF;

    SELECT result INTO outcome
      FROM kokonut_security.revoke_mobile_device(
          'e2000000-0000-4000-8000-000000000001', 'codex-revoke-capability',
          'api_key', repeat('c', 64), NULL, NULL
      );
    IF outcome IS DISTINCT FROM 'denied' THEN
        RAISE EXCEPTION 'wrong-location API key was not denied';
    END IF;
END;
$$;

COMMIT;

BEGIN;
SET LOCAL ROLE kokonut_operator_auth;
DO $$
DECLARE
    authenticated_operator UUID;
BEGIN
    IF NOT has_schema_privilege(current_user, 'kokonut_security', 'USAGE') THEN
        RAISE EXCEPTION 'operator-auth login cannot resolve private session functions';
    END IF;

    SELECT operator_id INTO authenticated_operator
      FROM kokonut_security.authenticate_operator_session(repeat('e', 64));
    IF authenticated_operator IS DISTINCT FROM 'e4000000-0000-4000-8000-000000000001'::UUID THEN
        RAISE EXCEPTION 'operator-auth function grant failed after ACL restore';
    END IF;

    IF has_table_privilege(current_user, 'public.operator_session', 'SELECT')
       OR has_table_privilege(current_user, 'public.operator_identity', 'SELECT') THEN
        RAISE EXCEPTION 'operator-auth login has direct identity or session table access';
    END IF;
END;
$$;
COMMIT;

BEGIN;
SET LOCAL ROLE kokonut_runtime;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM kokonut_security.current_tenant_context()) THEN
        RAISE EXCEPTION 'tenant context persisted after transaction end';
    END IF;
END;
$$;
COMMIT;
