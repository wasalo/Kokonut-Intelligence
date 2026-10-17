-- Record the repository-owner confirmation for the two pilot locations.
-- Kept separate from 120 so the ordered migration can create the audit table
-- before fresh pilot data exists.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM (VALUES
            ('a0000000-0000-0000-0000-000000000001'::UUID, 'kokonut-network'),
            ('a0000000-0000-0000-0000-000000000002'::UUID, 'kokonut-network')
          ) AS expected(location_id, org_key)
          LEFT JOIN location AS loc ON loc.id = expected.location_id
          LEFT JOIN organization AS org ON org.id = loc.organization_id
         WHERE loc.id IS NULL OR org.org_key IS DISTINCT FROM expected.org_key
    ) THEN
        RAISE EXCEPTION 'Pilot tenant-owner verification requires migration 387 and the confirmed owner mapping';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM (VALUES
            ('a0000000-0000-0000-0000-000000000001'::UUID, 'kokonut-network'),
            ('a0000000-0000-0000-0000-000000000002'::UUID, 'kokonut-network')
          ) AS expected(location_id, org_key)
          JOIN location AS loc ON loc.id = expected.location_id
          JOIN organization AS org
            ON org.id = loc.organization_id AND org.org_key = expected.org_key
         WHERE NOT EXISTS (
             SELECT 1
               FROM organization_member AS member
              WHERE member.location_id = loc.id
                AND member.organization_id = org.id
                AND member.membership_type = 'owned'
                AND member.role = 'primary'
                AND member.status = 'active'
                AND member.metadata->>'ownership_reconciliation' = 'owner_confirmed'
         )
    ) THEN
        RAISE EXCEPTION 'Pilot tenant-owner verification requires active owner relationships';
    END IF;
END;
$$;

INSERT INTO location_tenant_owner_verification (
    location_id, organization_id, decision_reference, confirmed_by, confirmed_at
)
SELECT loc.id,
       org.id,
       'repository-owner-confirmation-2026-10-13:' || expected.location_slug,
       'repository owner',
       TIMESTAMPTZ '2026-10-13 12:00:00+00'
  FROM (VALUES
    ('a0000000-0000-0000-0000-000000000001'::UUID, 'kokonut-network', 'kokonut-adelphi'),
    ('a0000000-0000-0000-0000-000000000002'::UUID, 'kokonut-network', 'kokonut-genesis')
  ) AS expected(location_id, org_key, location_slug)
  JOIN location AS loc ON loc.id = expected.location_id
  JOIN organization AS org
    ON org.id = loc.organization_id AND org.org_key = expected.org_key
 WHERE EXISTS (
       SELECT 1
         FROM organization_member AS member
        WHERE member.location_id = loc.id
          AND member.organization_id = org.id
          AND member.membership_type = 'owned'
          AND member.role = 'primary'
          AND member.status = 'active'
          AND member.metadata->>'ownership_reconciliation' = 'owner_confirmed'
  )
ON CONFLICT (decision_reference) DO NOTHING;

COMMIT;
