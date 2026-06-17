-- Per-square-meter revenue: add bed-level fields to plot
-- Enables granular yield/revenue calculation:
--   Total Production = Planting Density/m² × Bed Area m² × Beds/Plot × Plots × (1 − Loss Rate)

ALTER TABLE plot
    ADD COLUMN IF NOT EXISTS bed_count INTEGER,
    ADD COLUMN IF NOT EXISTS bed_area_sqm NUMERIC(10,2);

COMMENT ON COLUMN plot.bed_count IS 'Number of cultivation beds in this plot';
COMMENT ON COLUMN plot.bed_area_sqm IS 'Area of each bed in square meters (uniform per plot)';
