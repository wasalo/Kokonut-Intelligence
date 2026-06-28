-- Per-square-meter revenue: bed data for pilot plots
-- Depends on: 001_pilot_farm.sql (plot)
-- Plot A: 4 ha, 20 beds × 1.2 m² = 24 m² total bed area
-- Plot B: 3 ha, 15 beds × 1.0 m² = 15 m² total bed area
-- Plot C: 5 ha, 25 beds × 1.5 m² = 37.5 m² total bed area
UPDATE plot SET bed_count = 20, bed_area_sqm = 1.20 WHERE id = 'a0000000-0000-0000-0000-000000000020';
UPDATE plot SET bed_count = 15, bed_area_sqm = 1.00 WHERE id = 'a0000000-0000-0000-0000-000000000021';
UPDATE plot SET bed_count = 25, bed_area_sqm = 1.50 WHERE id = 'a0000000-0000-0000-0000-000000000022';
