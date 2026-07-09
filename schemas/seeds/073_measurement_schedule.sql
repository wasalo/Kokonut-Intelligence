-- ============================================================
-- 073_measurement_schedule.sql — Seeds: Adelphi measurement schedules
-- ============================================================

-- Set measurement schedules for Adelphi farm zones
UPDATE farm_zone SET
    measurement_frequency = 'semi_annual',
    last_measurement_date = '2026-06-01',
    next_measurement_due = '2026-12-01'
WHERE zone_key = 'adelphi-syntropic-beds';

UPDATE farm_zone SET
    measurement_frequency = 'semi_annual',
    last_measurement_date = '2026-06-01',
    next_measurement_due = '2026-12-01'
WHERE zone_key = 'adelphi-agroforestry-corridor';

UPDATE farm_zone SET
    measurement_frequency = 'quarterly',
    last_measurement_date = '2026-06-01',
    next_measurement_due = '2026-09-01'
WHERE zone_key = 'adelphi-nursery-biofactory';

UPDATE farm_zone SET
    measurement_frequency = 'annual',
    last_measurement_date = '2026-06-01',
    next_measurement_due = '2027-06-01'
WHERE zone_key = 'adelphi-poultry-loop';
