-- Keep Field Collector farm activity out of reports and further workflow use
-- whenever its source form, review, participant link, or consent is no longer
-- eligible. Canonical records remain available to the private operator review
-- and retention-disposition paths.

CREATE FUNCTION farm_activity_source_eligible_for_use(
    activity_source_system TEXT,
    activity_source_id TEXT,
    activity_source_raw JSONB,
    activity_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    source_collection_id UUID;
BEGIN
    -- Existing non-mobile farm activity keeps its established governance path.
    IF activity_source_system IS DISTINCT FROM 'field_collector' THEN
        RETURN TRUE;
    END IF;

    IF activity_location_id IS NULL
       OR activity_source_id IS NULL
       OR jsonb_typeof(activity_source_raw) IS DISTINCT FROM 'object'
       OR activity_source_raw->>'form_id' IS DISTINCT FROM 'farm_activity_v1'
       OR activity_source_raw->>'offline_collection_id' IS DISTINCT FROM activity_source_id
       OR NULLIF(activity_source_raw->>'form_version', '') IS NULL THEN
        RETURN FALSE;
    END IF;

    BEGIN
        source_collection_id := activity_source_id::UUID;
    EXCEPTION WHEN invalid_text_representation THEN
        RETURN FALSE;
    END;
    IF source_collection_id::text IS DISTINCT FROM activity_source_id THEN
        RETURN FALSE;
    END IF;

    RETURN EXISTS (
        SELECT 1
          FROM offline_collection AS collection
          JOIN mobile_form_version AS revision
            ON revision.id = collection.form_revision_id
          JOIN v_mobile_collection_use_eligibility AS eligibility
            ON eligibility.collection_id = collection.id
         WHERE collection.id = source_collection_id
           AND collection.location_id = activity_location_id
           AND collection.form_id = activity_source_raw->>'form_id'
           AND collection.form_version = activity_source_raw->>'form_version'
           AND collection.collection_type = 'farm_activity'
           AND collection.sync_status = 'synced'
           AND collection.form_validation_status = 'active'
           AND collection.form_review_required = FALSE
           AND revision.form_id = collection.form_id
           AND revision.version = collection.form_version
           AND revision.status = 'active'
           AND eligibility.eligible_for_use IS TRUE
    );
END;
$$;

COMMENT ON FUNCTION farm_activity_source_eligible_for_use(TEXT, TEXT, JSONB, UUID) IS
    'Fail-closed current-use gate for Field Collector farm activity; non-mobile rows retain existing governance. This is not an authorization or human-review substitute.';

-- Directus cannot express this cross-table eligibility predicate in its row
-- permission DSL. Keep legacy farm_activity rows readable there, but route all
-- Field Collector reads through the scoped Gateway review/use endpoints.
-- Directus is optional, so a Kernel-only deployment has no dependency here.
DO $$
DECLARE
    field_collector_read_gate JSON :=
        '{"_or":[{"source_system":{"_null":true}},{"source_system":{"_neq":"field_collector"}}]}'::JSON;
BEGIN
    IF to_regclass('public.directus_permissions') IS NOT NULL THEN
        UPDATE public.directus_permissions
           SET permissions = json_build_object(
               '_and', json_build_array(
                   COALESCE(permissions, '{}'::JSON), field_collector_read_gate
               )
           )
         WHERE collection = 'farm_activity'
           AND action = 'read'
           AND NOT jsonb_path_exists(
               COALESCE(permissions, '{}'::JSON)::jsonb,
               '$.** ? (@._or[0].source_system._null == true && @._or[1].source_system._neq == "field_collector")'::jsonpath
           );
    END IF;
END;
$$;

-- Keep the two repository-owned saved dashboard queries aligned. Unknown or
-- operator-edited SQL is deliberately not rewritten by this migration.
UPDATE dashboard_dataset
   SET query_sql = $query$
       SELECT fa.activity_type, COUNT(*) as count,
              SUM(fa.labor_hours) as total_hours
         FROM farm_activity fa
        WHERE fa.location_id = 'a0000000-0000-0000-0000-000000000001'
          AND fa.status = 'published'
          AND farm_activity_source_eligible_for_use(
              fa.source_system, fa.source_id, fa.source_raw, fa.location_id
          )
        GROUP BY fa.activity_type
        ORDER BY count DESC
   $query$,
       updated_at = NOW()
 WHERE id = 'd1000000-0000-0000-0000-000000000001'
   AND query_sql = $old$SELECT fa.activity_type, COUNT(*) as count, SUM(labor_hours) as total_hours FROM farm_activity fa WHERE fa.location_id = 'a0000000-0000-0000-0000-000000000001' GROUP BY fa.activity_type ORDER BY count DESC$old$;

UPDATE dashboard_dataset
   SET query_sql = replace(
           query_sql,
           $old$UNION ALL SELECT 'farm_activity', status, COUNT(*) FROM farm_activity GROUP BY status$old$,
           $new$UNION ALL SELECT 'farm_activity', status, COUNT(*) FROM farm_activity WHERE farm_activity_source_eligible_for_use(source_system, source_id, source_raw, location_id) GROUP BY status$new$
       ),
       updated_at = NOW()
 WHERE id = 'd1040000-0000-0000-0000-000000000001'
   AND position(
       $old$UNION ALL SELECT 'farm_activity', status, COUNT(*) FROM farm_activity GROUP BY status$old$
       IN query_sql
   ) > 0;

-- The existing eligibility view evaluates the immutable revision snapshot at
-- collection time. Retire/inactivate must also move all linked collections to
-- the private review queue so the existing view immediately reports them as
-- ineligible. The read-time helper above independently checks revision status.
CREATE FUNCTION queue_collections_for_inactive_form_revision()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'active' AND NEW.status IS DISTINCT FROM 'active' THEN
        UPDATE offline_collection
           SET form_validation_status = 'retired_review',
               form_review_required = TRUE,
               updated_at = NOW()
         WHERE form_revision_id = NEW.id
           AND (form_validation_status IS DISTINCT FROM 'retired_review'
                OR form_review_required IS DISTINCT FROM TRUE);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_queue_collections_for_inactive_form_revision
AFTER UPDATE OF status ON mobile_form_version
FOR EACH ROW
EXECUTE FUNCTION queue_collections_for_inactive_form_revision();

-- Cover revisions that were already inactive before this migration.
UPDATE offline_collection AS collection
   SET form_validation_status = 'retired_review',
       form_review_required = TRUE,
       updated_at = NOW()
  FROM mobile_form_version AS revision
 WHERE revision.id = collection.form_revision_id
   AND revision.status <> 'active'
   AND (collection.form_validation_status IS DISTINCT FROM 'retired_review'
        OR collection.form_review_required IS DISTINCT FROM TRUE);

CREATE FUNCTION guard_farm_activity_use_eligibility_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    content_changed BOOLEAN;
    provenance_changed BOOLEAN;
    productive_status_changed BOOLEAN;
BEGIN
    IF OLD.source_system IS DISTINCT FROM 'field_collector'
       AND NEW.source_system IS DISTINCT FROM 'field_collector' THEN
        RETURN NEW;
    END IF;

    content_changed := ROW(
        NEW.plot_id, NEW.crop_cycle_id, NEW.activity_type, NEW.activity_date,
        NEW.description, NEW.labor_hours, NEW.labor_cost, NEW.materials_used,
        NEW.evidence_urls, NEW.evidence_hashes, NEW.notes
    ) IS DISTINCT FROM ROW(
        OLD.plot_id, OLD.crop_cycle_id, OLD.activity_type, OLD.activity_date,
        OLD.description, OLD.labor_hours, OLD.labor_cost, OLD.materials_used,
        OLD.evidence_urls, OLD.evidence_hashes, OLD.notes
    );
    provenance_changed := ROW(
        NEW.source_system, NEW.source_id, NEW.source_raw, NEW.location_id
    ) IS DISTINCT FROM ROW(
        OLD.source_system, OLD.source_id, OLD.source_raw, OLD.location_id
    );
    productive_status_changed := NEW.status IS DISTINCT FROM OLD.status
        AND NEW.status::text IN ('draft', 'submitted', 'verified', 'published');

    IF provenance_changed THEN
        RAISE EXCEPTION 'Field Collector farm activity source provenance is immutable';
    END IF;

    IF (content_changed OR productive_status_changed)
       AND farm_activity_source_eligible_for_use(
            NEW.source_system, NEW.source_id, NEW.source_raw, NEW.location_id
       ) IS NOT TRUE THEN
        RAISE EXCEPTION 'Field Collector farm activity is ineligible for further use pending human disposition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_farm_activity_use_eligibility
BEFORE UPDATE ON farm_activity
FOR EACH ROW
EXECUTE FUNCTION guard_farm_activity_use_eligibility_update();

COMMENT ON FUNCTION guard_farm_activity_use_eligibility_update() IS
    'Blocks Field Collector farm activity edits and productive lifecycle transitions after its current form, review, participant, or consent eligibility ends. Existing rejection/exception actions remain subject to their governed lifecycle preconditions.';

INSERT INTO schema_version (version, description, applied_by)
VALUES (
    'farm-activity-consent-use-gate-v1',
    'Current Field Collector eligibility gate for canonical activity use and workflow (schema 386)',
    'schema 386'
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
