-- Reconcile only the five locations whose operating tenant was confirmed by
-- the repository owner on 2026-10-15. This is not a land-title assertion.
-- Missing future locations are skipped; rerun after their source records are
-- imported. Sharing and operator memberships are never created here.

BEGIN;

DO $$
DECLARE
    canonical_org_id UUID;
    current_location_id UUID;
    current_org_id UUID;
    current_name TEXT;
    active_owner_count INTEGER;
    map_row RECORD;
BEGIN
    SELECT id
      INTO canonical_org_id
      FROM organization
     WHERE org_key = 'kokonut-network'
       AND name = 'Kokonut Network'
       AND status = 'active';

    IF canonical_org_id IS NULL THEN
        RAISE EXCEPTION 'Apply migration 387 and resolve the active Kokonut Network organization first';
    END IF;

    FOR map_row IN
        SELECT *
          FROM (VALUES
            ('Kokonut Genesis', 'kokonut-genesis'),
            ('Kokonut Seeds', 'kokonut-seeds'),
            ('Kokonut Adelphi', 'kokonut-adelphi'),
            ('Kokonut Terra Viva', 'kokonut-terra-viva'),
            ('Kokonut V1', 'kokonut-v1')
          ) AS mapping(location_name, location_slug)
    LOOP
        current_location_id := NULL;
        current_name := NULL;
        current_org_id := NULL;

        SELECT id, name, organization_id
          INTO current_location_id, current_name, current_org_id
          FROM location
         WHERE slug = map_row.location_slug;

        IF NOT FOUND THEN
            IF EXISTS (
                SELECT 1
                  FROM location
                 WHERE name = map_row.location_name
            ) THEN
                RAISE EXCEPTION 'Known location name % exists with an unexpected slug',
                    map_row.location_name;
            END IF;
            -- Seeds, Terra Viva, and V1 may be created by later source imports.
            CONTINUE;
        END IF;

        IF current_name IS DISTINCT FROM map_row.location_name THEN
            RAISE EXCEPTION 'Known location slug % has an unexpected name',
                map_row.location_slug;
        END IF;

        IF current_org_id IS NOT NULL AND current_org_id <> canonical_org_id THEN
            RAISE EXCEPTION 'Known location % has a different organization assignment; use the audited transfer/reconciliation path',
                map_row.location_slug;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM organization_member AS member
             WHERE member.location_id = current_location_id
               AND member.status = 'active'
               AND member.membership_type = 'owned'
               AND member.organization_id <> canonical_org_id
        ) THEN
            RAISE EXCEPTION 'Known location % has an active owner relationship outside Kokonut Network',
                map_row.location_slug;
        END IF;

        SELECT COUNT(*)
          INTO active_owner_count
          FROM organization_member AS member
         WHERE member.location_id = current_location_id
           AND member.status = 'active'
           AND member.membership_type = 'owned';

        IF active_owner_count > 1 THEN
            RAISE EXCEPTION 'Known location % has multiple active owner relationships',
                map_row.location_slug;
        END IF;

        IF active_owner_count = 1 AND NOT EXISTS (
            SELECT 1
              FROM organization_member AS member
             WHERE member.location_id = current_location_id
               AND member.organization_id = canonical_org_id
               AND member.membership_type = 'owned'
               AND member.role = 'primary'
               AND member.status = 'active'
        ) THEN
            RAISE EXCEPTION 'Known location % has an active owner relationship without the primary role',
                map_row.location_slug;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM location_tenant_owner_verification AS owner
             WHERE owner.location_id = current_location_id
               AND owner.revoked_at IS NULL
               AND owner.organization_id <> canonical_org_id
        ) THEN
            RAISE EXCEPTION 'Known location % has an active owner verification outside Kokonut Network',
                map_row.location_slug;
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM location_tenant_owner_verification AS owner
             WHERE owner.location_id = current_location_id
               AND owner.revoked_at IS NULL
               AND owner.organization_id = canonical_org_id
        ) AND EXISTS (
            SELECT 1
              FROM location_tenant_owner_verification AS owner
             WHERE owner.location_id = current_location_id
        ) THEN
            RAISE EXCEPTION 'Known location % has owner-verification history without a current confirmation',
                map_row.location_slug;
        END IF;

        UPDATE location
           SET organization_id = canonical_org_id
         WHERE id = current_location_id
           AND organization_id IS NULL;

        IF active_owner_count = 0 THEN
            INSERT INTO organization_member (
                organization_id, location_id, membership_type, role, status,
                metadata
            ) VALUES (
                canonical_org_id,
                current_location_id,
                'owned',
                'primary',
                'active',
                jsonb_build_object(
                    'operating_tenant_confirmation', 'owner_confirmed',
                    'confirmed_at', '2026-10-15',
                    'basis', 'repository_owner_confirmation',
                    'not_a_land_title_assertion', true
                )
            );
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM location_tenant_owner_verification AS owner
             WHERE owner.location_id = current_location_id
               AND owner.revoked_at IS NULL
               AND owner.organization_id = canonical_org_id
        ) THEN
            INSERT INTO location_tenant_owner_verification (
                location_id, organization_id, decision_reference,
                confirmed_by, confirmed_at
            ) VALUES (
                current_location_id,
                canonical_org_id,
                'repository-owner-operating-tenant-2026-10-15:' || map_row.location_slug,
                'repository owner',
                TIMESTAMPTZ '2026-10-15 12:00:00+00'
            );
        END IF;
    END LOOP;
END;
$$;

COMMIT;
