-- Complete ecological synthesis provenance using only minimal, reviewable row
-- references. The location row itself remains implicit in the bound summary.

BEGIN;

-- Keep the serialized manifest bounded at 64 KB and each source sample at 50
-- rows, while allowing a registered synthesis to identify up to 20 sources.
-- Guard the function-body update so drift from migration 540 fails closed.
DO $$
DECLARE
    function_definition TEXT;
    old_cap_count INTEGER;
    new_cap_count INTEGER;
BEGIN
    function_definition := pg_catalog.pg_get_functiondef(
        'kokonut_security.set_location_ai_summary_source_references(uuid, uuid, uuid, jsonb)'::pg_catalog.regprocedure
    );
    old_cap_count := (
        pg_catalog.length(function_definition)
        - pg_catalog.length(pg_catalog.replace(
            function_definition, 'expected_keys NOT BETWEEN 1 AND 10', ''
        ))
    ) / pg_catalog.length('expected_keys NOT BETWEEN 1 AND 10');
    new_cap_count := (
        pg_catalog.length(function_definition)
        - pg_catalog.length(pg_catalog.replace(
            function_definition, 'expected_keys NOT BETWEEN 1 AND 20', ''
        ))
    ) / pg_catalog.length('expected_keys NOT BETWEEN 1 AND 20');

    IF old_cap_count = 1 AND new_cap_count = 0 THEN
        EXECUTE pg_catalog.replace(
            function_definition,
            'expected_keys NOT BETWEEN 1 AND 10',
            'expected_keys NOT BETWEEN 1 AND 20'
        );
    ELSIF old_cap_count <> 0 OR new_cap_count <> 1 THEN
        RAISE EXCEPTION 'source-reference setter cap differs from migration 540 contract';
    END IF;
END;
$$;

-- These views expose IDs and location scope only. Harvest/feed rows must be
-- verified or published; livestock groups must be active. All require an
-- active farm with a verified/published registry record.
CREATE OR REPLACE VIEW public.v_public_ecological_harvest_event_reference AS
SELECT harvest.id, harvest.location_id
  FROM public.harvest_event AS harvest
  JOIN public.location AS farm ON farm.id = harvest.location_id
 WHERE farm.status = 'active'
   AND harvest.status IN ('verified', 'published')
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   );

CREATE OR REPLACE VIEW public.v_public_ecological_livestock_group_reference AS
SELECT livestock.id, livestock.location_id
  FROM public.livestock_group AS livestock
  JOIN public.location AS farm ON farm.id = livestock.location_id
 WHERE livestock.status = 'active'
   AND farm.status = 'active'
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   );

CREATE OR REPLACE VIEW public.v_public_ecological_feed_intake_reference AS
SELECT intake.id, intake.location_id
  FROM public.feed_intake_record AS intake
  JOIN public.livestock_group AS livestock
    ON livestock.id = intake.livestock_group_id
   AND livestock.location_id = intake.location_id
  JOIN public.location AS farm ON farm.id = intake.location_id
 WHERE livestock.status = 'active'
   AND farm.status = 'active'
   AND intake.status IN ('verified', 'published')
   AND EXISTS (
       SELECT 1 FROM public.farm_registry_record AS registry
        WHERE registry.location_id = farm.id
          AND registry.status IN ('verified', 'published')
   );

REVOKE ALL PRIVILEGES ON TABLE
    public.v_public_ecological_harvest_event_reference,
    public.v_public_ecological_livestock_group_reference,
    public.v_public_ecological_feed_intake_reference
FROM PUBLIC, kokonut_agent_summary_source_login,
     kokonut_agent_summary_source_reader;
GRANT SELECT (id, location_id) ON TABLE
    public.v_public_ecological_harvest_event_reference,
    public.v_public_ecological_livestock_group_reference,
    public.v_public_ecological_feed_intake_reference
TO kokonut_ai_summary_drafter, kokonut_agent_summary_source_view_owner;

INSERT INTO kokonut_security.ai_summary_source_reference_view
    (source_table, source_view_name, source_scope)
VALUES
    ('harvest_event', 'v_public_ecological_harvest_event_reference', 'location'),
    ('livestock_group', 'v_public_ecological_livestock_group_reference', 'location'),
    ('feed_intake_record', 'v_public_ecological_feed_intake_reference', 'location')
ON CONFLICT (source_table) DO UPDATE
    SET source_view_name = EXCLUDED.source_view_name,
        source_scope = EXCLUDED.source_scope;

CREATE OR REPLACE VIEW kokonut_agent_source.v_public_ecological_harvest_event_reference
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_ecological_harvest_event_reference AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.v_public_ecological_livestock_group_reference
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_ecological_livestock_group_reference AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

CREATE OR REPLACE VIEW kokonut_agent_source.v_public_ecological_feed_intake_reference
WITH (security_barrier = true) AS
SELECT source_row.id, source_row.location_id
  FROM public.v_public_ecological_feed_intake_reference AS source_row
 WHERE EXISTS (
       SELECT 1 FROM kokonut_security.current_worker_scope('ai_summary', 'read') AS scope
        WHERE scope.location_id = source_row.location_id
 );

ALTER VIEW kokonut_agent_source.v_public_ecological_harvest_event_reference
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_ecological_livestock_group_reference
    OWNER TO kokonut_agent_summary_source_view_owner;
ALTER VIEW kokonut_agent_source.v_public_ecological_feed_intake_reference
    OWNER TO kokonut_agent_summary_source_view_owner;

REVOKE ALL PRIVILEGES ON TABLE
    kokonut_agent_source.v_public_ecological_harvest_event_reference,
    kokonut_agent_source.v_public_ecological_livestock_group_reference,
    kokonut_agent_source.v_public_ecological_feed_intake_reference
FROM PUBLIC, kokonut_agent_summary_source_login,
     kokonut_agent_summary_source_reader;
GRANT SELECT ON TABLE
    kokonut_agent_source.v_public_ecological_harvest_event_reference,
    kokonut_agent_source.v_public_ecological_livestock_group_reference,
    kokonut_agent_source.v_public_ecological_feed_intake_reference
TO kokonut_agent_summary_source_reader;

COMMIT;
