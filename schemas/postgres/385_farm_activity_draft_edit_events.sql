-- Add an operator-reviewed, append-only path for correcting native farm-activity drafts.

ALTER TABLE farm_activity_workflow_event
    DROP CONSTRAINT farm_activity_workflow_event_action_check,
    DROP CONSTRAINT chk_farm_activity_workflow_event_reason,
    DROP CONSTRAINT chk_farm_activity_workflow_event_transition;

ALTER TABLE farm_activity_workflow_event
    ADD CONSTRAINT farm_activity_workflow_event_action_check CHECK (
        action IN (
            'draft_created', 'draft_edited', 'submitted', 'verified', 'published',
            'rejected', 'rework_requested', 'exception_closed'
        )
    ),
    ADD CONSTRAINT chk_farm_activity_workflow_event_reason CHECK (
        action NOT IN ('draft_edited', 'rejected', 'rework_requested', 'exception_closed')
        OR NULLIF(BTRIM(reason), '') IS NOT NULL
    ),
    ADD CONSTRAINT chk_farm_activity_workflow_event_transition CHECK (
        (action = 'draft_created' AND from_status IS NULL AND to_status = 'draft')
        OR (action = 'draft_edited' AND from_status = 'draft' AND to_status = 'draft')
        OR (action = 'submitted' AND from_status = 'draft' AND to_status = 'submitted')
        OR (action = 'verified' AND from_status = 'submitted' AND to_status = 'verified')
        OR (action = 'published' AND from_status = 'verified' AND to_status = 'published')
        OR (action = 'rejected' AND from_status IN ('submitted', 'verified') AND to_status = 'rejected')
        OR (action = 'rework_requested' AND from_status = 'rejected' AND to_status = 'draft')
        OR (action = 'exception_closed' AND from_status = 'rejected' AND to_status = 'rejected')
    );

-- Keep the migration-384 validation function intact for all existing actions;
-- route draft_edited events through a separate guarded branch.
DROP TRIGGER trg_guard_farm_activity_workflow_event_insert ON farm_activity_workflow_event;

CREATE TRIGGER trg_guard_farm_activity_workflow_event_insert
BEFORE INSERT ON farm_activity_workflow_event
FOR EACH ROW
WHEN (NEW.action <> 'draft_edited')
EXECUTE FUNCTION guard_farm_activity_workflow_event_insert();

CREATE FUNCTION guard_farm_activity_draft_edit_event_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    activity_location UUID;
    activity_status TEXT;
    activity_source_system TEXT;
    activity_source_id TEXT;
    activity_source_raw JSONB;
    activity_date_value DATE;
    activity_type_value TEXT;
    description_value TEXT;
    labor_hours_value NUMERIC;
    notes_value TEXT;
    expected_digest TEXT;
    collection_location UUID;
    configured_actor UUID;
    configured_action TEXT;
    active_operator UUID;
    active_grant UUID;
BEGIN
    SELECT location_id, status::text, source_system, source_id, source_raw,
           activity_date, activity_type, description, labor_hours, notes
      INTO activity_location, activity_status, activity_source_system,
           activity_source_id, activity_source_raw, activity_date_value,
           activity_type_value, description_value, labor_hours_value, notes_value
      FROM farm_activity
     WHERE id = NEW.farm_activity_id;
    IF NOT FOUND
       OR activity_location IS DISTINCT FROM NEW.location_id
       OR activity_status IS DISTINCT FROM 'draft'
       OR activity_source_system IS DISTINCT FROM 'field_collector'
       OR activity_source_id IS DISTINCT FROM NEW.source_collection_id::text
       OR activity_source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR activity_source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RAISE EXCEPTION 'farm activity draft-edit event does not match its native draft';
    END IF;

    BEGIN
        configured_actor := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        configured_actor := NULL;
    END;
    configured_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    IF current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR configured_actor IS DISTINCT FROM NEW.actor_operator_id
       OR configured_action IS DISTINCT FROM 'draft_edited' THEN
        RAISE EXCEPTION 'farm activity draft edit requires the matching native operator action';
    END IF;

    SELECT identity.id
      INTO active_operator
      FROM operator_identity AS identity
     WHERE identity.id = NEW.actor_operator_id
       AND identity.enabled = TRUE
     FOR SHARE;
    SELECT grant_row.id
      INTO active_grant
      FROM operator_scope_grant AS grant_row
     WHERE grant_row.operator_id = NEW.actor_operator_id
       AND grant_row.resource = 'farm_activity'
       AND grant_row.action = 'edit_draft'
       AND grant_row.location_id = NEW.location_id
       AND grant_row.revoked_at IS NULL
     FOR SHARE;
    IF active_operator IS NULL OR active_grant IS NULL THEN
        RAISE EXCEPTION 'farm activity draft edit requires an enabled operator with a current location grant';
    END IF;

    IF jsonb_typeof(NEW.metadata->'changed_fields') IS DISTINCT FROM 'array'
       OR jsonb_array_length(NEW.metadata->'changed_fields') = 0
       OR EXISTS (
           SELECT 1
             FROM jsonb_array_elements_text(NEW.metadata->'changed_fields') AS fields(field_name)
            WHERE field_name IS NULL
               OR field_name NOT IN ('activity_type', 'activity_date', 'description', 'labor_hours', 'notes')
       ) THEN
        RAISE EXCEPTION 'farm activity draft edit event requires an allowlisted changed-field list';
    END IF;

    expected_digest := encode(
        digest(
            convert_to(jsonb_build_object(
                'activity_type', activity_type_value,
                'activity_date', to_char(activity_date_value, 'YYYY-MM-DD'),
                'description', description_value,
                'labor_hours', labor_hours_value,
                'notes', notes_value
            )::text, 'UTF8'),
            'sha256'
        ),
        'hex'
    );
    IF NEW.metadata->>'content_sha256' IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'farm activity draft edit event digest does not match canonical content';
    END IF;

    SELECT location_id INTO collection_location
      FROM offline_collection
     WHERE id = NEW.source_collection_id;
    IF NOT FOUND OR collection_location IS DISTINCT FROM NEW.location_id THEN
        RAISE EXCEPTION 'farm activity draft edit source is outside its location';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_draft_edit_event_insert
BEFORE INSERT ON farm_activity_workflow_event
FOR EACH ROW
WHEN (NEW.action = 'draft_edited')
EXECUTE FUNCTION guard_farm_activity_draft_edit_event_insert();

CREATE FUNCTION guard_farm_activity_native_draft_edit()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    actor_id UUID;
    current_action TEXT;
    current_reason TEXT;
    active_operator UUID;
    required_grant_count INTEGER;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       OR OLD.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR OLD.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;
    IF OLD.status::text IS DISTINCT FROM 'draft'
       OR NEW.status::text IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Only native farm activity drafts may be edited';
    END IF;

    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;
    current_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    current_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    IF current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR actor_id IS NULL
       OR current_action IS DISTINCT FROM 'draft_edited'
       OR NULLIF(BTRIM(current_reason), '') IS NULL
       OR CHAR_LENGTH(current_reason) > 2000 THEN
        RAISE EXCEPTION 'Native farm activity draft edit requires an attributed operator, action, and reason';
    END IF;

    NEW.updated_at := NOW();
    IF (to_jsonb(NEW) - ARRAY[
            'activity_type', 'activity_date', 'description', 'labor_hours', 'notes', 'updated_at'
        ]) IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY[
            'activity_type', 'activity_date', 'description', 'labor_hours', 'notes', 'updated_at'
        ]) THEN
        RAISE EXCEPTION 'Native farm activity draft edit may change only fields declared by its form revision';
    END IF;
    IF ROW(NEW.activity_type, NEW.activity_date, NEW.description, NEW.labor_hours, NEW.notes)
       IS NOT DISTINCT FROM
       ROW(OLD.activity_type, OLD.activity_date, OLD.description, OLD.labor_hours, OLD.notes) THEN
        RAISE EXCEPTION 'Native farm activity draft edit must change at least one content field';
    END IF;

    SELECT identity.id
      INTO active_operator
      FROM operator_identity AS identity
     WHERE identity.id = actor_id
       AND identity.enabled = TRUE
     FOR SHARE;
    PERFORM 1
      FROM operator_scope_grant AS grant_row
     WHERE grant_row.operator_id = actor_id
       AND grant_row.location_id = NEW.location_id
       AND grant_row.revoked_at IS NULL
       AND (
           (grant_row.resource = 'farm_activity' AND grant_row.action IN ('edit_draft', 'read_detail'))
           OR (grant_row.resource = 'mobile_collection_review' AND grant_row.action = 'read_detail')
       )
     FOR SHARE;
    SELECT COUNT(DISTINCT ROW(grant_row.resource, grant_row.action))
      INTO required_grant_count
      FROM operator_scope_grant AS grant_row
     WHERE grant_row.operator_id = actor_id
       AND grant_row.location_id = NEW.location_id
       AND grant_row.revoked_at IS NULL
       AND (
           (grant_row.resource = 'farm_activity' AND grant_row.action IN ('edit_draft', 'read_detail'))
           OR (grant_row.resource = 'mobile_collection_review' AND grant_row.action = 'read_detail')
       );
    IF active_operator IS NULL OR required_grant_count < 3 THEN
        RAISE EXCEPTION 'Native farm activity draft edit requires current edit and private detail grants';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_native_draft_edit
BEFORE UPDATE OF activity_type, activity_date, description, labor_hours, notes
ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_native_draft_edit();

CREATE FUNCTION record_farm_activity_native_draft_edit()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    actor_id UUID;
    changed_fields TEXT[];
    content_digest TEXT;
    edit_reason TEXT;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       OR OLD.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR OLD.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;

    actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    edit_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    changed_fields := ARRAY_REMOVE(ARRAY[
        CASE WHEN NEW.activity_type IS DISTINCT FROM OLD.activity_type THEN 'activity_type' END,
        CASE WHEN NEW.activity_date IS DISTINCT FROM OLD.activity_date THEN 'activity_date' END,
        CASE WHEN NEW.description IS DISTINCT FROM OLD.description THEN 'description' END,
        CASE WHEN NEW.labor_hours IS DISTINCT FROM OLD.labor_hours THEN 'labor_hours' END,
        CASE WHEN NEW.notes IS DISTINCT FROM OLD.notes THEN 'notes' END
    ]::TEXT[], NULL);
    content_digest := encode(
        digest(
            convert_to(jsonb_build_object(
                'activity_type', NEW.activity_type,
                'activity_date', to_char(NEW.activity_date, 'YYYY-MM-DD'),
                'description', NEW.description,
                'labor_hours', NEW.labor_hours,
                'notes', NEW.notes
            )::text, 'UTF8'),
            'sha256'
        ),
        'hex'
    );

    INSERT INTO farm_activity_workflow_event (
        farm_activity_id, location_id, source_collection_id,
        actor_operator_id, action, from_status, to_status, reason, metadata
    ) VALUES (
        NEW.id, NEW.location_id, NEW.source_id::UUID, actor_id,
        'draft_edited', 'draft', 'draft', edit_reason,
        jsonb_build_object(
            'route', 'native_gateway',
            'changed_fields', to_jsonb(changed_fields),
            'content_sha256', content_digest
        )
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_farm_activity_native_draft_edit
AFTER UPDATE OF activity_type, activity_date, description, labor_hours, notes
ON farm_activity
FOR EACH ROW EXECUTE FUNCTION record_farm_activity_native_draft_edit();

COMMENT ON FUNCTION guard_farm_activity_native_draft_edit() IS
    'Requires an enabled location-scoped operator and explicit edit grant before native farm-activity draft content changes.';
COMMENT ON FUNCTION record_farm_activity_native_draft_edit() IS
    'Appends a reasoned, allowlisted, content-digest workflow event atomically with each native draft edit.';
