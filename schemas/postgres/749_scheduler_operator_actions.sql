-- Authenticated, auditable scheduler schedule-definition administration.
-- The executor identity from migration 748 remains unable to call this path.
BEGIN;

ALTER TABLE kokonut_security.operator_global_capability
    DROP CONSTRAINT operator_global_capability_capability_code_check,
    ADD CONSTRAINT operator_global_capability_capability_code_check CHECK (
        capability_code IN (
            'clickhouse_outbox:read',
            'clickhouse_outbox:replay',
            'clickhouse_outbox:resolve',
            'clickhouse_outbox:discard',
            'scheduler:read',
            'scheduler:enable',
            'scheduler:disable'
        )
    );
ALTER TABLE kokonut_security.operator_global_capability_audit
    DROP CONSTRAINT operator_global_capability_audit_capability_code_check,
    ADD CONSTRAINT operator_global_capability_audit_capability_code_check CHECK (
        capability_code IN (
            'clickhouse_outbox:read',
            'clickhouse_outbox:replay',
            'clickhouse_outbox:resolve',
            'clickhouse_outbox:discard',
            'scheduler:read',
            'scheduler:enable',
            'scheduler:disable'
        )
    );

CREATE OR REPLACE FUNCTION kokonut_security.operator_global_capability_allows(
    requested_session_token_hash TEXT,
    requested_capability_code TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
BEGIN
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable'
    ) THEN
        RETURN FALSE;
    END IF;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
    RETURN EXISTS (
        SELECT 1
          FROM kokonut_security.operator_global_capability AS capability
         WHERE capability.operator_id = resolved_operator_id
           AND capability.capability_code = requested_capability_code
           AND capability.revoked_at IS NULL
    );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.grant_operator_global_capability(
    requested_operator_id UUID,
    requested_capability_code TEXT,
    requested_approved_by TEXT,
    requested_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    granted_id UUID;
BEGIN
    IF session_user IN ('kokonut_runtime', 'kokonut_operator_auth', 'kokonut_clickhouse_outbox_operator_login') THEN
        RAISE EXCEPTION 'DBA-approved capability provisioning is required' USING ERRCODE = '42501';
    END IF;
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable'
    ) OR btrim(coalesce(requested_approved_by, '')) = '' OR btrim(coalesce(requested_reason, '')) = '' THEN
        RAISE EXCEPTION 'capability, approver, and reason are required' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM public.operator_identity
         WHERE id = requested_operator_id
           AND enabled
    ) THEN
        RAISE EXCEPTION 'enabled operator identity is required' USING ERRCODE = '22023';
    END IF;
    INSERT INTO kokonut_security.operator_global_capability (
        operator_id, capability_code, granted_by_db_role, approved_by, grant_reason
    ) VALUES (
        requested_operator_id,
        requested_capability_code,
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    )
    RETURNING id INTO granted_id;
    INSERT INTO kokonut_security.operator_global_capability_audit (
        capability_id, operator_id, capability_code, action, actor_db_role, approved_by, reason
    ) VALUES (
        granted_id,
        requested_operator_id,
        requested_capability_code,
        'granted',
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    );
    RETURN granted_id;
END;
$$;

GRANT SELECT ON public.scheduled_task TO kokonut_operator_capability_owner;

CREATE TABLE kokonut_security.scheduler_operator_audit (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    scheduled_task_id UUID NOT NULL,
    task_name TEXT NOT NULL CHECK (length(btrim(task_name)) BETWEEN 1 AND 100),
    action TEXT NOT NULL CHECK (action IN ('enabled', 'disabled')),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
ALTER TABLE kokonut_security.scheduler_operator_audit OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON TABLE kokonut_security.scheduler_operator_audit FROM PUBLIC;
ALTER TABLE kokonut_security.scheduler_operator_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.scheduler_operator_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY scheduler_operator_audit_owner_all
    ON kokonut_security.scheduler_operator_audit
    FOR ALL TO kokonut_operator_capability_owner
    USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION kokonut_security.audit_scheduler_operator_action(
    requested_session_token_hash TEXT,
    requested_task_id UUID,
    requested_action TEXT,
    requested_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
    required_capability TEXT;
    task_record RECORD;
    audit_id UUID;
BEGIN
    IF session_user <> 'kokonut_runtime' THEN
        RAISE EXCEPTION 'Kernel runtime identity required for scheduler operator audit' USING ERRCODE = '42501';
    END IF;
    IF requested_action NOT IN ('enable', 'disable')
       OR btrim(coalesce(requested_reason, '')) = ''
       OR length(btrim(requested_reason)) > 2000
       OR requested_session_token_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'scheduler action, session, and reason are required' USING ERRCODE = '22023';
    END IF;
    required_capability := 'scheduler:' || requested_action;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
    IF NOT EXISTS (
        SELECT 1
          FROM kokonut_security.operator_global_capability AS capability
         WHERE capability.operator_id = resolved_operator_id
           AND capability.capability_code = required_capability
           AND capability.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'scheduler operator capability required' USING ERRCODE = '42501';
    END IF;
    SELECT id, name, is_enabled
      INTO task_record
      FROM public.scheduled_task
     WHERE id = requested_task_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'scheduled task not found' USING ERRCODE = 'P0002';
    END IF;
    IF task_record.is_enabled IS DISTINCT FROM (requested_action = 'enable') THEN
        RAISE EXCEPTION 'scheduled task state does not match audited action' USING ERRCODE = '42501';
    END IF;
    INSERT INTO kokonut_security.scheduler_operator_audit (
        operator_id, scheduled_task_id, task_name, action, reason
    ) VALUES (
        resolved_operator_id,
        task_record.id,
        task_record.name,
        CASE requested_action WHEN 'enable' THEN 'enabled' ELSE 'disabled' END,
        btrim(requested_reason)
    )
    RETURNING id INTO audit_id;
    RETURN audit_id;
END;
$$;
COMMENT ON TABLE kokonut_security.scheduler_operator_audit IS
    'Evidence for authenticated scheduler enable/disable actions; reason and operator are captured with each state change.';
ALTER FUNCTION kokonut_security.audit_scheduler_operator_action(TEXT, UUID, TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.audit_scheduler_operator_action(TEXT, UUID, TEXT, TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.audit_scheduler_operator_action(TEXT, UUID, TEXT, TEXT)
    TO kokonut_runtime;

COMMIT;
