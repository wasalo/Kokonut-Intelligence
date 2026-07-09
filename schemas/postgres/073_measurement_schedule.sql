-- 073_measurement_schedule.sql
-- Measurement Schedule: tracking cadence and due dates for forest monitoring
-- Inspired by Open Forest Protocol's measurement frequency model

BEGIN;

-- ============================================================================
-- ADD MEASUREMENT SCHEDULE COLUMNS TO FARM_ZONE
-- ============================================================================

ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS measurement_frequency VARCHAR(50)
    DEFAULT 'semi_annual'
    CHECK (measurement_frequency IN ('monthly', 'quarterly', 'semi_annual', 'annual'));

ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS last_measurement_date DATE;

ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS next_measurement_due DATE;

COMMENT ON COLUMN farm_zone.measurement_frequency IS 'How often measurement should occur: monthly, quarterly, semi_annual, annual';
COMMENT ON COLUMN farm_zone.last_measurement_date IS 'Date of most recent measurement for this zone';
COMMENT ON COLUMN farm_zone.next_measurement_due IS 'Calculated next measurement due date based on frequency';

-- ============================================================================
-- ADD MEASUREMENT SCHEDULE COLUMNS TO TREE_RECORD
-- ============================================================================

ALTER TABLE tree_record ADD COLUMN IF NOT EXISTS measurement_frequency VARCHAR(50)
    CHECK (measurement_frequency IN ('monthly', 'quarterly', 'semi_annual', 'annual'));

ALTER TABLE tree_record ADD COLUMN IF NOT EXISTS next_measurement_due DATE;

COMMENT ON COLUMN tree_record.measurement_frequency IS 'Override measurement frequency for individual tree (NULL = use zone default)';
COMMENT ON COLUMN tree_record.next_measurement_due IS 'Next measurement due date for this individual tree';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_farm_zone_measurement_due ON farm_zone(next_measurement_due)
    WHERE next_measurement_due IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_farm_zone_measurement_freq ON farm_zone(measurement_frequency)
    WHERE measurement_frequency IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tree_measurement_due ON tree_record(next_measurement_due)
    WHERE next_measurement_due IS NOT NULL;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Measurement schedule overview per zone
CREATE OR REPLACE VIEW v_measurement_schedule AS
SELECT
    fz.id AS zone_id,
    fz.location_id,
    l.name AS location_name,
    fz.zone_key,
    fz.name AS zone_name,
    fz.zone_type,
    fz.measurement_frequency,
    fz.last_measurement_date,
    fz.next_measurement_due,
    CASE
        WHEN fz.next_measurement_due IS NULL THEN 'no_schedule'
        WHEN fz.next_measurement_due <= CURRENT_DATE THEN 'overdue'
        WHEN fz.next_measurement_due <= CURRENT_DATE + INTERVAL '14 days' THEN 'due_soon'
        ELSE 'on_track'
    END AS schedule_status,
    CASE
        WHEN fz.next_measurement_due IS NOT NULL AND fz.next_measurement_due <= CURRENT_DATE
        THEN (CURRENT_DATE - fz.next_measurement_due)::int
        ELSE NULL
    END AS days_overdue,
    (SELECT COUNT(*) FROM tree_record t WHERE t.zone_id = fz.id AND t.status = 'alive') AS tree_count
FROM farm_zone fz
JOIN location l ON fz.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND fz.measurement_frequency IS NOT NULL;

-- 2. Overdue measurements summary per location
CREATE OR REPLACE VIEW v_measurement_overdue_summary AS
SELECT
    fz.location_id,
    l.name AS location_name,
    COUNT(*) AS total_scheduled_zones,
    COUNT(*) FILTER (WHERE fz.next_measurement_due <= CURRENT_DATE) AS overdue_count,
    COUNT(*) FILTER (WHERE fz.next_measurement_due > CURRENT_DATE
                     AND fz.next_measurement_due <= CURRENT_DATE + INTERVAL '14 days') AS due_soon_count,
    COUNT(*) FILTER (WHERE fz.next_measurement_due > CURRENT_DATE + INTERVAL '14 days') AS on_track_count,
    MIN(fz.next_measurement_due) FILTER (WHERE fz.next_measurement_due <= CURRENT_DATE) AS earliest_overdue_date
FROM farm_zone fz
JOIN location l ON fz.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND fz.measurement_frequency IS NOT NULL
GROUP BY fz.location_id, l.name;

-- 3. Individual tree measurement schedule
CREATE OR REPLACE VIEW v_tree_measurement_schedule AS
SELECT
    t.id AS tree_id,
    t.location_id,
    l.name AS location_name,
    t.zone_id,
    fz.name AS zone_name,
    t.plot_id,
    t.tree_tag,
    t.species_name,
    COALESCE(t.measurement_frequency, fz.measurement_frequency) AS effective_frequency,
    t.next_measurement_due,
    t.last_survey_date,
    CASE
        WHEN t.next_measurement_due IS NULL THEN 'no_schedule'
        WHEN t.next_measurement_due <= CURRENT_DATE THEN 'overdue'
        WHEN t.next_measurement_due <= CURRENT_DATE + INTERVAL '14 days' THEN 'due_soon'
        ELSE 'on_track'
    END AS schedule_status
FROM tree_record t
JOIN location l ON t.location_id = l.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published')
  AND t.status = 'alive';

COMMIT;
