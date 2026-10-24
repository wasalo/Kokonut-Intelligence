-- Synthetic-only post-restore contract for migrations 398–400 and the runtime
-- role bootstrap. Run after the operator and mobile role-boundary fixtures.
ALTER TABLE public.mobile_device ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mobile_device FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_identity FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_session FORCE ROW LEVEL SECURITY;

BEGIN;
SET LOCAL ROLE kokonut_runtime;
DO $$
DECLARE
    incorrect_owner_count INTEGER;
    result_value TEXT;
    device_value TEXT;
BEGIN
    IF NOT has_schema_privilege(current_user, 'kokonut_security', 'USAGE') THEN
        RAISE EXCEPTION 'runtime cannot resolve bounded security functions';
    END IF;
    IF has_column_privilege(current_user, 'public.mobile_device', 'status', 'UPDATE')
       OR has_column_privilege(current_user, 'public.mobile_device', 'device_token_hash', 'UPDATE') THEN
        RAISE EXCEPTION 'runtime retained direct device-revocation privileges';
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
        RAISE EXCEPTION 'restored SECURITY DEFINER functions are not bound to bounded owners';
    END IF;

    SELECT result, device_id INTO result_value, device_value
      FROM kokonut_security.revoke_mobile_device(
          'a0000000-0000-0000-0000-000000000001', 'role-boundary-device',
          'api_key', repeat('c', 64), NULL, NULL
      );
    IF result_value IS DISTINCT FROM 'revoked'
       OR device_value IS DISTINCT FROM 'role-boundary-device' THEN
        RAISE EXCEPTION 'runtime cannot revoke an owner-scoped device under forced RLS';
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
    IF has_table_privilege(current_user, 'public.operator_session', 'SELECT')
       OR has_table_privilege(current_user, 'public.operator_identity', 'SELECT') THEN
        RAISE EXCEPTION 'operator-auth login has direct identity or session table access';
    END IF;
    SELECT operator_id INTO authenticated_operator
      FROM kokonut_security.authenticate_operator_session(repeat('b', 64));
    IF authenticated_operator IS DISTINCT FROM 'a0000000-0000-0000-0000-000000000901'::UUID THEN
        RAISE EXCEPTION 'operator-auth session lookup fails under forced RLS';
    END IF;
END;
$$;
COMMIT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.mobile_device
         WHERE device_id = 'role-boundary-device'
           AND status = 'revoked'
           AND device_token_hash IS NULL
    ) THEN
        RAISE EXCEPTION 'revocation did not clear the synthetic device token';
    END IF;
END;
$$;
