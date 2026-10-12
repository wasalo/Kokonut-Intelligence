-- Append-only, operator-attributed notes for private Field Collector review.
-- These events never alter consent eligibility or the governed lifecycle.

CREATE TABLE mobile_collection_review_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES offline_collection(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    actor_operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (
        decision IN ('reviewed', 'needs_follow_up', 'ineligibility_acknowledged')
    ),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL
        AND CHAR_LENGTH(reason) <= 2000
    ),
    evidence JSONB NOT NULL CHECK (
        jsonb_typeof(evidence) = 'array'
        AND jsonb_array_length(evidence) BETWEEN 1 AND 20
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_mobile_collection_review_event_collection
    ON mobile_collection_review_event (collection_id, created_at DESC, id DESC);
CREATE INDEX idx_mobile_collection_review_event_location
    ON mobile_collection_review_event (location_id, created_at DESC, id DESC);

CREATE FUNCTION guard_mobile_collection_review_event_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    collection_location UUID;
    collection_status TEXT;
    review_required BOOLEAN;
    eligible BOOLEAN;
    evidence_item JSONB;
BEGIN
    IF jsonb_typeof(NEW.evidence) <> 'array'
       OR jsonb_array_length(NEW.evidence) NOT BETWEEN 1 AND 20 THEN
        RAISE EXCEPTION 'mobile collection review evidence must contain 1 to 20 entries';
    END IF;

    FOR evidence_item IN SELECT value FROM jsonb_array_elements(NEW.evidence)
    LOOP
        IF jsonb_typeof(evidence_item) <> 'object'
           OR evidence_item - 'source' - 'basis' <> '{}'::jsonb
           OR NOT (evidence_item ? 'source')
           OR NOT (evidence_item ? 'basis')
           OR COALESCE(jsonb_typeof(evidence_item->'source'), '') <> 'string'
           OR COALESCE(jsonb_typeof(evidence_item->'basis'), '') <> 'string'
           OR NULLIF(BTRIM(evidence_item->>'source'), '') IS NULL
           OR NULLIF(BTRIM(evidence_item->>'basis'), '') IS NULL
           OR CHAR_LENGTH(evidence_item->>'source') > 1000
           OR CHAR_LENGTH(evidence_item->>'basis') > 2000 THEN
            RAISE EXCEPTION 'mobile collection review evidence entry is invalid';
        END IF;
    END LOOP;

    SELECT oc.location_id, oc.sync_status, oc.form_review_required,
           eligibility.eligible_for_use
      INTO collection_location, collection_status, review_required, eligible
      FROM offline_collection AS oc
      JOIN v_mobile_collection_use_eligibility AS eligibility
        ON eligibility.collection_id = oc.id
     WHERE oc.id = NEW.collection_id;

    IF NOT FOUND
       OR collection_location IS DISTINCT FROM NEW.location_id
       OR collection_status <> 'synced'
       OR (NOT review_required AND eligible) THEN
        RAISE EXCEPTION 'mobile collection is not eligible for a review event';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_mobile_collection_review_event_insert
BEFORE INSERT ON mobile_collection_review_event
FOR EACH ROW EXECUTE FUNCTION guard_mobile_collection_review_event_insert();

CREATE FUNCTION protect_mobile_collection_review_event()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'mobile collection review events are append-only';
END;
$$;

CREATE TRIGGER trg_protect_mobile_collection_review_event
BEFORE UPDATE OR DELETE ON mobile_collection_review_event
FOR EACH ROW EXECUTE FUNCTION protect_mobile_collection_review_event();

COMMENT ON TABLE mobile_collection_review_event IS
    'Append-only, location-scoped reviewer notes. Events never mutate collection payload, consent eligibility, or governed lifecycle status.';
