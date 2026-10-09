-- ============================================================
-- 275_strategy_evidence_identity_fix.sql
-- Make nullable evidence identity fields idempotent.
-- ============================================================

ALTER TABLE strategy_evidence_link
    DROP CONSTRAINT IF EXISTS strategy_evidence_link_strategy_plan_id_subject_type_subject_id_source_type_source_id_source_ref_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_evidence_link_identity
    ON strategy_evidence_link(strategy_plan_id, subject_type, subject_id, source_type,
                              COALESCE(source_id, '00000000-0000-0000-0000-000000000000'::uuid),
                              COALESCE(source_ref, ''));
