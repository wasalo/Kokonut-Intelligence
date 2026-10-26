-- Apply tenant-aware operator grant checks to the existing Field Collector
-- draft and lifecycle trigger paths without editing migrations 384/385.
-- Legacy NULL-tenant grants remain accepted by operator_scope_grant_allows.

BEGIN;

CREATE OR REPLACE FUNCTION guard_tenant_scope_field_collector_activity_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actor_id UUID;
BEGIN
    IF NEW.source_system IS DISTINCT FROM 'field_collector'
       OR NEW.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR NEW.source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;

    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;

    IF actor_id IS NULL
       OR NOT operator_scope_grant_allows(
           actor_id, 'farm_activity', 'create_draft', NEW.location_id
       )
       OR NOT operator_scope_grant_allows(
           actor_id, 'mobile_collection_review', 'read_detail', NEW.location_id
       ) THEN
        RAISE EXCEPTION 'Field Collector draft creation requires current tenant-aware grants';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_tenant_scope_field_collector_activity_insert
    ON farm_activity;
CREATE TRIGGER trg_guard_tenant_scope_field_collector_activity_insert
BEFORE INSERT ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_tenant_scope_field_collector_activity_insert();

CREATE OR REPLACE FUNCTION guard_tenant_scope_field_collector_activity_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actor_id UUID;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       OR OLD.source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR OLD.source_raw->>'form_version' IS DISTINCT FROM '1.2.0'
       OR ROW(
           NEW.activity_type, NEW.activity_date, NEW.description,
           NEW.labor_hours, NEW.notes
       ) IS NOT DISTINCT FROM ROW(
           OLD.activity_type, OLD.activity_date, OLD.description,
           OLD.labor_hours, OLD.notes
       ) THEN
        RETURN NEW;
    END IF;

    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;

    IF actor_id IS NULL
       OR NOT operator_scope_grant_allows(
           actor_id, 'farm_activity', 'edit_draft', NEW.location_id
       )
       OR NOT operator_scope_grant_allows(
           actor_id, 'farm_activity', 'read_detail', NEW.location_id
       )
       OR NOT operator_scope_grant_allows(
           actor_id, 'mobile_collection_review', 'read_detail', NEW.location_id
       ) THEN
        RAISE EXCEPTION 'Field Collector draft edit requires current tenant-aware grants';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_tenant_scope_field_collector_activity_update
    ON farm_activity;
CREATE TRIGGER trg_guard_tenant_scope_field_collector_activity_update
BEFORE UPDATE ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_tenant_scope_field_collector_activity_update();

CREATE OR REPLACE FUNCTION guard_tenant_scope_field_collector_workflow_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    source_system TEXT;
    source_raw JSONB;
    grant_action TEXT;
BEGIN
    SELECT activity.source_system, activity.source_raw
      INTO source_system, source_raw
      FROM farm_activity AS activity
     WHERE activity.id = NEW.farm_activity_id;
    IF NOT FOUND
       OR source_system IS DISTINCT FROM 'field_collector'
       OR source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR source_raw->>'form_version' IS DISTINCT FROM '1.2.0' THEN
        RETURN NEW;
    END IF;

    grant_action := CASE NEW.action
        WHEN 'draft_created' THEN 'create_draft'
        WHEN 'draft_edited' THEN 'edit_draft'
        WHEN 'submitted' THEN 'submit'
        WHEN 'verified' THEN 'verify'
        WHEN 'rejected' THEN 'reject'
        WHEN 'rework_requested' THEN 'rework'
        WHEN 'published' THEN 'publish'
        WHEN 'exception_closed' THEN 'close_exception'
        ELSE NULL
    END;

    IF grant_action IS NULL
       OR NOT operator_scope_grant_allows(
           NEW.actor_operator_id, 'farm_activity', grant_action, NEW.location_id
       ) THEN
        RAISE EXCEPTION 'Field Collector workflow event requires a current tenant-aware grant';
    END IF;

    IF NEW.action = 'draft_edited'
       AND (
           NOT operator_scope_grant_allows(
               NEW.actor_operator_id, 'farm_activity', 'read_detail', NEW.location_id
           )
           OR NOT operator_scope_grant_allows(
               NEW.actor_operator_id, 'mobile_collection_review', 'read_detail', NEW.location_id
           )
       ) THEN
        RAISE EXCEPTION 'Field Collector draft edit requires current tenant-aware detail grants';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_tenant_scope_field_collector_workflow_event
    ON farm_activity_workflow_event;
CREATE TRIGGER trg_guard_tenant_scope_field_collector_workflow_event
BEFORE INSERT ON farm_activity_workflow_event
FOR EACH ROW EXECUTE FUNCTION guard_tenant_scope_field_collector_workflow_event();

COMMENT ON FUNCTION guard_tenant_scope_field_collector_activity_insert() IS
    'Rechecks Field Collector draft creation with the shared tenant-aware operator grant predicate.';
COMMENT ON FUNCTION guard_tenant_scope_field_collector_activity_update() IS
    'Rechecks Field Collector draft edits with the shared tenant-aware operator grant predicate.';
COMMENT ON FUNCTION guard_tenant_scope_field_collector_workflow_event() IS
    'Rechecks Field Collector lifecycle and review events with the shared tenant-aware operator grant predicate.';

COMMIT;
