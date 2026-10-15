-- Retention windows are operator policy, not product constants. New or
-- incomplete policies remain inert until an accountable operator approves
-- them explicitly.
ALTER TABLE data_retention_policy
    ALTER COLUMN retention_days DROP NOT NULL,
    ALTER COLUMN retention_days DROP DEFAULT,
    ALTER COLUMN auto_enforce SET DEFAULT FALSE,
    ALTER COLUMN status SET DEFAULT 'draft';

-- Reference categories must not silently choose a legal period. Operators
-- configure actual policy rows only after an accountable review.
ALTER TABLE data_governance_category
    ALTER COLUMN default_retention_days DROP NOT NULL,
    ALTER COLUMN default_retention_days DROP DEFAULT;
UPDATE data_governance_category SET default_retention_days = NULL;

ALTER TABLE consent_data_type
    ALTER COLUMN default_retention_days DROP DEFAULT;
UPDATE consent_data_type SET default_retention_days = NULL;

ALTER TABLE data_retention_policy
    ADD CONSTRAINT data_retention_policy_positive_window
    CHECK (retention_days IS NULL OR retention_days > 0) NOT VALID;

-- Legacy policies without explicit approval metadata must be reviewed again;
-- do not infer that their historical default window was intentional.
UPDATE data_retention_policy
SET status = 'draft', auto_enforce = FALSE,
    retention_days = CASE WHEN retention_days <= 0 THEN NULL ELSE retention_days END,
    updated_at = NOW()
WHERE approved_by IS NULL
   OR length(btrim(approved_by)) = 0
   OR approval_date IS NULL
   OR policy_owner IS NULL
   OR length(btrim(policy_owner)) = 0
   OR retention_days IS NULL
   OR retention_days <= 0;

CREATE TABLE IF NOT EXISTS data_retention_policy_event (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id       UUID NOT NULL REFERENCES data_retention_policy(id),
    action          VARCHAR(32) NOT NULL
        CHECK (action IN ('draft_created', 'approved', 'retired', 'migration_review_required')),
    actor           VARCHAR(200) NOT NULL CHECK (length(btrim(actor)) > 0),
    reason          TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    policy_snapshot JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_retention_policy_event_history
    ON data_retention_policy_event (policy_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION prevent_data_retention_policy_event_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'retention policy history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_data_retention_policy_event_immutable
    ON data_retention_policy_event;
CREATE TRIGGER trg_data_retention_policy_event_immutable
    BEFORE UPDATE OR DELETE ON data_retention_policy_event
    FOR EACH ROW EXECUTE FUNCTION prevent_data_retention_policy_event_mutation();

INSERT INTO data_retention_policy_event
    (policy_id, action, actor, reason, policy_snapshot)
SELECT id,
       'migration_review_required',
       'migration:401',
       'Policy was made inert because its approval or positive window was not explicit.',
       jsonb_build_object(
           'data_category', data_category,
           'entity_type', entity_type,
           'location_id', location_id,
           'retention_days', retention_days,
           'deletion_method', deletion_method,
           'auto_enforce', auto_enforce,
           'approved_by', approved_by,
           'approval_date', approval_date,
           'status', status
       )
FROM data_retention_policy
WHERE status = 'draft'
  AND (approved_by IS NULL OR length(btrim(approved_by)) = 0
       OR approval_date IS NULL OR policy_owner IS NULL
       OR length(btrim(policy_owner)) = 0 OR retention_days IS NULL);

CREATE TABLE IF NOT EXISTS data_retention_legal_hold (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(100) NOT NULL
        CHECK (entity_type ~ '^[a-z_]+$'),
    entity_id       UUID NOT NULL,
    reason          TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    placed_by       VARCHAR(200) NOT NULL CHECK (length(btrim(placed_by)) > 0),
    placed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_by     VARCHAR(200),
    released_at     TIMESTAMPTZ,
    release_reason  TEXT,
    CHECK (
        (released_at IS NULL AND released_by IS NULL AND release_reason IS NULL)
        OR
        (released_at IS NOT NULL
         AND released_by IS NOT NULL AND length(btrim(released_by)) > 0
         AND release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_data_retention_active_hold_entity
    ON data_retention_legal_hold (entity_type, entity_id)
    WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_data_retention_hold_entity_history
    ON data_retention_legal_hold (entity_type, entity_id, placed_at DESC);

CREATE TABLE IF NOT EXISTS data_retention_legal_hold_event (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hold_id     UUID NOT NULL REFERENCES data_retention_legal_hold(id),
    action      VARCHAR(10) NOT NULL CHECK (action IN ('placed', 'released')),
    actor       VARCHAR(200) NOT NULL CHECK (length(btrim(actor)) > 0),
    reason      TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_retention_hold_event_history
    ON data_retention_legal_hold_event (hold_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION audit_data_retention_legal_hold()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'retention legal holds cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO data_retention_legal_hold_event
            (hold_id, action, actor, reason, occurred_at)
        VALUES (NEW.id, 'placed', NEW.placed_by, NEW.reason, NEW.placed_at);
        RETURN NEW;
    END IF;

    IF OLD.released_at IS NOT NULL
       OR NEW.released_at IS NULL
       OR NEW.id IS DISTINCT FROM OLD.id
       OR NEW.entity_type IS DISTINCT FROM OLD.entity_type
       OR NEW.entity_id IS DISTINCT FROM OLD.entity_id
       OR NEW.reason IS DISTINCT FROM OLD.reason
       OR NEW.placed_by IS DISTINCT FROM OLD.placed_by
       OR NEW.placed_at IS DISTINCT FROM OLD.placed_at
       OR NEW.released_by IS NULL
       OR length(btrim(NEW.released_by)) = 0
       OR NEW.release_reason IS NULL
       OR length(btrim(NEW.release_reason)) = 0 THEN
        RAISE EXCEPTION 'retention legal holds may only be released once with actor and reason';
    END IF;

    INSERT INTO data_retention_legal_hold_event
        (hold_id, action, actor, reason, occurred_at)
    VALUES (NEW.id, 'released', NEW.released_by, NEW.release_reason, NEW.released_at);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_data_retention_legal_hold_audit
    ON data_retention_legal_hold;
CREATE TRIGGER trg_data_retention_legal_hold_audit
    AFTER INSERT OR UPDATE OR DELETE ON data_retention_legal_hold
    FOR EACH ROW EXECUTE FUNCTION audit_data_retention_legal_hold();

CREATE OR REPLACE FUNCTION prevent_data_retention_hold_event_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'retention legal hold history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_data_retention_hold_event_immutable
    ON data_retention_legal_hold_event;
CREATE TRIGGER trg_data_retention_hold_event_immutable
    BEFORE UPDATE OR DELETE ON data_retention_legal_hold_event
    FOR EACH ROW EXECUTE FUNCTION prevent_data_retention_hold_event_mutation();
