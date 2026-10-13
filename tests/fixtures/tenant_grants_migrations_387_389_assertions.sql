BEGIN;

CREATE FUNCTION pg_temp.assert_true(assertion BOOLEAN, label TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF assertion IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'acceptance assertion failed: %', label;
    END IF;
END;
$$;

CREATE FUNCTION pg_temp.expect_statement_failure(
    statement TEXT, label TEXT, expected_error TEXT
)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE statement;
    EXCEPTION WHEN OTHERS THEN
        IF POSITION(expected_error IN SQLERRM) = 0 THEN
            RAISE EXCEPTION 'unexpected rejection for %: %', label, SQLERRM;
        END IF;
        RETURN;
    END;
    RAISE EXCEPTION 'acceptance statement unexpectedly succeeded: %', label;
END;
$$;

SELECT pg_temp.assert_true(
    (SELECT COUNT(*) = 2 FROM location_tenant_owner_verification),
    '387-388 seed exactly two confirmed owner rows'
);
SELECT pg_temp.assert_true(
    (SELECT COUNT(*) = 2
       FROM location_tenant_owner_verification AS owner
       JOIN organization AS tenant ON tenant.id = owner.organization_id
      WHERE tenant.org_key = 'kokonut-network' AND owner.revoked_at IS NULL),
    'both confirmed locations belong to Kokonut Network'
);

INSERT INTO operator_organization_membership (
    operator_id, organization_id, membership_role, granted_by
) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'a0000000-0000-0000-0000-000000000701', 'tenant_admin', 'acceptance'),
    ('a0000000-0000-0000-0000-000000000902', 'a0000000-0000-0000-0000-000000000800', 'operator', 'acceptance');

INSERT INTO operator_scope_grant (
    operator_id, resource, action, location_id, granted_by, organization_id
) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000901', 'mobile_collection_review', 'read_detail', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'edit_draft', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'read_detail', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'submit', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000800'),
    ('a0000000-0000-0000-0000-000000000902', 'mobile_collection_review', 'read_detail', 'a0000000-0000-0000-0000-000000000001', 'acceptance', 'a0000000-0000-0000-0000-000000000800'),
    ('a0000000-0000-0000-0000-000000000903', 'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000001', 'acceptance', NULL),
    ('a0000000-0000-0000-0000-000000000903', 'mobile_collection_review', 'read_detail', 'a0000000-0000-0000-0000-000000000001', 'acceptance', NULL),
    ('a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft', 'a0000000-0000-0000-0000-000000000003', 'acceptance', 'a0000000-0000-0000-0000-000000000701');

SELECT pg_temp.assert_true(
    operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'owner grant is allowed'
);
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'partner grant is denied without an explicit share'
);

INSERT INTO location_organization_share (
    location_id, organization_id, granted_by_operator_id, reason
) VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000800',
    'a0000000-0000-0000-0000-000000000901',
    'synthetic acceptance share'
);
SELECT pg_temp.assert_true(
    operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'partner grant is allowed while an explicit share is active'
);
UPDATE location_organization_share
   SET expires_at = NOW() - INTERVAL '1 second'
 WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
   AND organization_id = 'a0000000-0000-0000-0000-000000000800';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'expired share denies the partner grant'
);
UPDATE location_organization_share
   SET expires_at = NULL,
       revoked_at = NOW(),
       revoked_by_operator_id = 'a0000000-0000-0000-0000-000000000901',
       revocation_reason = 'synthetic acceptance revocation'
 WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
   AND organization_id = 'a0000000-0000-0000-0000-000000000800';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'revoked share denies the partner grant'
);

UPDATE operator_organization_membership
   SET revoked_at = NOW(), revoked_by = 'acceptance', revocation_reason = 'synthetic revocation'
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000902';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'revoked organization membership denies access'
);
UPDATE operator_organization_membership
   SET revoked_at = NULL, revoked_by = NULL, revocation_reason = NULL
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000902';

UPDATE organization SET status = 'inactive'
 WHERE id = 'a0000000-0000-0000-0000-000000000800';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'inactive organization denies access'
);
UPDATE organization SET status = 'active'
 WHERE id = 'a0000000-0000-0000-0000-000000000800';

UPDATE operator_identity SET enabled = FALSE
 WHERE id = 'a0000000-0000-0000-0000-000000000902';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'disabled identity denies access'
);
UPDATE operator_identity SET enabled = TRUE
 WHERE id = 'a0000000-0000-0000-0000-000000000902';

UPDATE operator_scope_grant SET revoked_at = NOW()
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000902'
   AND resource = 'farm_activity' AND action = 'create_draft';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000902', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'revoked resource grant denies access'
);

SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000003'
    ),
    'unverified location denies tenant-qualified grant'
);
UPDATE location SET organization_id = 'a0000000-0000-0000-0000-000000000800'
 WHERE id = 'a0000000-0000-0000-0000-000000000001';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000901', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'stale ownership verification denies access'
);
UPDATE location SET organization_id = 'a0000000-0000-0000-0000-000000000701'
 WHERE id = 'a0000000-0000-0000-0000-000000000001';

SELECT pg_temp.assert_true(
    operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000903', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'legacy NULL-tenant grant remains compatible'
);
UPDATE operator_identity SET enabled = FALSE
 WHERE id = 'a0000000-0000-0000-0000-000000000903';
SELECT pg_temp.assert_true(
    NOT operator_scope_grant_allows(
        'a0000000-0000-0000-0000-000000000903', 'farm_activity', 'create_draft',
        'a0000000-0000-0000-0000-000000000001'
    ),
    'legacy grant still requires an enabled identity'
);
UPDATE operator_identity SET enabled = TRUE
 WHERE id = 'a0000000-0000-0000-0000-000000000903';

SELECT set_config('kokonut.actor_id', 'a0000000-0000-0000-0000-000000000901', TRUE);
UPDATE operator_scope_grant SET revoked_at = NOW()
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_statement_failure(
    $$INSERT INTO farm_activity (id, location_id, activity_type, activity_date, source_system, source_raw)
      VALUES ('a0000000-0000-0000-0000-000000000911', 'a0000000-0000-0000-0000-000000000001', 'weeding', CURRENT_DATE, 'field_collector', '{"form_id":"farm_activity_v1","form_version":"1.2.0"}')$$,
    'draft insert requires both tenant-aware create and review grants',
    'Field Collector draft creation requires current tenant-aware grants'
);
UPDATE operator_scope_grant SET revoked_at = NULL
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';

INSERT INTO farm_activity (
    id, location_id, activity_type, activity_date, notes, source_system, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000912',
    'a0000000-0000-0000-0000-000000000001',
    'weeding', CURRENT_DATE, 'initial note', 'field_collector',
    '{"form_id":"farm_activity_v1","form_version":"1.2.0"}'
);
UPDATE farm_activity SET notes = 'reviewed edit'
 WHERE id = 'a0000000-0000-0000-0000-000000000912';

UPDATE operator_scope_grant SET revoked_at = NOW()
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_statement_failure(
    $$UPDATE farm_activity SET notes = 'denied edit'
      WHERE id = 'a0000000-0000-0000-0000-000000000912'$$,
    'draft edit requires create-independent edit, canonical detail, and review detail grants',
    'Field Collector draft edit requires current tenant-aware grants'
);
UPDATE operator_scope_grant SET revoked_at = NULL
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';

INSERT INTO farm_activity_workflow_event (
    farm_activity_id, location_id, actor_operator_id, action
) VALUES (
    'a0000000-0000-0000-0000-000000000912',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000901', 'submitted'
);
UPDATE operator_scope_grant SET revoked_at = NOW()
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'farm_activity' AND action = 'submit'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_statement_failure(
    $$INSERT INTO farm_activity_workflow_event (
          farm_activity_id, location_id, actor_operator_id, action
      ) VALUES (
          'a0000000-0000-0000-0000-000000000912',
          'a0000000-0000-0000-0000-000000000001',
          'a0000000-0000-0000-0000-000000000901', 'submitted'
      )$$,
    'workflow event requires a current tenant-aware action grant',
    'Field Collector workflow event requires a current tenant-aware grant'
);
UPDATE operator_scope_grant SET revoked_at = NULL
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'farm_activity' AND action = 'submit'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';

UPDATE operator_scope_grant SET revoked_at = NOW()
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';
SELECT pg_temp.expect_statement_failure(
    $$INSERT INTO farm_activity_workflow_event (
          farm_activity_id, location_id, actor_operator_id, action
      ) VALUES (
          'a0000000-0000-0000-0000-000000000912',
          'a0000000-0000-0000-0000-000000000001',
          'a0000000-0000-0000-0000-000000000901', 'draft_edited'
      )$$,
    'draft-edited event requires current private detail grants',
    'Field Collector draft edit requires current tenant-aware detail grants'
);
UPDATE operator_scope_grant SET revoked_at = NULL
 WHERE operator_id = 'a0000000-0000-0000-0000-000000000901'
   AND resource = 'mobile_collection_review' AND action = 'read_detail'
   AND location_id = 'a0000000-0000-0000-0000-000000000001';
INSERT INTO farm_activity_workflow_event (
    farm_activity_id, location_id, actor_operator_id, action
) VALUES (
    'a0000000-0000-0000-0000-000000000912',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000901', 'draft_edited'
);

-- The legacy compatibility branch remains effective at the Field Collector write boundary.
SELECT set_config('kokonut.actor_id', 'a0000000-0000-0000-0000-000000000903', TRUE);
INSERT INTO farm_activity (
    id, location_id, activity_type, activity_date, source_system, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000913',
    'a0000000-0000-0000-0000-000000000001',
    'mulching', CURRENT_DATE, 'field_collector',
    '{"form_id":"farm_activity_v1","form_version":"1.2.0"}'
);

-- Migration 389 is deliberately limited to the current native form identity.
INSERT INTO farm_activity (
    id, location_id, activity_type, activity_date, source_system, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000914',
    'a0000000-0000-0000-0000-000000000001',
    'mulching', CURRENT_DATE, 'manual', '{"form_id":"manual","form_version":"1"}'
);

COMMIT;
