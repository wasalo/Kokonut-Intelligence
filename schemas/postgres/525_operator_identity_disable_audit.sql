-- Record operator identity disable actions without treating caller-supplied
-- attribution as proof of an authenticated human identity.
BEGIN;

CREATE TABLE public.operator_identity_admin_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action = 'identity_disabled'),
    actor_label TEXT NOT NULL
        CHECK (NULLIF(BTRIM(actor_label), '') IS NOT NULL
               AND CHAR_LENGTH(actor_label) <= 200),
    reason TEXT NOT NULL
        CHECK (NULLIF(BTRIM(reason), '') IS NOT NULL
               AND CHAR_LENGTH(reason) <= 2000),
    database_principal TEXT NOT NULL DEFAULT SESSION_USER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_operator_identity_admin_audit_history
    ON public.operator_identity_admin_audit(operator_id, created_at DESC);

COMMENT ON TABLE public.operator_identity_admin_audit IS
    'Private append-only history of local operator identity disable actions. actor_label is caller-supplied attribution, not authenticated identity.';
COMMENT ON COLUMN public.operator_identity_admin_audit.database_principal IS
    'PostgreSQL SESSION_USER that ran the administrative command; this does not establish separation from a privileged or shared login.';

CREATE OR REPLACE FUNCTION public.prevent_operator_identity_admin_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'operator identity administration audit is append-only';
END;
$$;

REVOKE ALL ON FUNCTION public.prevent_operator_identity_admin_audit_mutation()
    FROM PUBLIC;
CREATE TRIGGER trg_operator_identity_admin_audit_append_only
    BEFORE UPDATE OR DELETE ON public.operator_identity_admin_audit
    FOR EACH ROW EXECUTE FUNCTION public.prevent_operator_identity_admin_audit_mutation();
CREATE TRIGGER trg_operator_identity_admin_audit_no_truncate
    BEFORE TRUNCATE ON public.operator_identity_admin_audit
    FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_operator_identity_admin_audit_mutation();

REVOKE ALL ON TABLE public.operator_identity_admin_audit FROM PUBLIC;
DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOR role_name IN
        SELECT rolname FROM pg_roles WHERE left(rolname, 8) = 'kokonut_'
    LOOP
        EXECUTE format(
            'REVOKE ALL ON TABLE public.operator_identity_admin_audit FROM %I',
            role_name
        );
    END LOOP;
END;
$$;

COMMIT;
