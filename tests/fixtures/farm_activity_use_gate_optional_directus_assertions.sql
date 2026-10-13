DO $$
BEGIN
    IF to_regclass('public.directus_permissions') IS NOT NULL THEN
        RAISE EXCEPTION 'optional Directus table unexpectedly exists';
    END IF;

    IF to_regprocedure('farm_activity_source_eligible_for_use(text,text,jsonb,uuid)') IS NULL THEN
        RAISE EXCEPTION 'Kernel migration did not install its use gate without Directus';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 'farm-activity-consent-use-gate-v1') THEN
        RAISE EXCEPTION 'Kernel migration version marker is missing without Directus';
    END IF;
END;
$$;
