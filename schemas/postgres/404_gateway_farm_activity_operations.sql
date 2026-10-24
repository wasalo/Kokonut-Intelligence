-- Add a first-party operational path for non-Field-Collector farm activities.
-- Native Field Collector records remain governed by their separate consent-aware
-- workflow and audit ledger.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_farm_activity_event_owner'
    ) THEN
        CREATE ROLE kokonut_farm_activity_event_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_farm_activity_event_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'farm activity event function owner has unsafe role attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_farm_activity_event_owner'
            OR member_role.rolname = 'kokonut_farm_activity_event_owner'
    ) THEN
        RAISE EXCEPTION 'farm activity event function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO kokonut_farm_activity_event_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_farm_activity_event_owner;
REVOKE CREATE ON SCHEMA public FROM kokonut_farm_activity_event_owner;
-- PostgreSQL requires the new owner to have schema CREATE during ALTER
-- FUNCTION OWNER. Grant it only for this migration transaction, then revoke.
GRANT CREATE ON SCHEMA public TO kokonut_farm_activity_event_owner;

CREATE TABLE farm_activity_operator_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_activity_id UUID NOT NULL REFERENCES farm_activity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    actor_operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (
        action IN (
            'draft_created', 'draft_edited', 'submitted', 'verified', 'published',
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
    CONSTRAINT chk_farm_activity_operator_event_reason CHECK (
        action NOT IN ('draft_edited', 'rejected', 'rework_requested', 'exception_closed')
        OR NULLIF(BTRIM(reason), '') IS NOT NULL
    ),
    CONSTRAINT chk_farm_activity_operator_event_transition CHECK (
        (action = 'draft_created' AND from_status IS NULL AND to_status = 'draft')
        OR (action = 'draft_edited' AND from_status = 'draft' AND to_status = 'draft')
        OR (action = 'submitted' AND from_status = 'draft' AND to_status = 'submitted')
        OR (action = 'verified' AND from_status = 'submitted' AND to_status = 'verified')
        OR (action = 'published' AND from_status = 'verified' AND to_status = 'published')
        OR (action = 'rejected' AND from_status IN ('submitted', 'verified') AND to_status = 'rejected')
        OR (action = 'rework_requested' AND from_status = 'rejected' AND to_status = 'draft')
        OR (action = 'exception_closed' AND from_status = 'rejected' AND to_status = 'rejected')
    )
);

CREATE INDEX idx_farm_activity_operator_event_activity
    ON farm_activity_operator_event (farm_activity_id, created_at, id);

REVOKE ALL ON TABLE public.farm_activity_operator_event FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.farm_activity_operator_event
    TO kokonut_farm_activity_event_owner;
GRANT SELECT ON TABLE public.farm_activity, public.location,
    public.operator_identity TO kokonut_farm_activity_event_owner;
GRANT SELECT ON TABLE public.operator_scope_grant, public.operator_organization_membership,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization TO kokonut_farm_activity_event_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_farm_activity_event_owner;

CREATE FUNCTION guard_farm_activity_operator_event_insert()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    activity_location UUID;
    activity_status TEXT;
    activity_source_system TEXT;
    configured_actor UUID;
    configured_action TEXT;
    grant_action TEXT;
    active_operator UUID;
    context_actor UUID;
    context_location UUID;
    context_actor_type TEXT;
    prior_actor UUID;
    submitted_actor UUID;
    verified_actor UUID;
BEGIN
    SELECT location_id, status::text, source_system
      INTO activity_location, activity_status, activity_source_system
      FROM farm_activity
     WHERE id = NEW.farm_activity_id;
    IF NOT FOUND
       OR activity_location IS DISTINCT FROM NEW.location_id
       OR activity_status IS DISTINCT FROM NEW.to_status
       OR activity_source_system IS NOT DISTINCT FROM 'field_collector' THEN
        RAISE EXCEPTION 'farm activity operator event does not match an eligible canonical record';
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
        RAISE EXCEPTION 'farm activity operator event requires its matching authenticated operator action';
    END IF;
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_actor, context_location, context_actor_type
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_actor IS DISTINCT FROM NEW.actor_operator_id
       OR context_location IS DISTINCT FROM NEW.location_id
       OR context_actor_type IS DISTINCT FROM 'operator' THEN
        RAISE EXCEPTION 'farm activity operator event requires a signed tenant context for its actor and location';
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
    SELECT identity.id
      INTO active_operator
      FROM operator_identity AS identity
     WHERE identity.id = NEW.actor_operator_id
       AND identity.enabled = TRUE;
    IF active_operator IS NULL
       OR grant_action IS NULL
       OR NOT public.operator_scope_grant_allows(
           NEW.actor_operator_id, 'farm_activity', grant_action, NEW.location_id
       ) THEN
        RAISE EXCEPTION 'farm activity operator event requires an enabled operator with a current tenant grant';
    END IF;

    IF NEW.action = 'draft_edited' THEN
        IF NEW.from_status IS DISTINCT FROM 'draft'
           OR NEW.to_status IS DISTINCT FROM 'draft'
           OR jsonb_typeof(NEW.metadata->'changed_fields') IS DISTINCT FROM 'array'
           OR jsonb_array_length(NEW.metadata->'changed_fields') = 0 THEN
            RAISE EXCEPTION 'farm activity draft edit event requires changed fields';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM jsonb_array_elements_text(NEW.metadata->'changed_fields') AS changed(field_name)
             WHERE changed.field_name IS NULL
                OR changed.field_name = ''
                OR changed.field_name NOT IN (
                 'plot_id', 'crop_cycle_id', 'activity_type', 'activity_date',
                 'description', 'labor_hours', 'labor_cost', 'materials_used',
                 'evidence_urls', 'notes'
             )
        ) THEN
            RAISE EXCEPTION 'farm activity draft edit event contains a protected field';
        END IF;
        IF NOT public.operator_scope_grant_allows(
            NEW.actor_operator_id, 'farm_activity', 'read_detail', NEW.location_id
        ) THEN
            RAISE EXCEPTION 'farm activity draft edit event requires a current detail grant';
        END IF;
    ELSIF NEW.action = 'verified' THEN
        SELECT actor_operator_id INTO prior_actor
          FROM farm_activity_operator_event
         WHERE farm_activity_id = NEW.farm_activity_id AND action = 'submitted'
         ORDER BY created_at DESC, id DESC LIMIT 1;
        IF prior_actor IS NULL OR prior_actor = NEW.actor_operator_id THEN
            RAISE EXCEPTION 'farm activity verifier must differ from the latest submitter';
        END IF;
    ELSIF NEW.action = 'rejected' THEN
        IF NEW.from_status = 'submitted' THEN
            SELECT actor_operator_id INTO prior_actor
              FROM farm_activity_operator_event
             WHERE farm_activity_id = NEW.farm_activity_id AND action = 'submitted'
             ORDER BY created_at DESC, id DESC LIMIT 1;
            IF prior_actor IS NULL OR prior_actor = NEW.actor_operator_id THEN
                RAISE EXCEPTION 'farm activity reviewer must differ from the latest submitter';
            END IF;
        ELSE
            SELECT actor_operator_id INTO verified_actor
              FROM farm_activity_operator_event
             WHERE farm_activity_id = NEW.farm_activity_id AND action = 'verified'
             ORDER BY created_at DESC, id DESC LIMIT 1;
            SELECT actor_operator_id INTO submitted_actor
              FROM farm_activity_operator_event
             WHERE farm_activity_id = NEW.farm_activity_id AND action = 'submitted'
             ORDER BY created_at DESC, id DESC LIMIT 1;
            IF verified_actor IS NULL OR submitted_actor IS NULL
               OR NEW.actor_operator_id IN (verified_actor, submitted_actor) THEN
                RAISE EXCEPTION 'farm activity reviewer must differ from the latest submitter and verifier';
            END IF;
        END IF;
    ELSIF NEW.action = 'published' THEN
        SELECT actor_operator_id INTO submitted_actor
          FROM farm_activity_operator_event
         WHERE farm_activity_id = NEW.farm_activity_id AND action = 'submitted'
         ORDER BY created_at DESC, id DESC LIMIT 1;
        SELECT actor_operator_id INTO verified_actor
          FROM farm_activity_operator_event
         WHERE farm_activity_id = NEW.farm_activity_id AND action = 'verified'
         ORDER BY created_at DESC, id DESC LIMIT 1;
        IF submitted_actor IS NULL OR verified_actor IS NULL
           OR NEW.actor_operator_id IN (submitted_actor, verified_actor) THEN
            RAISE EXCEPTION 'farm activity publisher must differ from the latest submitter and verifier';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_operator_event_insert
BEFORE INSERT ON farm_activity_operator_event
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_operator_event_insert();

ALTER FUNCTION guard_farm_activity_operator_event_insert()
    OWNER TO kokonut_farm_activity_event_owner;
REVOKE ALL ON FUNCTION guard_farm_activity_operator_event_insert() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION guard_farm_activity_operator_event_insert()
    TO kokonut_farm_activity_event_owner;

CREATE FUNCTION protect_farm_activity_operator_event()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'farm activity operator events are append-only';
END;
$$;

CREATE TRIGGER trg_protect_farm_activity_operator_event
BEFORE UPDATE OR DELETE ON farm_activity_operator_event
FOR EACH ROW EXECUTE FUNCTION protect_farm_activity_operator_event();

CREATE FUNCTION guard_gateway_farm_activity_insert()
RETURNS TRIGGER LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
DECLARE
    actor_id UUID;
    context_actor UUID;
    context_location UUID;
    context_actor_type TEXT;
BEGIN
    IF NEW.source_system IS DISTINCT FROM 'kokonut_gateway' THEN
        RETURN NEW;
    END IF;
    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;
    IF NEW.status::text IS DISTINCT FROM 'draft'
       OR NEW.schema_version IS DISTINCT FROM 'gateway_v1'
       OR NEW.source_id IS NOT NULL
       OR NEW.source_raw IS NOT NULL
       OR current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR actor_id IS NULL
       OR current_setting('kokonut.workflow_action', TRUE) IS DISTINCT FROM 'draft_created'
       OR NOT public.operator_scope_grant_allows(
           actor_id, 'farm_activity', 'create_draft', NEW.location_id
       ) THEN
        RAISE EXCEPTION 'Gateway farm activity creation requires an attributed draft and current tenant grant';
    END IF;
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_actor, context_location, context_actor_type
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_actor IS DISTINCT FROM actor_id
       OR context_location IS DISTINCT FROM NEW.location_id
       OR context_actor_type IS DISTINCT FROM 'operator' THEN
        RAISE EXCEPTION 'Gateway farm activity creation requires a signed operator tenant context';
    END IF;
    IF NEW.plot_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM plot AS parent
          JOIN farm ON farm.id = parent.farm_id
         WHERE parent.id = NEW.plot_id AND farm.location_id = NEW.location_id
    ) THEN
        RAISE EXCEPTION 'farm activity plot must belong to its location';
    END IF;
    IF NEW.crop_cycle_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM crop_cycle AS parent WHERE parent.id = NEW.crop_cycle_id AND parent.location_id = NEW.location_id
    ) THEN
        RAISE EXCEPTION 'farm activity crop cycle must belong to its location';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_gateway_farm_activity_insert
BEFORE INSERT ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_gateway_farm_activity_insert();

CREATE FUNCTION record_gateway_farm_activity_create()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    actor_id UUID;
BEGIN
    IF NEW.source_system IS DISTINCT FROM 'kokonut_gateway' THEN
        RETURN NEW;
    END IF;
    actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    INSERT INTO farm_activity_operator_event (
        farm_activity_id, location_id, actor_operator_id, action,
        from_status, to_status, metadata
    ) VALUES (
        NEW.id, NEW.location_id, actor_id, 'draft_created', NULL, 'draft',
        jsonb_build_object('route', 'gateway_farm_activity_records')
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_gateway_farm_activity_create
AFTER INSERT ON farm_activity
FOR EACH ROW EXECUTE FUNCTION record_gateway_farm_activity_create();

ALTER FUNCTION record_gateway_farm_activity_create()
    OWNER TO kokonut_farm_activity_event_owner;
REVOKE ALL ON FUNCTION record_gateway_farm_activity_create() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION record_gateway_farm_activity_create()
    TO kokonut_farm_activity_event_owner;

CREATE FUNCTION guard_farm_activity_gateway_operation()
RETURNS TRIGGER LANGUAGE plpgsql
SET search_path = pg_catalog, public AS $$
DECLARE
    actor_id UUID;
    workflow_action TEXT;
    workflow_reason TEXT;
    grant_action TEXT;
    content_changed BOOLEAN;
    status_changed BOOLEAN;
    changed_fields JSONB;
    from_status TEXT;
    to_status TEXT;
    context_actor UUID;
    context_location UUID;
    context_actor_type TEXT;
BEGIN
    IF OLD.source_system IS NOT DISTINCT FROM 'field_collector' THEN
        IF NEW.source_system IS DISTINCT FROM OLD.source_system
           OR NEW.source_id IS DISTINCT FROM OLD.source_id
           OR NEW.source_raw IS DISTINCT FROM OLD.source_raw
           OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
           OR NEW.location_id IS DISTINCT FROM OLD.location_id THEN
            RAISE EXCEPTION 'Field Collector source and tenant identity are immutable';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.source_system IS DISTINCT FROM OLD.source_system
       OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.source_raw IS DISTINCT FROM OLD.source_raw
       OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
       OR NEW.location_id IS DISTINCT FROM OLD.location_id THEN
        RAISE EXCEPTION 'farm activity source and tenant identity are immutable through Gateway operations';
    END IF;

    IF (to_jsonb(NEW) - ARRAY[
            'plot_id', 'crop_cycle_id', 'activity_type', 'activity_date', 'description',
            'labor_hours', 'labor_cost', 'materials_used', 'evidence_urls', 'notes',
            'status', 'verified_by', 'verified_at', 'rejection_reason', 'updated_at', 'updated_by'
        ]) IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY[
            'plot_id', 'crop_cycle_id', 'activity_type', 'activity_date', 'description',
            'labor_hours', 'labor_cost', 'materials_used', 'evidence_urls', 'notes',
            'status', 'verified_by', 'verified_at', 'rejection_reason', 'updated_at', 'updated_by'
        ]) THEN
        RAISE EXCEPTION 'farm activity Gateway operation changed a protected field';
    END IF;

    content_changed := ROW(
        NEW.plot_id, NEW.crop_cycle_id, NEW.activity_type, NEW.activity_date,
        NEW.description, NEW.labor_hours, NEW.labor_cost, NEW.materials_used,
        NEW.evidence_urls, NEW.notes
    ) IS DISTINCT FROM ROW(
        OLD.plot_id, OLD.crop_cycle_id, OLD.activity_type, OLD.activity_date,
        OLD.description, OLD.labor_hours, OLD.labor_cost, OLD.materials_used,
        OLD.evidence_urls, OLD.notes
    );
    status_changed := NEW.status IS DISTINCT FROM OLD.status;
    workflow_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    IF NOT content_changed AND NOT status_changed
       AND ROW(NEW.verified_by, NEW.verified_at, NEW.rejection_reason)
           IS NOT DISTINCT FROM ROW(OLD.verified_by, OLD.verified_at, OLD.rejection_reason)
       AND workflow_action IS DISTINCT FROM 'exception_closed' THEN
        IF NEW.updated_at IS DISTINCT FROM OLD.updated_at
           OR NEW.updated_by IS DISTINCT FROM OLD.updated_by THEN
            RAISE EXCEPTION 'farm activity timestamps and editor identity are managed by Gateway';
        END IF;
        RETURN NEW;
    END IF;

    BEGIN
        actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    EXCEPTION WHEN OTHERS THEN
        actor_id := NULL;
    END;
    workflow_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    IF actor_id IS NULL OR current_setting('kokonut.actor_type', TRUE) IS DISTINCT FROM 'operator'
       OR workflow_action IS NULL THEN
        RAISE EXCEPTION 'farm activity changes require an attributed Gateway operator action';
    END IF;
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_actor, context_location, context_actor_type
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_actor IS DISTINCT FROM actor_id
       OR context_location IS DISTINCT FROM NEW.location_id
       OR context_actor_type IS DISTINCT FROM 'operator' THEN
        RAISE EXCEPTION 'farm activity operation requires a signed operator tenant context';
    END IF;

    from_status := OLD.status::text;
    to_status := NEW.status::text;
    IF workflow_action = 'draft_edited' THEN
        IF OLD.status::text IS DISTINCT FROM 'draft'
           OR NEW.status::text IS DISTINCT FROM 'draft'
           OR NOT content_changed OR status_changed
           OR NULLIF(BTRIM(workflow_reason), '') IS NULL
           OR CHAR_LENGTH(workflow_reason) > 2000
           OR ROW(NEW.verified_by, NEW.verified_at, NEW.rejection_reason)
                IS DISTINCT FROM ROW(OLD.verified_by, OLD.verified_at, OLD.rejection_reason) THEN
            RAISE EXCEPTION 'only attributed draft content edits with a reason are permitted';
        END IF;
        grant_action := 'edit_draft';
        IF NOT public.operator_scope_grant_allows(actor_id, 'farm_activity', 'read_detail', NEW.location_id) THEN
            RAISE EXCEPTION 'farm activity draft edit requires a current detail grant';
        END IF;
    ELSE
        IF content_changed THEN
            RAISE EXCEPTION 'save farm activity draft content separately from lifecycle decisions';
        END IF;
        grant_action := CASE workflow_action
            WHEN 'submitted' THEN 'submit'
            WHEN 'verified' THEN 'verify'
            WHEN 'rejected' THEN 'reject'
            WHEN 'rework_requested' THEN 'rework'
            WHEN 'published' THEN 'publish'
            WHEN 'exception_closed' THEN 'close_exception'
            ELSE NULL
        END;
        IF grant_action IS NULL THEN
            RAISE EXCEPTION 'unsupported farm activity operator action';
        END IF;
        IF workflow_action = 'submitted' AND NOT (from_status = 'draft' AND to_status = 'submitted')
           OR workflow_action = 'verified' AND NOT (from_status = 'submitted' AND to_status = 'verified')
           OR workflow_action = 'rejected' AND NOT (from_status IN ('submitted', 'verified') AND to_status = 'rejected')
           OR workflow_action = 'rework_requested' AND NOT (from_status = 'rejected' AND to_status = 'draft')
           OR workflow_action = 'published' AND NOT (from_status = 'verified' AND to_status = 'published')
           OR workflow_action = 'exception_closed' AND NOT (from_status = 'rejected' AND to_status = 'rejected') THEN
            RAISE EXCEPTION 'invalid farm activity lifecycle transition';
        END IF;
        IF workflow_action IN ('rejected', 'rework_requested', 'exception_closed')
           AND (NULLIF(BTRIM(workflow_reason), '') IS NULL OR CHAR_LENGTH(workflow_reason) > 2000) THEN
            RAISE EXCEPTION 'this farm activity decision requires a bounded reason';
        END IF;
    END IF;

    IF NOT public.operator_scope_grant_allows(actor_id, 'farm_activity', grant_action, NEW.location_id) THEN
        RAISE EXCEPTION 'farm activity operation requires a current tenant-qualified grant';
    END IF;
    IF NEW.plot_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM plot AS parent
          JOIN farm ON farm.id = parent.farm_id
         WHERE parent.id = NEW.plot_id AND farm.location_id = NEW.location_id
    ) THEN
        RAISE EXCEPTION 'farm activity plot must belong to its location';
    END IF;
    IF NEW.crop_cycle_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM crop_cycle AS parent WHERE parent.id = NEW.crop_cycle_id AND parent.location_id = NEW.location_id
    ) THEN
        RAISE EXCEPTION 'farm activity crop cycle must belong to its location';
    END IF;

    NEW.updated_at := NOW();
    NEW.updated_by := actor_id;
    IF workflow_action = 'verified' THEN
        NEW.verified_by := actor_id;
        NEW.verified_at := NOW();
    ELSIF workflow_action = 'rejected' THEN
        NEW.rejection_reason := workflow_reason;
    END IF;

    IF workflow_action IN ('submitted', 'published', 'exception_closed')
       AND ROW(NEW.verified_by, NEW.verified_at, NEW.rejection_reason)
           IS DISTINCT FROM ROW(OLD.verified_by, OLD.verified_at, OLD.rejection_reason)
       OR workflow_action = 'verified'
          AND NEW.rejection_reason IS DISTINCT FROM OLD.rejection_reason
       OR workflow_action = 'rejected'
          AND ROW(NEW.verified_by, NEW.verified_at)
              IS DISTINCT FROM ROW(OLD.verified_by, OLD.verified_at)
       OR workflow_action = 'rework_requested'
          AND ROW(NEW.verified_by, NEW.verified_at, NEW.rejection_reason)
              IS DISTINCT FROM ROW(OLD.verified_by, OLD.verified_at, OLD.rejection_reason) THEN
        RAISE EXCEPTION 'farm activity decision changed fields outside its lifecycle action';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_gateway_operation
BEFORE UPDATE ON farm_activity
FOR EACH ROW EXECUTE FUNCTION guard_farm_activity_gateway_operation();

CREATE FUNCTION record_farm_activity_gateway_operation()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    workflow_action TEXT;
    workflow_reason TEXT;
    actor_id UUID;
    changed_fields JSONB;
BEGIN
    workflow_action := NULLIF(current_setting('kokonut.workflow_action', TRUE), '');
    IF NEW.source_system IS NOT DISTINCT FROM 'field_collector'
       OR (ROW(
           NEW.plot_id, NEW.crop_cycle_id, NEW.activity_type, NEW.activity_date,
           NEW.description, NEW.labor_hours, NEW.labor_cost, NEW.materials_used,
           NEW.evidence_urls, NEW.notes, NEW.status, NEW.verified_by,
           NEW.verified_at, NEW.rejection_reason
       ) IS NOT DISTINCT FROM ROW(
           OLD.plot_id, OLD.crop_cycle_id, OLD.activity_type, OLD.activity_date,
           OLD.description, OLD.labor_hours, OLD.labor_cost, OLD.materials_used,
           OLD.evidence_urls, OLD.notes, OLD.status, OLD.verified_by,
           OLD.verified_at, OLD.rejection_reason
       ) AND workflow_action IS DISTINCT FROM 'exception_closed') THEN
        RETURN NEW;
    END IF;
    workflow_reason := NULLIF(current_setting('kokonut.workflow_reason', TRUE), '');
    actor_id := NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID;
    IF workflow_action = 'draft_edited' THEN
        changed_fields := to_jsonb(array_remove(ARRAY[
            CASE WHEN NEW.plot_id IS DISTINCT FROM OLD.plot_id THEN 'plot_id' END,
            CASE WHEN NEW.crop_cycle_id IS DISTINCT FROM OLD.crop_cycle_id THEN 'crop_cycle_id' END,
            CASE WHEN NEW.activity_type IS DISTINCT FROM OLD.activity_type THEN 'activity_type' END,
            CASE WHEN NEW.activity_date IS DISTINCT FROM OLD.activity_date THEN 'activity_date' END,
            CASE WHEN NEW.description IS DISTINCT FROM OLD.description THEN 'description' END,
            CASE WHEN NEW.labor_hours IS DISTINCT FROM OLD.labor_hours THEN 'labor_hours' END,
            CASE WHEN NEW.labor_cost IS DISTINCT FROM OLD.labor_cost THEN 'labor_cost' END,
            CASE WHEN NEW.materials_used IS DISTINCT FROM OLD.materials_used THEN 'materials_used' END,
            CASE WHEN NEW.evidence_urls IS DISTINCT FROM OLD.evidence_urls THEN 'evidence_urls' END,
            CASE WHEN NEW.notes IS DISTINCT FROM OLD.notes THEN 'notes' END
        ]::TEXT[], NULL));
    ELSE
        changed_fields := '{}'::jsonb;
    END IF;
    INSERT INTO farm_activity_operator_event (
        farm_activity_id, location_id, actor_operator_id, action,
        from_status, to_status, reason, metadata
    ) VALUES (
        NEW.id, NEW.location_id, actor_id, workflow_action,
        OLD.status::text, NEW.status::text, workflow_reason,
        CASE WHEN workflow_action = 'draft_edited'
            THEN jsonb_build_object('route', 'gateway_farm_activity_records', 'changed_fields', changed_fields)
            ELSE jsonb_build_object('route', 'gateway_farm_activity_records')
        END
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_farm_activity_gateway_operation
AFTER UPDATE ON farm_activity
FOR EACH ROW EXECUTE FUNCTION record_farm_activity_gateway_operation();

ALTER FUNCTION record_farm_activity_gateway_operation()
    OWNER TO kokonut_farm_activity_event_owner;
REVOKE ALL ON FUNCTION record_farm_activity_gateway_operation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION record_farm_activity_gateway_operation()
    TO kokonut_farm_activity_event_owner;

COMMENT ON TABLE farm_activity_operator_event IS
    'Append-only operator audit for Gateway-managed non-Field-Collector farm activity creation, draft edits, and lifecycle decisions.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.farm_activity_operator_event FROM kokonut_runtime;
        GRANT SELECT ON TABLE public.farm_activity_operator_event TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.farm_activity_operator_event FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA public FROM kokonut_farm_activity_event_owner;

COMMIT;
