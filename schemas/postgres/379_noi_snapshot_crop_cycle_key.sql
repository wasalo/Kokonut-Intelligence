-- Crop-cycle NOI is a current snapshot, not an append-only history. The
-- Directus and Kernel reconcilers both upsert by crop_cycle_id, so enforce
-- that contract in PostgreSQL. If historical duplicates exist, fail this
-- migration transactionally and require an explicit data review first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_noi_snapshot_crop_cycle_id
    ON noi_snapshot (crop_cycle_id);
