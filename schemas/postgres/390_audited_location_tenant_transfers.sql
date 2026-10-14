-- Ownership here is the platform's verified organization-tenant assignment;
-- this workflow does not assert legal land title or change on-chain state.

BEGIN;

CREATE TABLE IF NOT EXISTS location_tenant_transfer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    source_owner_verification_id UUID NOT NULL
        REFERENCES location_tenant_owner_verification(id) ON DELETE RESTRICT,
    source_organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT,
    target_organization_id UUID NOT NULL REFERENCES organization(id) ON DELETE RESTRICT,
    requested_by_operator_id UUID NOT NULL REFERENCES operator_identity(id) ON DELETE RESTRICT,
    request_reference TEXT NOT NULL UNIQUE
        CHECK (length(btrim(request_reference)) BETWEEN 1 AND 500),
    request_reason TEXT NOT NULL
        CHECK (length(btrim(request_reason)) BETWEEN 1 AND 2000),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_owner_relationship_ids UUID[] NOT NULL
        CHECK (cardinality(source_owner_relationship_ids) > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'cancelled')),
    accepted_by_operator_id UUID REFERENCES operator_identity(id) ON DELETE RESTRICT,
    acceptance_reference TEXT UNIQUE,
    accepted_at TIMESTAMPTZ,
    resulting_owner_verification_id UUID
        REFERENCES location_tenant_owner_verification(id) ON DELETE RESTRICT,
    revoked_share_ids UUID[] NOT NULL DEFAULT '{}'::UUID[],
    revoked_scope_grant_ids UUID[] NOT NULL DEFAULT '{}'::UUID[],
    cancelled_by_operator_id UUID REFERENCES operator_identity(id) ON DELETE RESTRICT,
    cancellation_reason TEXT,
    cancelled_at TIMESTAMPTZ,
    CHECK (source_organization_id <> target_organization_id),
    CHECK (status = 'accepted' OR
           (cardinality(revoked_share_ids) = 0
            AND cardinality(revoked_scope_grant_ids) = 0)),
    CHECK (
        (status = 'pending'
            AND accepted_by_operator_id IS NULL AND acceptance_reference IS NULL
            AND accepted_at IS NULL AND resulting_owner_verification_id IS NULL
            AND cancelled_by_operator_id IS NULL AND cancellation_reason IS NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'accepted'
            AND accepted_by_operator_id IS NOT NULL
            AND accepted_by_operator_id <> requested_by_operator_id
            AND acceptance_reference IS NOT NULL AND length(btrim(acceptance_reference)) > 0
            AND accepted_at IS NOT NULL AND resulting_owner_verification_id IS NOT NULL
            AND cancelled_by_operator_id IS NULL AND cancellation_reason IS NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'cancelled'
            AND accepted_by_operator_id IS NULL AND acceptance_reference IS NULL
            AND accepted_at IS NULL AND resulting_owner_verification_id IS NULL
            AND cancelled_by_operator_id IS NOT NULL
            AND cancellation_reason IS NOT NULL AND length(btrim(cancellation_reason)) > 0
            AND cancelled_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_location_tenant_transfer_pending
    ON location_tenant_transfer (location_id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_location_tenant_transfer_history
    ON location_tenant_transfer (location_id, requested_at DESC, id);

ALTER TABLE location_organization_share
    ADD COLUMN IF NOT EXISTS ownership_transfer_id UUID
        REFERENCES location_tenant_transfer(id) ON DELETE RESTRICT;
ALTER TABLE operator_scope_grant
    ADD COLUMN IF NOT EXISTS revoked_by TEXT,
    ADD COLUMN IF NOT EXISTS revocation_reason TEXT,
    ADD COLUMN IF NOT EXISTS ownership_transfer_id UUID
        REFERENCES location_tenant_transfer(id) ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_operator_scope_grant_revocation_actor_reason'
           AND conrelid = 'operator_scope_grant'::regclass
    ) THEN
        ALTER TABLE operator_scope_grant
            ADD CONSTRAINT ck_operator_scope_grant_revocation_actor_reason
            CHECK ((revoked_by IS NULL) = (revocation_reason IS NULL));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_operator_scope_grant_transfer_revoked'
           AND conrelid = 'operator_scope_grant'::regclass
    ) THEN
        ALTER TABLE operator_scope_grant
            ADD CONSTRAINT ck_operator_scope_grant_transfer_revoked
            CHECK (ownership_transfer_id IS NULL OR
                   (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
                    AND revocation_reason IS NOT NULL));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_location_share_transfer_revoked'
           AND conrelid = 'location_organization_share'::regclass
    ) THEN
        ALTER TABLE location_organization_share
            ADD CONSTRAINT ck_location_share_transfer_revoked
            CHECK (ownership_transfer_id IS NULL OR
                   (revoked_at IS NOT NULL AND revoked_by_operator_id IS NOT NULL
                    AND revocation_reason IS NOT NULL));
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION guard_location_tenant_transfer_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_owner_verification_id UUID;
    current_relationship_ids UUID[];
BEGIN
    IF NEW.status <> 'pending' THEN
        RAISE EXCEPTION 'location tenant transfers must begin pending';
    END IF;

    SELECT owner.id
      INTO current_owner_verification_id
      FROM location AS loc
      JOIN organization AS tenant
        ON tenant.id = loc.organization_id AND tenant.status = 'active'
      JOIN location_tenant_owner_verification AS owner
        ON owner.location_id = loc.id
       AND owner.organization_id = loc.organization_id
       AND owner.revoked_at IS NULL
     WHERE loc.id = NEW.location_id
       AND loc.organization_id = NEW.source_organization_id;
    IF current_owner_verification_id IS DISTINCT FROM NEW.source_owner_verification_id THEN
        RAISE EXCEPTION 'transfer source does not match current verified location ownership';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM organization
         WHERE id = NEW.target_organization_id AND status = 'active'
    ) OR NOT EXISTS (
        SELECT 1
          FROM operator_identity AS identity
          JOIN operator_organization_membership AS membership
            ON membership.operator_id = identity.id
         WHERE identity.id = NEW.requested_by_operator_id
           AND identity.enabled
           AND membership.organization_id = NEW.source_organization_id
           AND membership.membership_role = 'tenant_admin'
           AND membership.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'transfer requires an active target organization and source tenant administrator';
    END IF;

    IF EXISTS (
        SELECT 1 FROM organization_member AS member
         WHERE member.location_id = NEW.location_id
           AND member.membership_type = 'owned' AND member.status = 'active'
           AND member.organization_id <> NEW.source_organization_id
    ) THEN
        RAISE EXCEPTION 'conflicting active owner relationships must be reconciled first';
    END IF;

    SELECT array_agg(member.id ORDER BY member.id)
      INTO current_relationship_ids
      FROM organization_member AS member
     WHERE member.location_id = NEW.location_id
       AND member.organization_id = NEW.source_organization_id
       AND member.membership_type = 'owned' AND member.status = 'active';
    IF current_relationship_ids IS DISTINCT FROM NEW.source_owner_relationship_ids
       OR NOT EXISTS (
           SELECT 1 FROM organization_member AS member
            WHERE member.id = ANY(NEW.source_owner_relationship_ids)
              AND member.role = 'primary'
       ) THEN
        RAISE EXCEPTION 'transfer must snapshot the current active owned-primary relationships';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_location_tenant_transfer_insert
    ON location_tenant_transfer;
CREATE TRIGGER trg_guard_location_tenant_transfer_insert
BEFORE INSERT ON location_tenant_transfer
FOR EACH ROW EXECUTE FUNCTION guard_location_tenant_transfer_insert();

CREATE OR REPLACE FUNCTION guard_location_tenant_transfer_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.id, NEW.location_id, NEW.source_owner_verification_id,
        NEW.source_organization_id, NEW.target_organization_id,
        NEW.requested_by_operator_id, NEW.request_reference, NEW.request_reason,
        NEW.requested_at, NEW.source_owner_relationship_ids
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.location_id, OLD.source_owner_verification_id,
        OLD.source_organization_id, OLD.target_organization_id,
        OLD.requested_by_operator_id, OLD.request_reference, OLD.request_reason,
        OLD.requested_at, OLD.source_owner_relationship_ids
    ) THEN
        RAISE EXCEPTION 'location tenant transfer request evidence is immutable';
    END IF;

    IF OLD.status <> 'pending' OR NEW.status NOT IN ('accepted', 'cancelled') THEN
        RAISE EXCEPTION 'location tenant transfer permits one pending-to-terminal transition';
    END IF;

    IF NEW.status = 'accepted' AND (
        NOT EXISTS (
            SELECT 1
              FROM operator_identity AS identity
              JOIN operator_organization_membership AS membership
                ON membership.operator_id = identity.id
              JOIN organization AS tenant ON tenant.id = membership.organization_id
             WHERE identity.id = NEW.requested_by_operator_id
               AND identity.enabled AND tenant.status = 'active'
               AND membership.organization_id = NEW.source_organization_id
               AND membership.membership_role = 'tenant_admin'
               AND membership.revoked_at IS NULL
        )
        OR NOT EXISTS (
            SELECT 1
              FROM operator_identity AS identity
              JOIN operator_organization_membership AS membership
                ON membership.operator_id = identity.id
              JOIN organization AS tenant ON tenant.id = membership.organization_id
             WHERE identity.id = NEW.accepted_by_operator_id
               AND identity.enabled AND tenant.status = 'active'
               AND membership.organization_id = NEW.target_organization_id
               AND membership.membership_role = 'tenant_admin'
               AND membership.revoked_at IS NULL
        )
    ) THEN
        RAISE EXCEPTION 'transfer acceptance requires active source and target tenant administrators';
    END IF;

    IF NEW.status = 'cancelled' AND NOT EXISTS (
        SELECT 1
          FROM operator_identity AS identity
          JOIN operator_organization_membership AS membership
            ON membership.operator_id = identity.id
          JOIN organization AS tenant ON tenant.id = membership.organization_id
         WHERE identity.id = NEW.cancelled_by_operator_id
           AND identity.enabled AND tenant.status = 'active'
           AND membership.organization_id = NEW.source_organization_id
           AND membership.membership_role = 'tenant_admin'
           AND membership.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'transfer cancellation requires an active source tenant administrator';
    END IF;

    IF NEW.status = 'accepted' AND (
        NOT EXISTS (
            SELECT 1
              FROM location AS loc
              JOIN location_tenant_owner_verification AS owner
                ON owner.id = NEW.resulting_owner_verification_id
               AND owner.location_id = loc.id
               AND owner.organization_id = NEW.target_organization_id
               AND owner.revoked_at IS NULL
             WHERE loc.id = NEW.location_id
               AND loc.organization_id = NEW.target_organization_id
        )
        OR EXISTS (
            SELECT 1
              FROM location_tenant_owner_verification AS owner
             WHERE owner.id = NEW.source_owner_verification_id
               AND owner.revoked_at IS NULL
        )
        OR EXISTS (
            SELECT 1 FROM location_organization_share AS share
             WHERE share.location_id = NEW.location_id AND share.revoked_at IS NULL
        )
        OR EXISTS (
            SELECT 1 FROM operator_scope_grant AS grant_row
             WHERE grant_row.location_id = NEW.location_id AND grant_row.revoked_at IS NULL
        )
        OR EXISTS (
            SELECT 1 FROM organization_member AS member
             WHERE member.location_id = NEW.location_id
               AND member.membership_type = 'owned' AND member.status = 'active'
               AND member.organization_id <> NEW.target_organization_id
        )
        OR NEW.revoked_share_ids IS DISTINCT FROM (
            SELECT COALESCE(array_agg(share.id ORDER BY share.id), '{}'::UUID[])
              FROM location_organization_share AS share
             WHERE share.ownership_transfer_id = NEW.id
        )
        OR NEW.revoked_scope_grant_ids IS DISTINCT FROM (
            SELECT COALESCE(array_agg(grant_row.id ORDER BY grant_row.id), '{}'::UUID[])
              FROM operator_scope_grant AS grant_row
             WHERE grant_row.ownership_transfer_id = NEW.id
        )
        OR NOT EXISTS (
            SELECT 1 FROM organization_member AS member
             WHERE member.location_id = NEW.location_id
               AND member.organization_id = NEW.target_organization_id
               AND member.membership_type = 'owned' AND member.role = 'primary'
               AND member.status = 'active'
        )
    ) THEN
        RAISE EXCEPTION 'transfer acceptance does not match the completed owner and access changes';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_location_tenant_transfer_update
    ON location_tenant_transfer;
CREATE TRIGGER trg_guard_location_tenant_transfer_update
BEFORE UPDATE ON location_tenant_transfer
FOR EACH ROW EXECUTE FUNCTION guard_location_tenant_transfer_update();

CREATE OR REPLACE FUNCTION reject_location_tenant_transfer_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'location tenant transfer history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_reject_location_tenant_transfer_delete
    ON location_tenant_transfer;
CREATE TRIGGER trg_reject_location_tenant_transfer_delete
BEFORE DELETE ON location_tenant_transfer
FOR EACH ROW EXECUTE FUNCTION reject_location_tenant_transfer_delete();
DROP TRIGGER IF EXISTS trg_reject_location_tenant_transfer_truncate
    ON location_tenant_transfer;
CREATE TRIGGER trg_reject_location_tenant_transfer_truncate
BEFORE TRUNCATE ON location_tenant_transfer
FOR EACH STATEMENT EXECUTE FUNCTION reject_location_tenant_transfer_delete();

CREATE OR REPLACE FUNCTION request_location_tenant_transfer(
    requested_location_id UUID,
    requested_target_organization_id UUID,
    requesting_operator_id UUID,
    transfer_reference TEXT,
    transfer_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    source_organization_id UUID;
    source_owner_verification_id UUID;
    target_organization_id UUID;
    owner_relationship_ids UUID[];
    transfer_id UUID := gen_random_uuid();
BEGIN
    IF transfer_reference IS NULL OR length(btrim(transfer_reference)) NOT BETWEEN 1 AND 500
       OR transfer_reason IS NULL OR length(btrim(transfer_reason)) NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'transfer reference and reason are required';
    END IF;

    SELECT loc.organization_id, owner.id
      INTO source_organization_id, source_owner_verification_id
      FROM location AS loc
      JOIN organization AS tenant
        ON tenant.id = loc.organization_id AND tenant.status = 'active'
      JOIN location_tenant_owner_verification AS owner
        ON owner.location_id = loc.id
       AND owner.organization_id = loc.organization_id
       AND owner.revoked_at IS NULL
     WHERE loc.id = requested_location_id
     FOR UPDATE OF loc, owner;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'location must have a current verified tenant owner';
    END IF;

    IF source_organization_id = requested_target_organization_id THEN
        RAISE EXCEPTION 'target organization already owns this location';
    END IF;

    SELECT id INTO target_organization_id
      FROM organization
     WHERE id = requested_target_organization_id AND status = 'active'
     FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'target organization must be active';
    END IF;

    PERFORM 1
      FROM operator_identity AS identity
      JOIN operator_organization_membership AS membership
        ON membership.operator_id = identity.id
     WHERE identity.id = requesting_operator_id AND identity.enabled
       AND membership.organization_id = source_organization_id
       AND membership.membership_role = 'tenant_admin'
       AND membership.revoked_at IS NULL
     FOR SHARE OF identity, membership;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'request requires an enabled source-owner tenant administrator';
    END IF;

    IF EXISTS (
        SELECT 1 FROM organization_member AS member
         WHERE member.location_id = requested_location_id
           AND member.membership_type = 'owned' AND member.status = 'active'
           AND member.organization_id <> source_organization_id
    ) THEN
        RAISE EXCEPTION 'conflicting active owner relationships must be reconciled first';
    END IF;

    PERFORM 1
      FROM organization_member AS member
     WHERE member.location_id = requested_location_id
       AND member.organization_id = source_organization_id
       AND member.membership_type = 'owned' AND member.status = 'active'
     FOR UPDATE;

    SELECT array_agg(member.id ORDER BY member.id)
      INTO owner_relationship_ids
      FROM organization_member AS member
     WHERE member.location_id = requested_location_id
       AND member.organization_id = source_organization_id
       AND member.membership_type = 'owned' AND member.status = 'active';
    IF owner_relationship_ids IS NULL OR NOT EXISTS (
        SELECT 1 FROM organization_member AS member
         WHERE member.id = ANY(owner_relationship_ids)
           AND member.role = 'primary'
    ) THEN
        RAISE EXCEPTION 'verified owner needs an active owned-primary relationship';
    END IF;

    INSERT INTO location_tenant_transfer (
        id, location_id, source_owner_verification_id,
        source_organization_id, target_organization_id,
        requested_by_operator_id, request_reference, request_reason,
        source_owner_relationship_ids
    ) VALUES (
        transfer_id, requested_location_id, source_owner_verification_id,
        source_organization_id, target_organization_id,
        requesting_operator_id, btrim(transfer_reference), btrim(transfer_reason),
        owner_relationship_ids
    );
    RETURN transfer_id;
END;
$$;

CREATE OR REPLACE FUNCTION accept_location_tenant_transfer(
    requested_transfer_id UUID,
    accepting_operator_id UUID,
    acceptance_decision_reference TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    transfer_row location_tenant_transfer%ROWTYPE;
    current_location_organization_id UUID;
    current_owner_verification_id UUID;
    current_owner_relationship_ids UUID[];
    new_owner_verification_id UUID;
    revoked_shares UUID[] := '{}'::UUID[];
    revoked_grants UUID[] := '{}'::UUID[];
    inserted_relationship_count INTEGER;
BEGIN
    IF acceptance_decision_reference IS NULL
       OR length(btrim(acceptance_decision_reference)) NOT BETWEEN 1 AND 500 THEN
        RAISE EXCEPTION 'acceptance reference is required';
    END IF;

    SELECT * INTO transfer_row
      FROM location_tenant_transfer
     WHERE id = requested_transfer_id AND status = 'pending'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'pending location tenant transfer was not found';
    END IF;
    IF accepting_operator_id = transfer_row.requested_by_operator_id THEN
        RAISE EXCEPTION 'transfer request and acceptance require different operators';
    END IF;

    SELECT loc.organization_id, owner.id
      INTO current_location_organization_id, current_owner_verification_id
      FROM location AS loc
      JOIN organization AS source_tenant
        ON source_tenant.id = loc.organization_id AND source_tenant.status = 'active'
      JOIN location_tenant_owner_verification AS owner
        ON owner.location_id = loc.id
       AND owner.organization_id = loc.organization_id
       AND owner.revoked_at IS NULL
     WHERE loc.id = transfer_row.location_id
     FOR UPDATE OF loc, owner;
    IF NOT FOUND
       OR current_location_organization_id <> transfer_row.source_organization_id
       OR current_owner_verification_id <> transfer_row.source_owner_verification_id THEN
        RAISE EXCEPTION 'location owner changed after the transfer was requested';
    END IF;

    PERFORM 1
      FROM operator_identity AS identity
      JOIN operator_organization_membership AS membership
        ON membership.operator_id = identity.id
      JOIN organization AS tenant ON tenant.id = membership.organization_id
     WHERE identity.id = transfer_row.requested_by_operator_id
       AND identity.enabled AND tenant.status = 'active'
       AND membership.organization_id = transfer_row.source_organization_id
       AND membership.membership_role = 'tenant_admin'
       AND membership.revoked_at IS NULL
     FOR SHARE OF identity, membership, tenant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'source-owner approval is no longer active';
    END IF;

    PERFORM 1
      FROM operator_identity AS identity
      JOIN operator_organization_membership AS membership
        ON membership.operator_id = identity.id
      JOIN organization AS tenant ON tenant.id = membership.organization_id
     WHERE identity.id = accepting_operator_id
       AND identity.enabled AND tenant.status = 'active'
       AND membership.organization_id = transfer_row.target_organization_id
       AND membership.membership_role = 'tenant_admin'
       AND membership.revoked_at IS NULL
     FOR SHARE OF identity, membership, tenant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'acceptance requires an enabled target-owner tenant administrator';
    END IF;

    PERFORM 1
      FROM organization_member AS member
     WHERE member.location_id = transfer_row.location_id
       AND member.membership_type = 'owned' AND member.status = 'active'
     FOR UPDATE;

    IF EXISTS (
        SELECT 1 FROM organization_member AS member
         WHERE member.location_id = transfer_row.location_id
           AND member.membership_type = 'owned' AND member.status = 'active'
           AND member.organization_id <> transfer_row.source_organization_id
    ) THEN
        RAISE EXCEPTION 'conflicting active owner relationships must be reconciled first';
    END IF;

    SELECT array_agg(member.id ORDER BY member.id)
      INTO current_owner_relationship_ids
      FROM organization_member AS member
     WHERE member.location_id = transfer_row.location_id
       AND member.organization_id = transfer_row.source_organization_id
       AND member.membership_type = 'owned' AND member.status = 'active';
    IF current_owner_relationship_ids IS DISTINCT FROM transfer_row.source_owner_relationship_ids THEN
        RAISE EXCEPTION 'owner relationships changed after the transfer was requested';
    END IF;

    UPDATE location_tenant_owner_verification
       SET revoked_at = NOW(), revoked_by = accepting_operator_id::TEXT,
           revocation_reason = 'accepted tenant transfer ' || transfer_row.id::TEXT
     WHERE id = transfer_row.source_owner_verification_id AND revoked_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'source owner verification is no longer active';
    END IF;

    WITH revoked AS (
        UPDATE location_organization_share
           SET revoked_at = NOW(), revoked_by_operator_id = accepting_operator_id,
               revocation_reason = 'ownership transferred; transfer ' || transfer_row.id::TEXT,
               ownership_transfer_id = transfer_row.id
         WHERE location_id = transfer_row.location_id AND revoked_at IS NULL
         RETURNING id
    )
    SELECT COALESCE(array_agg(id ORDER BY id), '{}'::UUID[])
      INTO revoked_shares FROM revoked;

    WITH revoked AS (
        UPDATE operator_scope_grant
           SET revoked_at = NOW(), revoked_by = accepting_operator_id::TEXT,
               revocation_reason = 'ownership transferred; transfer ' || transfer_row.id::TEXT,
               ownership_transfer_id = transfer_row.id
         WHERE location_id = transfer_row.location_id AND revoked_at IS NULL
         RETURNING id
    )
    SELECT COALESCE(array_agg(id ORDER BY id), '{}'::UUID[])
      INTO revoked_grants FROM revoked;

    UPDATE organization_member
       SET status = 'inactive',
           metadata = COALESCE(metadata, '{}'::JSONB)
                      || jsonb_build_object('ownership_transfer_id', transfer_row.id,
                                            'transferred_to_organization_id', transfer_row.target_organization_id),
           updated_at = NOW()
     WHERE id = ANY(transfer_row.source_owner_relationship_ids)
       AND status = 'active';

    INSERT INTO organization_member (
        organization_id, location_id, farm_id, membership_type,
        join_date, role, status, metadata
    )
    SELECT transfer_row.target_organization_id,
           member.location_id,
           member.farm_id,
           'owned',
           CURRENT_DATE,
           member.role,
           'active',
           COALESCE(member.metadata, '{}'::JSONB)
             || jsonb_build_object(
                    'ownership_reconciliation', 'owner_confirmed',
                    'confirmed_at', to_char(CURRENT_DATE, 'YYYY-MM-DD'),
                    'ownership_transfer_id', transfer_row.id,
                    'transferred_from_organization_id', transfer_row.source_organization_id
                )
      FROM organization_member AS member
     WHERE member.id = ANY(transfer_row.source_owner_relationship_ids);
    GET DIAGNOSTICS inserted_relationship_count = ROW_COUNT;
    IF inserted_relationship_count <> cardinality(transfer_row.source_owner_relationship_ids) THEN
        RAISE EXCEPTION 'owner relationship copy was incomplete';
    END IF;

    UPDATE location
       SET organization_id = transfer_row.target_organization_id
     WHERE id = transfer_row.location_id
       AND organization_id = transfer_row.source_organization_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'location owner changed during transfer';
    END IF;

    INSERT INTO location_tenant_owner_verification (
        location_id, organization_id, decision_reference, confirmed_by, confirmed_at
    ) VALUES (
        transfer_row.location_id,
        transfer_row.target_organization_id,
        'ownership-transfer:' || transfer_row.id::TEXT,
        accepting_operator_id::TEXT,
        NOW()
    ) RETURNING id INTO new_owner_verification_id;

    UPDATE location_tenant_transfer
       SET status = 'accepted',
           accepted_by_operator_id = accepting_operator_id,
           acceptance_reference = btrim(acceptance_decision_reference),
           accepted_at = NOW(),
           resulting_owner_verification_id = new_owner_verification_id,
           revoked_share_ids = revoked_shares,
           revoked_scope_grant_ids = revoked_grants
     WHERE id = transfer_row.id;

    RETURN transfer_row.id;
END;
$$;

CREATE OR REPLACE FUNCTION cancel_location_tenant_transfer(
    requested_transfer_id UUID,
    cancelling_operator_id UUID,
    cancellation_reason_text TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    transfer_row location_tenant_transfer%ROWTYPE;
BEGIN
    IF cancellation_reason_text IS NULL
       OR length(btrim(cancellation_reason_text)) NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'cancellation reason is required';
    END IF;

    SELECT * INTO transfer_row
      FROM location_tenant_transfer
     WHERE id = requested_transfer_id AND status = 'pending'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'pending location tenant transfer was not found';
    END IF;

    PERFORM 1
      FROM operator_identity AS identity
      JOIN operator_organization_membership AS membership
        ON membership.operator_id = identity.id
     WHERE identity.id = cancelling_operator_id AND identity.enabled
       AND membership.organization_id = transfer_row.source_organization_id
       AND membership.membership_role = 'tenant_admin'
       AND membership.revoked_at IS NULL
     FOR SHARE OF identity, membership;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'cancellation requires an enabled source-owner tenant administrator';
    END IF;

    UPDATE location_tenant_transfer
       SET status = 'cancelled',
           cancelled_by_operator_id = cancelling_operator_id,
           cancellation_reason = btrim(cancellation_reason_text),
           cancelled_at = NOW()
     WHERE id = transfer_row.id;
    RETURN transfer_row.id;
END;
$$;

COMMENT ON TABLE location_tenant_transfer IS
    'Append-only pending/accepted/cancelled audit for a two-operator tenant-owner transfer; it is not a land-title record.';
COMMENT ON FUNCTION request_location_tenant_transfer(UUID, UUID, UUID, TEXT, TEXT) IS
    'Creates a pending transfer only for a verified owner location requested by an enabled source-owner tenant administrator.';
COMMENT ON FUNCTION accept_location_tenant_transfer(UUID, UUID, TEXT) IS
    'Atomically transfers the verified location tenant after a distinct enabled target-owner tenant administrator accepts; revokes prior shares and location grants.';
COMMENT ON FUNCTION cancel_location_tenant_transfer(UUID, UUID, TEXT) IS
    'Cancels a pending transfer through an enabled source-owner tenant administrator without changing ownership.';

COMMIT;
