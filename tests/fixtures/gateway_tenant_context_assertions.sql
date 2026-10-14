ALTER TABLE public.api_key ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_key FORCE ROW LEVEL SECURITY;
ALTER TABLE public.capability_token ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.capability_token FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;

GRANT SELECT ON public.gateway_context_probe TO kokonut_runtime;
CREATE POLICY gateway_context_probe_scope
    ON public.gateway_context_probe
    FOR SELECT TO kokonut_runtime
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
             WHERE context.tenant_id = gateway_context_probe.tenant_id
               AND context.actor_type IN ('gateway_api_key', 'gateway_capability')
        )
    );
ALTER TABLE public.gateway_context_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gateway_context_probe FORCE ROW LEVEL SECURITY;

SET ROLE kokonut_runtime;
BEGIN;
DO $$
DECLARE
    context_row RECORD;
    row_count INTEGER;
    denied BOOLEAN;
BEGIN
    BEGIN
        INSERT INTO public.api_key (
            id, key_hash, key_prefix, name, is_active
        ) VALUES (
            'a0000000-0000-0000-0000-000000000999', repeat('1', 64), 'forbidden',
            'runtime-write-probe', TRUE
        );
    EXCEPTION WHEN insufficient_privilege THEN
        denied := TRUE;
    END;
    IF denied IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'runtime role inserted an API key';
    END IF;

    SELECT * INTO context_row
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('a', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF NOT FOUND
       OR context_row.tenant_id <> 'a0000000-0000-0000-0000-000000000801'::UUID
       OR context_row.actor_id <> 'a0000000-0000-0000-0000-000000000911'::UUID
       OR context_row.actor_type <> 'gateway_api_key' THEN
        RAISE EXCEPTION 'valid exact API-key scope did not establish expected context';
    END IF;
    SELECT count(*) INTO row_count FROM public.gateway_context_probe;
    IF row_count <> 1
       OR (SELECT value FROM public.gateway_context_probe) <> 'owner-row' THEN
        RAISE EXCEPTION 'forced RLS did not isolate API-key context to its owner';
    END IF;

    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('b', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'location-free API-key scope was accepted'; END IF;
    SELECT count(*) INTO row_count FROM kokonut_security.current_tenant_context();
    IF row_count <> 0 THEN RAISE EXCEPTION 'API-key denial retained prior tenant context'; END IF;

    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('d', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'wildcard API-key scope was accepted'; END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('e', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'expired API key was accepted'; END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('f', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'inactive API key was accepted'; END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'api_key', repeat('9', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'wrong-location API-key scope was accepted'; END IF;

    SELECT * INTO context_row
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('c', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF NOT FOUND
       OR context_row.actor_id <> 'a0000000-0000-0000-0000-000000000921'::UUID
       OR context_row.actor_type <> 'gateway_capability' THEN
        RAISE EXCEPTION 'valid exact capability did not establish expected context';
    END IF;
    SELECT count(*) INTO row_count FROM public.gateway_context_probe;
    IF row_count <> 1 THEN RAISE EXCEPTION 'capability context exposed another tenant'; END IF;

    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('8', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'wrong-location capability was accepted'; END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('7', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'expired capability was accepted'; END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('6', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'revoked capability was accepted'; END IF;
    SELECT * INTO context_row
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('4', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF NOT FOUND OR context_row.actor_type <> 'gateway_capability' THEN
        RAISE EXCEPTION 'final authorized capability use was rejected';
    END IF;
    SELECT count(*) INTO row_count
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('3', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF row_count <> 0 THEN RAISE EXCEPTION 'over-limit capability was accepted'; END IF;
    SELECT * INTO context_row
      FROM kokonut_security.set_gateway_tenant_context(
          'capability_token', repeat('5', 64),
          'a0000000-0000-0000-0000-000000000001'::UUID,
          'mobile_device', 'revoke'
      );
    IF NOT FOUND OR context_row.actor_type <> 'gateway_capability' THEN
        RAISE EXCEPTION 'zero max-usage capability did not retain unlimited semantics';
    END IF;

    PERFORM set_config('kokonut.tenant_id', 'a0000000-0000-0000-0000-000000000801', TRUE);
    PERFORM set_config('kokonut.location_id', 'a0000000-0000-0000-0000-000000000001', TRUE);
    PERFORM set_config('kokonut.actor_type', 'gateway_api_key', TRUE);
    PERFORM set_config('kokonut.context_payload', '{"actor_type":"gateway_api_key"}', TRUE);
    PERFORM set_config('kokonut.context_signature', repeat('0', 64), TRUE);
    SELECT count(*) INTO row_count FROM kokonut_security.current_tenant_context();
    IF row_count <> 0 THEN RAISE EXCEPTION 'forged caller GUC passed the signed accessor'; END IF;
    SELECT count(*) INTO row_count FROM public.gateway_context_probe;
    IF row_count <> 0 THEN RAISE EXCEPTION 'forged caller GUC passed forced RLS'; END IF;
END;
$$;
COMMIT;

BEGIN;
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT count(*) INTO row_count FROM kokonut_security.current_tenant_context();
    IF row_count <> 0 THEN RAISE EXCEPTION 'transaction end did not clear Gateway context'; END IF;
END;
$$;
COMMIT;
RESET ROLE;

DO $$
DECLARE
    duplicate_rejected BOOLEAN := FALSE;
BEGIN
    BEGIN
        INSERT INTO public.api_key (
            id, name, key_hash, key_prefix, scopes, expires_at, is_active
        ) VALUES (
            'a0000000-0000-0000-0000-000000000997', 'duplicate-owner-key',
            repeat('a', 64), 'duplicate',
            ARRAY['mobile_device:revoke:a0000000-0000-0000-0000-000000000001'],
            NOW() + INTERVAL '1 hour', TRUE
        );
    EXCEPTION WHEN unique_violation THEN
        duplicate_rejected := TRUE;
    END;
    IF NOT duplicate_rejected THEN
        RAISE EXCEPTION 'duplicate API-key hash was not rejected by the unique index';
    END IF;
END;
$$;
