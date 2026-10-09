-- P2 data-governance workflow controls.

ALTER TABLE data_portability_request
    ADD COLUMN IF NOT EXISTS authorization_ref TEXT,
    ADD COLUMN IF NOT EXISTS fulfilled_by VARCHAR(200),
    ADD COLUMN IF NOT EXISTS fulfillment_authorization_ref TEXT;

CREATE TABLE IF NOT EXISTS data_retention_enforcement_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id   UUID NOT NULL REFERENCES data_retention_policy(id),
    actor       VARCHAR(200) NOT NULL,
    dry_run     BOOLEAN NOT NULL DEFAULT FALSE,
    status      VARCHAR(20) NOT NULL CHECK (status IN ('skipped', 'dry_run', 'completed', 'error')),
    candidates  INTEGER NOT NULL DEFAULT 0 CHECK (candidates >= 0),
    affected    INTEGER NOT NULL DEFAULT 0 CHECK (affected >= 0),
    error       TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drel_policy_time
    ON data_retention_enforcement_log (policy_id, executed_at DESC);

-- Access logs and sharing agreements are evidence, not mutable state.
CREATE OR REPLACE FUNCTION prevent_data_access_log_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'data_access_log is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_data_access_log_immutable ON data_access_log;
CREATE TRIGGER trg_data_access_log_immutable
    BEFORE UPDATE OR DELETE ON data_access_log
    FOR EACH ROW EXECUTE FUNCTION prevent_data_access_log_mutation();

CREATE TABLE IF NOT EXISTS data_sharing_agreement_audit (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agreement_id UUID NOT NULL,
    operation    VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by   VARCHAR(200),
    old_record   JSONB,
    new_record   JSONB,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dsaa_agreement_time
    ON data_sharing_agreement_audit (agreement_id, changed_at DESC);

CREATE OR REPLACE FUNCTION audit_data_sharing_agreement()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO data_sharing_agreement_audit
        (agreement_id, operation, changed_by, old_record, new_record)
    VALUES (
        COALESCE(NEW.id, OLD.id), TG_OP, current_setting('app.actor_id', TRUE),
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END
    );
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_data_sharing_agreement_audit ON data_sharing_agreement;
CREATE TRIGGER trg_data_sharing_agreement_audit
    AFTER INSERT OR UPDATE OR DELETE ON data_sharing_agreement
    FOR EACH ROW EXECUTE FUNCTION audit_data_sharing_agreement();
