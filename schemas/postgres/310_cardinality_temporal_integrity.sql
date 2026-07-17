-- ============================================================
-- 310_cardinality_temporal_integrity.sql
-- Enforce selected semantic uniqueness rules.
-- ============================================================

-- A farmer may retain historical KYC results, but only one approved result
-- per verification method is current.
CREATE UNIQUE INDEX IF NOT EXISTS uq_kyc_current_approved_method
    ON kyc_verification(farmer_id, verification_method)
    WHERE verification_status = 'approved';

-- Active role assignments are unique within their semantic scope. The zero
-- UUID makes NULL global scope participate in the uniqueness key.
CREATE UNIQUE INDEX IF NOT EXISTS uq_role_assignment_active_scope
    ON role_assignment(
        farmer_id,
        COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid),
        role,
        scope
    )
    WHERE status = 'active';

-- A metric has one current value for a metric/location/period/method tuple.
-- Historical recalculations must use a distinct computation method.
CREATE UNIQUE INDEX IF NOT EXISTS uq_metric_value_semantic_current
    ON metric_value(
        metric_id,
        COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(period_start, '0001-01-01'::date),
        COALESCE(period_end, '0001-01-01'::date),
        COALESCE(computation_method, '')
    );

-- Domain time ranges must be ordered and non-negative. These checks are
-- deliberately additive; overlap policy remains domain-specific.
ALTER TABLE kyc_verification
    DROP CONSTRAINT IF EXISTS chk_kyc_expiry_after_creation;
ALTER TABLE kyc_verification
    ADD CONSTRAINT chk_kyc_expiry_after_creation
    CHECK (expires_at IS NULL OR expires_at >= created_at);

ALTER TABLE cooperative_board_member
    DROP CONSTRAINT IF EXISTS chk_board_term_order;
ALTER TABLE cooperative_board_member
    ADD CONSTRAINT chk_board_term_order
    CHECK (term_end IS NULL OR term_end >= term_start);

ALTER TABLE forecast_scenario
    DROP CONSTRAINT IF EXISTS chk_forecast_version_positive;
ALTER TABLE forecast_scenario
    ADD CONSTRAINT chk_forecast_version_positive
    CHECK (version > 0);

COMMENT ON INDEX uq_kyc_current_approved_method IS 'One current approved KYC result per farmer and verification method';
COMMENT ON INDEX uq_role_assignment_active_scope IS 'One active role assignment per farmer and semantic scope';
COMMENT ON INDEX uq_metric_value_semantic_current IS 'One metric result per semantic metric/location/period/method tuple';
