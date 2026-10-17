-- Tenant-qualified operator access builds on, but does not replace, legacy
-- location grants. RLS remains a separate rollout gate.

BEGIN;

CREATE TABLE IF NOT EXISTS location_tenant_owner_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT,
    decision_reference TEXT NOT NULL UNIQUE,
    confirmed_by TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT,
    CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_location_tenant_owner_verification_active
    ON location_tenant_owner_verification (location_id)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_location_tenant_owner_verification_history
    ON location_tenant_owner_verification (location_id, confirmed_at DESC);

CREATE TABLE IF NOT EXISTS operator_organization_membership (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT,
    membership_role TEXT NOT NULL DEFAULT 'operator'
        CHECK (membership_role IN ('operator', 'tenant_admin')),
    granted_by TEXT NOT NULL CHECK (length(btrim(granted_by)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT,
    CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operator_organization_membership_active
    ON operator_organization_membership (operator_id, organization_id)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_operator_organization_membership_org
    ON operator_organization_membership (organization_id, operator_id)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS location_organization_share (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT,
    granted_by_operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by_operator_id UUID REFERENCES operator_identity(id) ON DELETE RESTRICT,
    revocation_reason TEXT,
    CHECK (
        (revoked_at IS NULL AND revoked_by_operator_id IS NULL AND revocation_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by_operator_id IS NOT NULL
         AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) > 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_location_organization_share_active
    ON location_organization_share (location_id, organization_id)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_location_organization_share_org
    ON location_organization_share (organization_id, location_id)
    WHERE revoked_at IS NULL;

ALTER TABLE operator_scope_grant
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organization(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_operator_scope_grant_org_active
    ON operator_scope_grant (organization_id, operator_id, location_id)
    WHERE revoked_at IS NULL AND organization_id IS NOT NULL;

-- Record only the two ownership decisions explicitly confirmed by the
-- repository owner. Do not infer verification from other location fields.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM (VALUES
            ('a0000000-0000-0000-0000-000000000001'::UUID, 'kokonut-network'),
            ('a0000000-0000-0000-0000-000000000002'::UUID, 'kokonut-network')
          ) AS expected(location_id, org_key)
          JOIN location AS loc ON loc.id = expected.location_id
          LEFT JOIN organization AS org ON org.id = loc.organization_id
         WHERE org.org_key IS DISTINCT FROM expected.org_key
    ) THEN
        RAISE EXCEPTION 'A confirmed seed location has an unexpected current organization';
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
        RAISE EXCEPTION 'A confirmed seed location is missing its active owner relationship';
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

CREATE OR REPLACE FUNCTION operator_scope_grant_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY INVOKER
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM operator_scope_grant AS grant_row
          JOIN operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
          JOIN location AS loc ON loc.id = grant_row.location_id
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
           AND (
               -- Existing location-only grants remain compatible until each
               -- operator's tenant affiliation has an accountable mapping.
               grant_row.organization_id IS NULL
               OR (
                   grant_row.organization_id IS NOT NULL
                   AND EXISTS (
                       SELECT 1
                         FROM operator_organization_membership AS membership
                         JOIN organization AS tenant
                           ON tenant.id = membership.organization_id
                          AND tenant.status = 'active'
                        WHERE membership.operator_id = grant_row.operator_id
                          AND membership.organization_id = grant_row.organization_id
                          AND membership.revoked_at IS NULL
                   )
                   AND EXISTS (
                       SELECT 1
                         FROM location_tenant_owner_verification AS owner
                        WHERE owner.location_id = loc.id
                          AND owner.organization_id = loc.organization_id
                          AND owner.revoked_at IS NULL
                          AND (
                              owner.organization_id = grant_row.organization_id
                              OR EXISTS (
                                  SELECT 1
                                    FROM location_organization_share AS share
                                   WHERE share.location_id = loc.id
                                     AND share.organization_id = grant_row.organization_id
                                     AND share.revoked_at IS NULL
                                     AND (share.expires_at IS NULL OR share.expires_at > NOW())
                              )
                          )
                   )
               )
           )
    );
$$;

COMMENT ON TABLE location_tenant_owner_verification IS
    'Explicit, auditable evidence for the current organization tenant of a location; organization_member alone is not sufficient.';
COMMENT ON TABLE operator_organization_membership IS
    'Server-managed OIDC operator affiliation; membership alone grants no data access.';
COMMENT ON TABLE location_organization_share IS
    'Explicit, revocable location sharing from its verified owner to another organization; resource/action grants remain separately required.';
COMMENT ON COLUMN operator_scope_grant.organization_id IS
    'Tenant context for a new operator grant; NULL retains an existing legacy location-only grant.';
COMMENT ON FUNCTION operator_scope_grant_allows(UUID, TEXT, TEXT, UUID) IS
    'Checks an active location grant and, when tenant-qualified, current operator membership plus verified ownership or explicit sharing.';

COMMIT;
