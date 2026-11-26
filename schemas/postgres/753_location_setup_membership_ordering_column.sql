-- Grant the location setup function owner the membership timestamp it uses
-- to select a stable canonical active owned relationship.
-- Migration 752 granted the other columns used by the setup function but
-- omitted created_at from its ORDER BY clause.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_location_setup_owner'
    ) THEN
        RAISE EXCEPTION 'location setup owner role is missing';
    END IF;
END;
$$;

GRANT SELECT (created_at)
    ON TABLE public.organization_member
    TO kokonut_location_setup_owner;

DO $$
BEGIN
    IF NOT pg_catalog.has_column_privilege(
        'kokonut_location_setup_owner',
        'public.organization_member',
        'created_at',
        'SELECT'
    ) THEN
        RAISE EXCEPTION 'location setup owner cannot read membership creation time';
    END IF;
END;
$$;

COMMIT;
