-- ============================================================
-- 314_reference_policy_correction.sql
-- Correct the strategy advantage policy without editing migration 311.
-- ============================================================

UPDATE relationship_reference_policy
SET allowed_type_values = ARRAY['capability', 'process', 'service', 'value_stream', 'strategy_choice', 'investment'],
    enforcement_status = 'typed_table_planned',
    updated_at = NOW()
WHERE table_name = 'strategy_advantage_link'
  AND type_column = 'entity_type'
  AND id_column = 'entity_id';
