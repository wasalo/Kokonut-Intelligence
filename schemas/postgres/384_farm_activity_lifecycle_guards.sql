-- Enforce the native Field Collector farm-activity lifecycle at the database
-- boundary and write each transition to the operator-attributed event ledger.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM farm_activity AS activity
         WHERE activity.source_system = 'field_collector'
           AND activity.source_raw->>'form_id' = 'farm_activity_v1'
           AND activity.source_raw->>'form_version' = '1.2.0'
           AND (
               NOT EXISTS (
                   SELECT 1
                     FROM farm_activity_workflow_event AS event
                    WHERE event.farm_activity_id = activity.id
                      AND event.location_id = activity.location_id
                      AND event.source_collection_id::text = activity.source_id
                      AND event.action = 'draft_created'
                      AND event.from_status IS NULL
                      AND event.to_status = 'draft'
               )
               OR NOT EXISTS (
                   SELECT 1
                     FROM farm_activity_workflow_event AS event
                    WHERE event.farm_activity_id = activity.id
                      AND event.location_id = activity.location_id
                      AND event.source_collection_id::text = activity.source_id
                      AND event.to_status = activity.status::text
               )
           )
    ) THEN
        RAISE EXCEPTION 'Field Collector farm activities require source and current-status workflow evidence before lifecycle guards can be enabled';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION guard_farm_activity_workflow_event_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    activity_location UUID;
    activity_status TEXT;
    activity_source_system TEXT;
    activity_source_id TEXT;
    activity_source_raw JSONB;
    activity_payload_digest TEXT;
    collection_location UUID;
    configured_actor UUID;
    configured_action TEXT;
    grant_action TEXT;
    active_operator UUID;
    active_grant UUID;
    prior_actor UUID;
    submitted_actor UUID;
    verified_actor UUID;
BEGIN
    SELECT location_id, status::text, source_system, source_id, source_raw
      INTO activity_location, activity_status, activity_source_system, activity_source_id,
           activity_source_raw
      FROM farm_activity
     WHERE id = NEW.farm_activity_id;
    IF NOT FOUND
       OR activity_location IS DISTINCT FROM NEW.location_id
       OR activity_status IS DISTINCT FROM NEW.to_status
       OR activity_source_system IS DISTINCT FROM 'field_collector'
       OR activity_source_id IS DISTINCT FROM NEW.source_collection_id::text
       OR activity_source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR activity_source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RAISE EXCEPTION 'farm activity workflow event does not match its canonical record';
    END IF;

    BEGIN
        configured_actor := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        configured_actor := NULL;
    END;
    configured_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    IF current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR configured_actor IS DISTINCT FROM NEW.actor_operator_id
       OR configured_action IS DISTINCT FROM NEW.action THEN
        RAISE EXCEPTION 'farm activity workflow event requires the matching native operator action';
    END IF;

    grant_action := CASE NEW.action
        WHEN 'draft_created' THEN 'create_draft'
        WHEN 'submitted' THEN 'submit'
        WHEN 'verified' THEN 'verify'
        WHEN 'rejected' THEN 'reject'
        WHEN 'rework_requested' THEN 'rework'
        WHEN 'published' THEN 'publish'
        WHEN 'exception_closed' THEN 'close_exception'
        ELSE NULL
    END;
    SELECT identity.id
      INTO active_operator
      FROM operator_identity AS identity
     WHERE identity.id = NEW.actor_operator_id
       AND identity.enabled = TRUE
     FOR SHARE;
    IF active_operator IS NULL THEN
        RAISE EXCEPTION 'farm activity workflow event requires an enabled operator with a current location grant';
    END IF;
    SELECT grant_row.id
      INTO active_grant
      FROM operator_scope_grant AS grant_row
     WHERE grant_row.operator_id = NEW.actor_operator_id
       AND grant_row.resource = 'farm_activity'
       AND grant_row.action = grant_action
       AND grant_row.location_id = NEW.location_id
       AND grant_row.revoked_at IS NULL
     FOR SHARE;
    IF active_grant IS NULL THEN
        RAISE EXCEPTION 'farm activity workflow event requires an enabled operator with a current location grant';
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
    ELSIF NEW.action = 'verified' THEN
        SELECT actor_operator_id
          INTO prior_actor
          FROM farm_activity_workflow_event
         WHERE farm_activity_id = NEW.farm_activity_id
           AND action = 'submitted'
         ORDER BY created_at DESC, id DESC
         LIMIT 1;
        IF prior_actor IS NULL OR prior_actor = NEW.actor_operator_id THEN
            RAISE EXCEPTION 'farm activity verifier must differ from the latest submitter';
        END IF;
    ELSIF NEW.action = 'rejected' THEN
        IF NEW.from_status = 'submitted' THEN
            SELECT actor_operator_id
              INTO prior_actor
              FROM farm_activity_workflow_event
             WHERE farm_activity_id = NEW.farm_activity_id
               AND action = 'submitted'
             ORDER BY created_at DESC, id DESC
             LIMIT 1;
            IF prior_actor IS NULL OR prior_actor = NEW.actor_operator_id THEN
                RAISE EXCEPTION 'farm activity reviewer must differ from the latest submitter';
            END IF;
        ELSE
            SELECT actor_operator_id
              INTO verified_actor
              FROM farm_activity_workflow_event
             WHERE farm_activity_id = NEW.farm_activity_id
               AND action = 'verified'
             ORDER BY created_at DESC, id DESC
             LIMIT 1;
            SELECT actor_operator_id
              INTO submitted_actor
              FROM farm_activity_workflow_event
             WHERE farm_activity_id = NEW.farm_activity_id
               AND action = 'submitted'
             ORDER BY created_at DESC, id DESC
             LIMIT 1;
            IF verified_actor IS NULL OR submitted_actor IS NULL
               OR NEW.actor_operator_id IN (verified_actor, submitted_actor) THEN
                RAISE EXCEPTION 'farm activity reviewer must differ from the latest submitter and verifier';
            END IF;
        END IF;
    ELSIF NEW.action = 'published' THEN
        SELECT actor_operator_id
          INTO submitted_actor
          FROM farm_activity_workflow_event
         WHERE farm_activity_id = NEW.farm_activity_id
           AND action = 'submitted'
         ORDER BY created_at DESC, id DESC
         LIMIT 1;
        SELECT actor_operator_id
          INTO verified_actor
          FROM farm_activity_workflow_event
         WHERE farm_activity_id = NEW.farm_activity_id
           AND action = 'verified'
         ORDER BY created_at DESC, id DESC
         LIMIT 1;
        IF submitted_actor IS NULL OR verified_actor IS NULL
           OR NEW.actor_operator_id IN (submitted_actor, verified_actor) THEN
            RAISE EXCEPTION 'farm activity publisher must differ from the latest submitter and verifier';
        END IF;
    END IF;

    SELECT location_id
      INTO collection_location
      FROM offline_collection
     WHERE id = NEW.source_collection_id;
    IF NOT FOUND OR collection_location IS DISTINCT FROM NEW.location_id THEN
        RAISE EXCEPTION 'farm activity workflow event source is outside its location';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION guard_farm_activity_field_collector_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    source_collection UUID;
    source_location UUID;
    source_form_id TEXT;
    source_form_version TEXT;
    source_collection_type TEXT;
    source_sync_status TEXT;
    source_validation_status TEXT;
    source_consent_status TEXT;
    source_review_required BOOLEAN;
    revision_status TEXT;
    revision_consent_policy TEXT;
    eligible BOOLEAN;
    actor_id UUID;
    payload_digest TEXT;
    create_draft_grant UUID;
    review_detail_grant UUID;
BEGIN
    IF NEW.source_system IS DISTINCT FROM 'field_collector'
       OR NEW.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR NEW.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;
    IF NEW.status::text IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Field Collector farm activities must be created as drafts';
    END IF;
    IF current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR current_setting('kokonut.workflow_action', TRUE) IS DISTINCT FROM 'draft_created'
       OR current_setting('kokonut.content_reviewed', TRUE) IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'Field Collector draft creation requires an explicit reviewed operator action';
    END IF;
    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
        source_collection := NEW.source_id::UUID;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Field Collector draft requires valid operator and collection identifiers';
    END;
    payload_digest := NEW.source_raw->>'payload_sha256';
    IF actor_id IS NULL
       OR NEW.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR NEW.source_raw->>'form_version' IS DISTINCT FROM '1.2.0'
       OR NEW.source_raw->>'offline_collection_id' IS DISTINCT FROM source_collection::text
       OR payload_digest IS NULL
       OR payload_digest !~ '^[0-9a-f]{64}$'
       OR current_setting('kokonut.payload_sha256', TRUE) IS DISTINCT FROM payload_digest THEN
        RAISE EXCEPTION 'Field Collector draft lineage or review digest is invalid';
    END IF;

    SELECT oc.location_id, oc.form_id, oc.form_version, oc.collection_type,
           oc.sync_status, oc.form_validation_status, oc.consent_validation_status,
           oc.form_review_required, revision.status, revision.consent_policy_status,
           eligibility.eligible_for_use
      INTO source_location, source_form_id, source_form_version,
           source_collection_type, source_sync_status, source_validation_status,
           source_consent_status, source_review_required, revision_status,
           revision_consent_policy, eligible
      FROM offline_collection AS oc
      JOIN mobile_form_version AS revision ON revision.id = oc.form_revision_id
      JOIN v_mobile_collection_use_eligibility AS eligibility
        ON eligibility.collection_id = oc.id
     WHERE oc.id = source_collection
     FOR SHARE OF oc, revision;
    IF NOT FOUND
       OR source_location IS DISTINCT FROM NEW.location_id
       OR source_form_id IS DISTINCT FROM 'farm_activity_v1'
       OR source_form_version IS DISTINCT FROM '1.2.0'
       OR source_collection_type IS DISTINCT FROM 'farm_activity'
       OR source_sync_status IS DISTINCT FROM 'synced'
       OR source_validation_status IS DISTINCT FROM 'active'
       OR source_consent_status IS DISTINCT FROM 'not_required'
       OR source_review_required IS DISTINCT FROM FALSE
       OR revision_status IS DISTINCT FROM 'active'
       OR revision_consent_policy IS DISTINCT FROM 'not_required'
       OR eligible IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Field Collector source is not currently eligible for draft promotion';
    END IF;

    SELECT id
      INTO create_draft_grant
      FROM operator_scope_grant
     WHERE operator_id = actor_id
       AND resource = 'farm_activity' AND action = 'create_draft'
       AND location_id = NEW.location_id AND revoked_at IS NULL
     FOR SHARE;
    SELECT id
      INTO review_detail_grant
      FROM operator_scope_grant
     WHERE operator_id = actor_id
       AND resource = 'mobile_collection_review' AND action = 'read_detail'
       AND location_id = NEW.location_id AND revoked_at IS NULL
     FOR SHARE;
    IF create_draft_grant IS NULL OR review_detail_grant IS NULL THEN
        RAISE EXCEPTION 'Field Collector draft creation requires current location-scoped grants';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_field_collector_insert
BEFORE INSERT ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_field_collector_insert();

CREATE FUNCTION guard_farm_activity_field_collector_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       AND NEW.source_system IS DISTINCT FROM 'field_collector' THEN
        RETURN NEW;
    END IF;
    IF NOT (
        OLD.source_raw->>'form_id' = 'farm_activity_v1'
        AND OLD.source_raw->>'form_version' = '1.2.0'
    ) AND NOT (
        NEW.source_raw->>'form_id' = 'farm_activity_v1'
        AND NEW.source_raw->>'form_version' = '1.2.0'
    ) THEN
        RETURN NEW;
    END IF;
    IF OLD.source_system IS DISTINCT FROM NEW.source_system
       OR OLD.location_id IS DISTINCT FROM NEW.location_id
       OR OLD.source_id IS DISTINCT FROM NEW.source_id
       OR OLD.source_raw IS DISTINCT FROM NEW.source_raw
       OR OLD.schema_version IS DISTINCT FROM NEW.schema_version THEN
        RAISE EXCEPTION 'Field Collector farm activity source identity is immutable';
    END IF;
    IF OLD.status::text <> 'draft'
       AND ROW(
           NEW.plot_id, NEW.crop_cycle_id, NEW.activity_type, NEW.activity_date,
           NEW.description, NEW.labor_hours, NEW.labor_cost, NEW.materials_used,
           NEW.evidence_urls, NEW.evidence_hashes, NEW.notes
       ) IS DISTINCT FROM ROW(
           OLD.plot_id, OLD.crop_cycle_id, OLD.activity_type, OLD.activity_date,
           OLD.description, OLD.labor_hours, OLD.labor_cost, OLD.materials_used,
           OLD.evidence_urls, OLD.evidence_hashes, OLD.notes
       ) THEN
        RAISE EXCEPTION 'Submitted or published Field Collector farm activity content is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_field_collector_update
BEFORE UPDATE ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_field_collector_update();

CREATE FUNCTION guard_farm_activity_workflow_status_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    workflow_action TEXT;
    workflow_reason TEXT;
    actor_id UUID;
    actor_type TEXT;
    from_status TEXT;
    to_status TEXT;
    content_changed BOOLEAN;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       OR OLD.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR OLD.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;
    workflow_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    workflow_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    actor_type := NULLIF(current_setting('kokonut.actor_type', TRUE), '');
    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;
    IF workflow_action IS NULL OR actor_id IS NULL OR actor_type IS DISTINCT FROM 'operator' THEN
        RAISE EXCEPTION 'Field Collector lifecycle transitions require a native human operator action';
    END IF;
    from_status := OLD.status::text;
    to_status := NEW.status::text;
    content_changed := ROW(
        NEW.plot_id, NEW.crop_cycle_id, NEW.activity_type, NEW.activity_date,
        NEW.description, NEW.labor_hours, NEW.labor_cost, NEW.materials_used,
        NEW.evidence_urls, NEW.evidence_hashes, NEW.notes
    ) IS DISTINCT FROM ROW(
        OLD.plot_id, OLD.crop_cycle_id, OLD.activity_type, OLD.activity_date,
        OLD.description, OLD.labor_hours, OLD.labor_cost, OLD.materials_used,
        OLD.evidence_urls, OLD.evidence_hashes, OLD.notes
    );
    IF content_changed THEN
        RAISE EXCEPTION 'Save draft content separately before changing lifecycle state';
    END IF;

    IF workflow_action = 'submitted' AND from_status = 'draft' AND to_status = 'submitted' THEN
        RETURN NEW;
    ELSIF workflow_action = 'verified' AND from_status = 'submitted' AND to_status = 'verified' THEN
        RETURN NEW;
    ELSIF workflow_action = 'rejected' AND from_status IN ('submitted', 'verified') AND to_status = 'rejected' THEN
        IF workflow_reason IS NULL THEN RAISE EXCEPTION 'Rejection requires a reason'; END IF;
        RETURN NEW;
    ELSIF workflow_action = 'rework_requested' AND from_status = 'rejected' AND to_status = 'draft' THEN
        IF workflow_reason IS NULL THEN RAISE EXCEPTION 'Rework requires a reason'; END IF;
        RETURN NEW;
    ELSIF workflow_action = 'published' AND from_status = 'verified' AND to_status = 'published' THEN
        RETURN NEW;
    ELSIF workflow_action = 'exception_closed' AND from_status = 'rejected' AND to_status = 'rejected' THEN
        IF workflow_reason IS NULL THEN RAISE EXCEPTION 'Exception closure requires a reason'; END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invalid Field Collector farm activity lifecycle transition';
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_workflow_status_update
BEFORE UPDATE OF status ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_workflow_status_update();

CREATE FUNCTION record_farm_activity_workflow_transition()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    workflow_action TEXT;
    workflow_reason TEXT;
    actor_id UUID;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       OR OLD.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR OLD.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;
    workflow_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    workflow_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    INSERT INTO farm_activity_workflow_event (
        farm_activity_id, location_id, source_collection_id,
        actor_operator_id, action, from_status, to_status, reason, metadata
    ) VALUES (
        NEW.id, NEW.location_id, NEW.source_id::UUID,
        actor_id, workflow_action, OLD.status::text, NEW.status::text,
        workflow_reason, jsonb_build_object('route', 'native_gateway')
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_farm_activity_workflow_transition
AFTER UPDATE OF status ON farm_activity
FOR EACH ROW EXECUTE FUNCTION record_farm_activity_workflow_transition();

CREATE FUNCTION require_farm_activity_workflow_event()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.source_system IS DISTINCT FROM 'field_collector'
       OR NEW.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR NEW.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM farm_activity_workflow_event
         WHERE farm_activity_id = NEW.id
           AND location_id = NEW.location_id
           AND source_collection_id::text = NEW.source_id
           AND action = 'draft_created'
           AND from_status IS NULL
           AND to_status = 'draft'
    ) THEN
        RAISE EXCEPTION 'Field Collector farm activity creation requires draft workflow evidence';
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_require_farm_activity_workflow_event
AFTER INSERT ON farm_activity
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION require_farm_activity_workflow_event();

COMMENT ON FUNCTION guard_farm_activity_workflow_status_update() IS
    'Requires explicit OIDC operator action and legal transition shape for Field Collector farm activity status changes.';
COMMENT ON FUNCTION record_farm_activity_workflow_transition() IS
    'Writes the append-only operator event atomically after a guarded Field Collector status update.';
COMMENT ON FUNCTION require_farm_activity_workflow_event() IS
    'Deferred commit guard ensures every Field Collector draft insert has a matching review event; status updates append evidence synchronously.';
