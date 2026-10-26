-- Idempotent Field Collector promotion and operator-attributed workflow evidence.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM farm_activity
         WHERE source_system = 'field_collector'
           AND source_id IS NOT NULL
         GROUP BY source_system, source_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate Field Collector farm_activity source identities require review';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_farm_activity_field_collector_source
    ON farm_activity (source_system, source_id)
    WHERE source_system = 'field_collector' AND source_id IS NOT NULL;

CREATE TABLE farm_activity_workflow_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_activity_id UUID NOT NULL REFERENCES farm_activity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    source_collection_id UUID NOT NULL,
    actor_operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (
        action IN (
            'draft_created', 'submitted', 'verified', 'published',
            'rejected', 'rework_requested', 'exception_closed'
        )
    ),
    from_status TEXT CHECK (
        from_status IS NULL OR from_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
    ),
    to_status TEXT NOT NULL CHECK (
        to_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
    ),
    reason TEXT CHECK (reason IS NULL OR CHAR_LENGTH(reason) <= 2000),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_farm_activity_workflow_event_reason CHECK (
        action NOT IN ('rejected', 'rework_requested', 'exception_closed')
        OR NULLIF(BTRIM(reason), '') IS NOT NULL
    ),
    CONSTRAINT chk_farm_activity_workflow_event_transition CHECK (
        (action = 'draft_created' AND from_status IS NULL AND to_status = 'draft')
        OR (action = 'submitted' AND from_status = 'draft' AND to_status = 'submitted')
        OR (action = 'verified' AND from_status = 'submitted' AND to_status = 'verified')
        OR (action = 'published' AND from_status = 'verified' AND to_status = 'published')
        OR (action = 'rejected' AND from_status IN ('submitted', 'verified') AND to_status = 'rejected')
        OR (action = 'rework_requested' AND from_status = 'rejected' AND to_status = 'draft')
        OR (action = 'exception_closed' AND from_status = 'rejected' AND to_status = 'rejected')
    )
);

CREATE INDEX idx_farm_activity_workflow_event_activity
    ON farm_activity_workflow_event (farm_activity_id, created_at, id);
CREATE INDEX idx_farm_activity_workflow_event_collection
    ON farm_activity_workflow_event (source_collection_id, action);

CREATE FUNCTION guard_farm_activity_workflow_event_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    activity_location UUID;
    activity_status TEXT;
    activity_source_system TEXT;
    activity_source_id TEXT;
    activity_payload_digest TEXT;
    collection_location UUID;
BEGIN
    SELECT location_id, status, source_system, source_id
      INTO activity_location, activity_status, activity_source_system, activity_source_id
      FROM farm_activity
     WHERE id = NEW.farm_activity_id;
    IF NOT FOUND
       OR activity_location IS DISTINCT FROM NEW.location_id
       OR activity_status IS DISTINCT FROM NEW.to_status
       OR activity_source_system IS DISTINCT FROM 'field_collector'
       OR activity_source_id IS DISTINCT FROM NEW.source_collection_id::text THEN
        RAISE EXCEPTION 'farm activity workflow event does not match its canonical record';
    END IF;

    IF NEW.action = 'draft_created' THEN
        SELECT source_raw->>'payload_sha256'
          INTO activity_payload_digest
          FROM farm_activity
         WHERE id = NEW.farm_activity_id;
        IF COALESCE((NEW.metadata->>'content_reviewed')::boolean, FALSE) IS NOT TRUE
           OR activity_payload_digest IS NULL
           OR NEW.metadata->>'payload_sha256' IS DISTINCT FROM activity_payload_digest THEN
            RAISE EXCEPTION 'farm activity draft creation requires a matching content review record';
        END IF;
    END IF;

    SELECT location_id INTO collection_location
      FROM offline_collection
     WHERE id = NEW.source_collection_id;
    IF NOT FOUND OR collection_location IS DISTINCT FROM NEW.location_id THEN
        RAISE EXCEPTION 'farm activity workflow event source is outside its location';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_workflow_event_insert
BEFORE INSERT ON farm_activity_workflow_event
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_workflow_event_insert();

CREATE FUNCTION protect_farm_activity_workflow_event()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'farm activity workflow events are append-only';
END;
$$;

CREATE TRIGGER trg_protect_farm_activity_workflow_event
BEFORE UPDATE OR DELETE ON farm_activity_workflow_event
FOR EACH ROW EXECUTE FUNCTION protect_farm_activity_workflow_event();

COMMENT ON TABLE farm_activity_workflow_event IS
    'Append-only operator actions for Field Collector farm activity promotion and governed lifecycle transitions.';
COMMENT ON COLUMN farm_activity_workflow_event.source_collection_id IS
    'Stable provenance UUID from offline_collection; no foreign key so later retention disposition can be handled explicitly.';
