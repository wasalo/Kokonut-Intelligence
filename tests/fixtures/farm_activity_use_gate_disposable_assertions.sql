-- Apply after the disposable setup and migration 386.
DO $$
DECLARE
    expected_gate JSONB := '{"_and":[{"_or":[{"source_system":{"_null":true}},{"source_system":{"_neq":"field_collector"}}]}]}'::JSONB;
BEGIN
    IF NOT farm_activity_source_eligible_for_use(
        'field_collector', '44444444-4444-4444-8444-444444444444',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"44444444-4444-4444-8444-444444444444"}',
        '11111111-1111-4111-8111-111111111111'
    ) THEN
        RAISE EXCEPTION 'active, synced, consented source should be eligible';
    END IF;

    IF NOT farm_activity_source_eligible_for_use('legacy_import', 'legacy-1', '{}',
        '11111111-1111-4111-8111-111111111111') THEN
        RAISE EXCEPTION 'legacy source behavior should be preserved';
    END IF;

    IF farm_activity_source_eligible_for_use(
        'field_collector', '44444444-4444-4444-8444-444444444444',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"44444444-4444-4444-8444-444444444444"}',
        '66666666-6666-4666-8666-666666666666'
    ) THEN
        RAISE EXCEPTION 'cross-location source should fail closed';
    END IF;

    IF farm_activity_source_eligible_for_use(
        'field_collector', 'not-a-uuid',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"not-a-uuid"}',
        '11111111-1111-4111-8111-111111111111'
    ) THEN
        RAISE EXCEPTION 'malformed source ID should fail closed';
    END IF;

    IF farm_activity_source_eligible_for_use(
        'field_collector', '44444444-4444-4444-8444-444444444444',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"55555555-5555-4555-8555-555555555555"}',
        '11111111-1111-4111-8111-111111111111'
    ) THEN
        RAISE EXCEPTION 'mismatched payload source ID should fail closed';
    END IF;

    IF EXISTS (
        SELECT 1 FROM directus_permissions
         WHERE collection = 'farm_activity' AND action = 'read'
           AND permissions::jsonb @> expected_gate
    ) IS FALSE THEN
        RAISE EXCEPTION 'Directus read permission must exclude Field Collector rows';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM directus_permissions
         WHERE id = 'a1000000-0000-0000-0000-000000000001'
           AND permissions::jsonb @> '{"_and":[{"_and":[{"location_id":{"_eq":"11111111-1111-4111-8111-111111111111"}}]},{"_or":[{"source_system":{"_null":true}},{"source_system":{"_neq":"field_collector"}}]}]}'::JSONB
    ) THEN
        RAISE EXCEPTION 'Directus migration must preserve existing location scopes';
    END IF;

    IF EXISTS (
        WITH RECURSIVE permission_nodes(permission_id, node) AS (
            SELECT permission.id, COALESCE(permission.permissions, '{}'::JSON)::jsonb
              FROM directus_permissions AS permission
             WHERE permission.collection = 'farm_activity'
               AND permission.action = 'read'
            UNION ALL
            SELECT parent.permission_id, child.value
              FROM permission_nodes AS parent
              CROSS JOIN LATERAL (
                  SELECT value
                    FROM jsonb_each(
                        CASE WHEN jsonb_typeof(parent.node) = 'object'
                             THEN parent.node ELSE '{}'::jsonb END
                    )
                  UNION ALL
                  SELECT value
                    FROM jsonb_array_elements(
                        CASE WHEN jsonb_typeof(parent.node) = 'array'
                             THEN parent.node ELSE '[]'::jsonb END
                    )
              ) AS child
        )
        SELECT permission.id
          FROM directus_permissions AS permission
          JOIN permission_nodes AS node ON node.permission_id = permission.id
         WHERE permission.collection = 'farm_activity'
           AND permission.action = 'read'
         GROUP BY permission.id
        HAVING COUNT(*) FILTER (WHERE node.node = expected_gate->'_and'->0) <> 1
    ) OR EXISTS (
        SELECT 1 FROM directus_permissions
         WHERE collection = 'farm_activity' AND action = 'read'
           AND permissions IS NULL
    ) THEN
        RAISE EXCEPTION 'Directus source gate must be present exactly once, including null scopes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 'farm-activity-consent-use-gate-v1') THEN
        RAISE EXCEPTION 'migration version marker is missing';
    END IF;
END;
$$;

-- Consent withdrawal blocks content edits and productive lifecycle progress.
INSERT INTO collection_consent_event_fixture (collection_id, event_sequence, event_type) VALUES
    ('44444444-4444-4444-8444-444444444444', 2, 'withdrawal'),
    ('44444444-4444-4444-8444-444444444444', 3, 'grant');

DO $$
BEGIN
    IF farm_activity_source_eligible_for_use(
        'field_collector', '44444444-4444-4444-8444-444444444444',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"44444444-4444-4444-8444-444444444444"}',
        '11111111-1111-4111-8111-111111111111'
    ) THEN
        RAISE EXCEPTION 'withdrawn source remained eligible';
    END IF;

    BEGIN
        UPDATE farm_activity SET status = 'submitted'
         WHERE id = '77777777-7777-4777-8777-777777777777';
        RAISE EXCEPTION 'productive transition unexpectedly succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM = 'productive transition unexpectedly succeeded'
           OR SQLERRM NOT LIKE '%ineligible for further use%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        UPDATE farm_activity SET description = 'edited after withdrawal'
         WHERE id = '77777777-7777-4777-8777-777777777777';
        RAISE EXCEPTION 'content edit unexpectedly succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM = 'content edit unexpectedly succeeded'
           OR SQLERRM NOT LIKE '%ineligible for further use%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        UPDATE farm_activity SET source_id = 'legacy-1'
         WHERE id = '77777777-7777-4777-8777-777777777777';
        RAISE EXCEPTION 'source provenance edit unexpectedly succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM = 'source provenance edit unexpectedly succeeded'
           OR SQLERRM NOT LIKE '%source provenance is immutable%' THEN
            RAISE;
        END IF;
    END;
END;
$$;

-- Reasoned disposition remains possible while use is blocked.
UPDATE farm_activity SET status = 'rejected'
 WHERE id = '77777777-7777-4777-8777-777777777777';

-- The active-to-retired transition queues linked collections and revokes use.
UPDATE mobile_form_version SET status = 'retired'
 WHERE id = '33333333-3333-4333-8333-333333333333';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM offline_collection
         WHERE id = '55555555-5555-4555-8555-555555555555'
           AND form_validation_status = 'retired_review'
           AND form_review_required IS TRUE
    ) THEN
        RAISE EXCEPTION 'retired form collection was not queued for review';
    END IF;

    IF farm_activity_source_eligible_for_use(
        'field_collector', '55555555-5555-4555-8555-555555555555',
        '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"55555555-5555-4555-8555-555555555555"}',
        '66666666-6666-4666-8666-666666666666'
    ) THEN
        RAISE EXCEPTION 'retired form source remained eligible';
    END IF;

    IF (SELECT status FROM farm_activity WHERE id = '77777777-7777-4777-8777-777777777777') <> 'rejected' THEN
        RAISE EXCEPTION 'disposition status was not retained';
    END IF;

    IF EXISTS (
        SELECT 1 FROM dashboard_dataset
         WHERE id = 'd1000000-0000-0000-0000-000000000001'
           AND query_sql NOT LIKE '%farm_activity_source_eligible_for_use%'
    ) THEN
        RAISE EXCEPTION 'farm activity dashboard was not eligibility-gated';
    END IF;

    IF EXISTS (
        SELECT 1 FROM dashboard_dataset
         WHERE id = 'd1040000-0000-0000-0000-000000000001'
           AND query_sql NOT LIKE '%farm_activity_source_eligible_for_use%'
    ) THEN
        RAISE EXCEPTION 'VSM dashboard was not eligibility-gated';
    END IF;
END;
$$;
