-- Final pilot ownership reconciliation. Applied after both demo locations
-- exist so fresh bootstrap and repeated pilot seeding converge identically.

BEGIN;

DO $$
DECLARE
    canonical_org_id UUID;
    current_org_id UUID;
    current_name TEXT;
    current_slug TEXT;
    location_seed RECORD;
BEGIN
    SELECT id
      INTO canonical_org_id
      FROM organization
     WHERE org_key = 'kokonut-network';

    IF canonical_org_id IS NULL THEN
        RAISE EXCEPTION 'Apply migration 387 before loading Kokonut Network pilot ownership';
    END IF;

    FOR location_seed IN
        SELECT *
          FROM (VALUES
            ('a0000000-0000-0000-0000-000000000001'::UUID,
             'Kokonut Adelphi', 'kokonut-adelphi',
             'a0000000-0000-0000-0000-000000000010'::UUID,
             'a0000000-0000-0000-0000-000000000711'::UUID),
            ('a0000000-0000-0000-0000-000000000002'::UUID,
             'Kokonut Genesis', 'kokonut-genesis',
             'a0000000-0000-0000-0000-000000000012'::UUID,
             'a0000000-0000-0000-0000-000000000712'::UUID)
          ) AS seed(location_id, location_name, location_slug, farm_id, member_id)
    LOOP
        SELECT name, slug, organization_id
          INTO current_name, current_slug, current_org_id
          FROM location
         WHERE id = location_seed.location_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Expected pilot location % is missing',
                location_seed.location_id;
        END IF;

        IF current_name IS DISTINCT FROM location_seed.location_name
           OR current_slug IS DISTINCT FROM location_seed.location_slug THEN
            RAISE EXCEPTION 'Pilot location % has an unexpected name or slug',
                location_seed.location_id;
        END IF;

        IF current_org_id IS NOT NULL
           AND current_org_id <> canonical_org_id
           AND NOT EXISTS (
               SELECT 1
                 FROM organization
                WHERE id = current_org_id
                  AND id = 'a0000000-0000-0000-0000-000000000700'::UUID
                  AND org_key = 'kokonut-adelphi'
                  AND name = 'Kokonut Adelphi'
           ) THEN
            RAISE EXCEPTION 'Pilot location % has an unreviewed existing owner',
                location_seed.location_id;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM organization_member AS member
              JOIN organization AS owner ON owner.id = member.organization_id
             WHERE member.location_id = location_seed.location_id
               AND member.status = 'active'
               AND member.membership_type = 'owned'
               AND member.organization_id <> canonical_org_id
               AND NOT (
                   member.organization_id = 'a0000000-0000-0000-0000-000000000700'::UUID
                   AND owner.org_key = 'kokonut-adelphi'
                   AND owner.name = 'Kokonut Adelphi'
               )
        ) THEN
            RAISE EXCEPTION 'Pilot location % has an unreviewed active owner relationship',
                location_seed.location_id;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM organization_member
             WHERE id = location_seed.member_id
               AND (location_id <> location_seed.location_id
                    OR membership_type <> 'owned')
        ) THEN
            RAISE EXCEPTION 'Canonical ownership relationship ID % is already in use',
                location_seed.member_id;
        END IF;

        UPDATE location
           SET organization_id = canonical_org_id
         WHERE id = location_seed.location_id;

        UPDATE organization_member
           SET status = 'inactive', updated_at = NOW()
         WHERE location_id = location_seed.location_id
           AND membership_type = 'owned'
           AND id <> location_seed.member_id
           AND status = 'active';

        INSERT INTO organization_member (
            id, organization_id, location_id, farm_id, membership_type,
            role, status, metadata
        ) VALUES (
            location_seed.member_id,
            canonical_org_id,
            location_seed.location_id,
            CASE WHEN EXISTS (SELECT 1 FROM farm WHERE id = location_seed.farm_id)
                 THEN location_seed.farm_id ELSE NULL END,
            'owned',
            'primary',
            'active',
            '{"ownership_reconciliation":"owner_confirmed","confirmed_at":"2026-10-13"}'::JSONB
        )
        ON CONFLICT (id) DO UPDATE SET
            organization_id = EXCLUDED.organization_id,
            location_id = EXCLUDED.location_id,
            farm_id = COALESCE(EXCLUDED.farm_id, organization_member.farm_id),
            membership_type = 'owned',
            role = 'primary',
            status = 'active',
            metadata = EXCLUDED.metadata,
            updated_at = NOW();
    END LOOP;
END;
$$;

COMMIT;
