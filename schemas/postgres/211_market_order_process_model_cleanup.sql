-- ============================================================
-- 211_market_order_process_model_cleanup.sql
-- ============================================================
-- Remove states left by the earlier, incorrect publication-style
-- market_order workflow. Migration 186 upserts the canonical states but
-- cannot remove rows already present in persistent databases.

DELETE FROM process_model
WHERE entity_type = 'market_order'
  AND status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled');
